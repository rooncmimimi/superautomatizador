"""Histórico local em SQLite: execuções, documentos, linhas e valores com origem e evidência."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from automatizador.aplicacao.portas import DocumentoRegistrado, ExecucaoRegistrada, ValorRegistrado, VersaoValor
from automatizador.dominio.modelo import ConteudoDocumento, Linha, ValorCampo

ESQUEMA = """
CREATE TABLE IF NOT EXISTS execucao (
    id INTEGER PRIMARY KEY,
    descricao TEXT NOT NULL,
    inicio TEXT NOT NULL,
    fim TEXT,
    resultado TEXT NOT NULL,
    erro TEXT
);
CREATE TABLE IF NOT EXISTS documento (
    id INTEGER PRIMARY KEY,
    execucao_id INTEGER NOT NULL REFERENCES execucao(id),
    nome TEXT NOT NULL,
    caminho TEXT NOT NULL,
    hash_sha256 TEXT NOT NULL,
    paginas INTEGER NOT NULL,
    importado_em TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS documento_hash ON documento(hash_sha256);
CREATE TABLE IF NOT EXISTS linha (
    id INTEGER PRIMARY KEY,
    documento_id INTEGER NOT NULL REFERENCES documento(id),
    ordem INTEGER NOT NULL,
    aprovada_por TEXT,
    aprovada_em TEXT
);
CREATE TABLE IF NOT EXISTS valor_campo (
    id INTEGER PRIMARY KEY,
    linha_id INTEGER NOT NULL REFERENCES linha(id),
    coluna TEXT NOT NULL,
    valor TEXT,
    origem TEXT NOT NULL,
    trecho TEXT,
    pagina INTEGER,
    confianca REAL,
    pendencia TEXT,
    versao INTEGER NOT NULL DEFAULT 1,
    usuario TEXT,
    criado_em TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS exportacao (
    id INTEGER PRIMARY KEY,
    execucao_id INTEGER NOT NULL REFERENCES execucao(id),
    arquivo TEXT NOT NULL,
    linhas INTEGER NOT NULL,
    criado_em TEXT NOT NULL
);
"""


def _agora() -> str:
    return datetime.now().isoformat(timespec="seconds")


class RepositorioSqlite:
    def __init__(self, caminho: Path):
        caminho = Path(caminho)
        caminho.parent.mkdir(parents=True, exist_ok=True)
        self._conexao = sqlite3.connect(caminho)
        self._conexao.execute("PRAGMA foreign_keys = ON")
        self._conexao.executescript(ESQUEMA)
        self._migrar()

    def _migrar(self) -> None:
        """Atualiza bancos criados por versões anteriores do aplicativo."""
        colunas_linha = {c[1] for c in self._conexao.execute("PRAGMA table_info(linha)")}
        colunas_valor = {c[1] for c in self._conexao.execute("PRAGMA table_info(valor_campo)")}
        with self._conexao:
            if "aprovada_por" not in colunas_linha:
                self._conexao.execute("ALTER TABLE linha ADD COLUMN aprovada_por TEXT")
                self._conexao.execute("ALTER TABLE linha ADD COLUMN aprovada_em TEXT")
            if "usuario" not in colunas_valor:
                self._conexao.execute("ALTER TABLE valor_campo ADD COLUMN usuario TEXT")

    def iniciar_execucao(self, descricao: str) -> int:
        with self._conexao:
            cursor = self._conexao.execute(
                "INSERT INTO execucao (descricao, inicio, resultado) VALUES (?, ?, 'em_andamento')",
                (descricao, _agora()),
            )
        return cursor.lastrowid

    def finalizar_execucao(self, execucao_id: int, resultado: str, erro: str | None = None) -> None:
        with self._conexao:
            self._conexao.execute(
                "UPDATE execucao SET fim = ?, resultado = ?, erro = ? WHERE id = ?",
                (_agora(), resultado, erro, execucao_id),
            )

    def registrar_documento(
        self, execucao_id: int, conteudo: ConteudoDocumento, linhas: list[Linha]
    ) -> DocumentoRegistrado:
        agora = _agora()
        with self._conexao:
            documento_id = self._conexao.execute(
                "INSERT INTO documento (execucao_id, nome, caminho, hash_sha256, paginas, importado_em)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (
                    execucao_id,
                    conteudo.caminho.name,
                    str(conteudo.caminho),
                    conteudo.hash_sha256,
                    len(conteudo.paginas),
                    agora,
                ),
            ).lastrowid
            for linha in linhas:
                linha_id = self._conexao.execute(
                    "INSERT INTO linha (documento_id, ordem) VALUES (?, ?)", (documento_id, linha.ordem)
                ).lastrowid
                linha.id = linha_id
                self._conexao.executemany(
                    "INSERT INTO valor_campo (linha_id, coluna, valor, origem, trecho, pagina, confianca,"
                    " pendencia, criado_em) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    [
                        (
                            linha_id,
                            v.coluna,
                            v.valor,
                            str(v.origem),
                            v.trecho,
                            v.pagina,
                            v.confianca,
                            v.pendencia,
                            agora,
                        )
                        for v in linha.valores.values()
                    ],
                )
        return DocumentoRegistrado(documento_id, conteudo.caminho.name)

    def registrar_correcao(self, linha_id: int, valores: list[ValorCampo], usuario: str) -> None:
        """Grava cada valor como nova versão e desfaz a aprovação da linha, numa transação só.

        As versões anteriores continuam no histórico.
        """
        agora = _agora()
        with self._conexao:
            for valor in valores:
                versao = self._conexao.execute(
                    "SELECT COALESCE(MAX(versao), 0) + 1 FROM valor_campo WHERE linha_id = ? AND coluna = ?",
                    (linha_id, valor.coluna),
                ).fetchone()[0]
                self._conexao.execute(
                    "INSERT INTO valor_campo (linha_id, coluna, valor, origem, trecho, pagina, confianca,"
                    " pendencia, versao, usuario, criado_em) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        linha_id,
                        valor.coluna,
                        valor.valor,
                        str(valor.origem),
                        valor.trecho,
                        valor.pagina,
                        valor.confianca,
                        valor.pendencia,
                        versao,
                        usuario,
                        agora,
                    ),
                )
            self._conexao.execute(
                "UPDATE linha SET aprovada_por = NULL, aprovada_em = NULL WHERE id = ?", (linha_id,)
            )

    def registrar_aprovacao(self, linha_ids: list[int], usuario: str) -> None:
        agora = _agora()
        with self._conexao:
            self._conexao.executemany(
                "UPDATE linha SET aprovada_por = ?, aprovada_em = ? WHERE id = ?",
                [(usuario, agora, linha_id) for linha_id in linha_ids],
            )

    def versoes_do_valor(self, linha_id: int, coluna: str) -> list[VersaoValor]:
        cursor = self._conexao.execute(
            "SELECT versao, valor, origem, usuario, criado_em FROM valor_campo"
            " WHERE linha_id = ? AND coluna = ? ORDER BY versao",
            (linha_id, coluna),
        )
        return [VersaoValor(*registro) for registro in cursor.fetchall()]

    def aprovacao_da_linha(self, linha_id: int) -> tuple[str | None, str | None]:
        return self._conexao.execute(
            "SELECT aprovada_por, aprovada_em FROM linha WHERE id = ?", (linha_id,)
        ).fetchone()

    def registrar_exportacao(self, execucao_id: int, destino: Path, quantidade_linhas: int) -> None:
        with self._conexao:
            self._conexao.execute(
                "INSERT INTO exportacao (execucao_id, arquivo, linhas, criado_em) VALUES (?, ?, ?, ?)",
                (execucao_id, str(destino), quantidade_linhas, _agora()),
            )

    def valores_do_documento(self, documento_id: int) -> list[ValorRegistrado]:
        cursor = self._conexao.execute(
            "SELECT l.ordem, v.coluna, v.valor, v.origem, v.trecho, v.pagina, v.confianca, v.pendencia"
            " FROM valor_campo v JOIN linha l ON l.id = v.linha_id"
            " WHERE l.documento_id = ? AND v.versao = ("
            "   SELECT MAX(u.versao) FROM valor_campo u WHERE u.linha_id = v.linha_id AND u.coluna = v.coluna)"
            " ORDER BY l.ordem, v.id",
            (documento_id,),
        )
        return [ValorRegistrado(*registro) for registro in cursor.fetchall()]

    def execucoes(self) -> list[ExecucaoRegistrada]:
        cursor = self._conexao.execute("SELECT id, inicio, fim, resultado, erro FROM execucao ORDER BY id")
        return [
            ExecucaoRegistrada(
                id,
                datetime.fromisoformat(inicio),
                datetime.fromisoformat(fim) if fim else None,
                resultado,
                erro,
            )
            for id, inicio, fim, resultado, erro in cursor.fetchall()
        ]

    def fechar(self) -> None:
        self._conexao.close()
