"""Caso de uso: ler documentos, pedir as linhas à IA, conferir a evidência, gravar e exportar."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from automatizador.aplicacao.portas import (
    AssistenteIA,
    DocumentoRegistrado,
    Exportador,
    LeitorDocumento,
    Repositorio,
    RespostaInvalida,
)
from automatizador.dominio.colunas import COLUNAS_CONTROLE
from automatizador.dominio.modelo import Linha, conferir_campo


@dataclass
class ErroDocumento:
    arquivo: str
    mensagem: str


@dataclass
class ResultadoProcessamento:
    documentos: list[DocumentoRegistrado] = field(default_factory=list)
    linhas: list[tuple[str, Linha]] = field(default_factory=list)
    erros: list[ErroDocumento] = field(default_factory=list)
    destino: Path | None = None


class ProcessarDocumentos:
    def __init__(
        self,
        leitor: LeitorDocumento,
        assistente: AssistenteIA,
        repositorio: Repositorio,
        exportador: Exportador,
        colunas: list[str] | None = None,
    ):
        self._leitor = leitor
        self._assistente = assistente
        self._repositorio = repositorio
        self._exportador = exportador
        self._colunas = colunas or COLUNAS_CONTROLE

    def executar(self, arquivos: list[Path], destino: Path) -> ResultadoProcessamento:
        resultado = ResultadoProcessamento()
        execucao = self._repositorio.iniciar_execucao(f"processar {len(arquivos)} documento(s)")

        for arquivo in arquivos:
            try:
                self._processar_um(execucao, Path(arquivo), resultado)
            except (RespostaInvalida, OSError, ValueError) as erro:
                resultado.erros.append(ErroDocumento(Path(arquivo).name, str(erro)))

        if resultado.linhas:
            self._exportador.exportar(resultado.linhas, self._colunas, destino)
            self._repositorio.registrar_exportacao(execucao, destino, len(resultado.linhas))
            resultado.destino = destino

        if not resultado.erros:
            situacao, erro = "concluida", None
        elif resultado.linhas:
            situacao, erro = "concluida_com_erros", f"{len(resultado.erros)} documento(s) com erro"
        else:
            situacao, erro = "falhou", f"{len(resultado.erros)} documento(s) com erro"
        self._repositorio.finalizar_execucao(execucao, situacao, erro)
        return resultado

    def _processar_um(self, execucao: int, arquivo: Path, resultado: ResultadoProcessamento) -> None:
        conteudo = self._leitor.ler(arquivo)
        sugestoes = self._assistente.extrair_linhas(conteudo, self._colunas)

        linhas = []
        for ordem, sugestao in enumerate(sugestoes, start=1):
            linha = Linha(ordem)
            for coluna in self._colunas:
                linha.valores[coluna] = conferir_campo(coluna, sugestao.get(coluna), conteudo)
            linhas.append(linha)

        documento = self._repositorio.registrar_documento(execucao, conteudo)
        self._repositorio.registrar_linhas(documento.id, linhas)
        resultado.documentos.append(documento)
        resultado.linhas.extend((documento.nome, linha) for linha in linhas)
