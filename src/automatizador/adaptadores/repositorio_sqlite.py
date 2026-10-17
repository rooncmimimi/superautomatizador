"""Histórico local em SQLite: execuções, documentos, linhas e valores com origem e evidência."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from automatizador.aplicacao.portas import DocumentoRegistrado, ExecucaoRegistrada, ValorRegistrado
from automatizador.dominio.modelo import ConteudoDocumento, Linha

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
    ordem INTEGER NOT NULL
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

    def registrar_documento(self, execucao_id: int, conteudo: ConteudoDocumento) -> DocumentoRegistrado:
        with self._conexao:
            cursor = self._conexao.execute(
                "INSERT INTO documento (execucao_id, nome, caminho, hash_sha256, paginas, importado_em)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (
                    execucao_id,
                    conteudo.caminho.name,
                    str(conteudo.caminho),
                    conteudo.hash_sha256,
                    len(conteudo.paginas),
                    _agora(),
                ),
            )
        return DocumentoRegistrado(cursor.lastrowid, conteudo.caminho.name)

    def registrar_linhas(self, documento_id: int, linhas: list[Linha]) -> None:
        agora = _agora()
        with self._conexao:
            for linha in linhas:
                linha_id = self._conexao.execute(
                    "INSERT INTO linha (documento_id, ordem) VALUES (?, ?)", (documento_id, linha.ordem)
                ).lastrowid
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
            " WHERE l.documento_id = ? ORDER BY l.ordem, v.id",
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
