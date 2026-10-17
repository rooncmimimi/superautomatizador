"""Caso de uso: ler documentos, pedir as linhas à IA, conferir a evidência, gravar e exportar."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from automatizador.aplicacao.portas import (
    AssistenteIA,
    DocumentoRegistrado,
    ErroServicoIA,
    Exportador,
    LeitorDocumento,
    Repositorio,
    RespostaInvalida,
)
from automatizador.dominio.colunas import COLUNAS_CONTROLE
from automatizador.dominio.modelo import (
    CampoSugerido,
    ConteudoDocumento,
    Linha,
    conferir_campo,
    derivar_tipo_de_nota,
)

COLUNA_TIPO_DE_NOTA = "TIPO DE NOTA"


def montar_linhas(
    sugestoes: list[dict[str, CampoSugerido]], conteudo: ConteudoDocumento, colunas: list[str]
) -> list[Linha]:
    """Confere cada sugestão da IA contra o documento e aplica as regras (TIPO DE NOTA)."""
    tipo_de_nota = derivar_tipo_de_nota(COLUNA_TIPO_DE_NOTA, conteudo)
    linhas = []
    for ordem, sugestao in enumerate(sugestoes, start=1):
        linha = Linha(ordem)
        for coluna in colunas:
            linha.valores[coluna] = conferir_campo(coluna, sugestao.get(coluna), conteudo)
        if tipo_de_nota and COLUNA_TIPO_DE_NOTA in linha.valores:
            linha.valores[COLUNA_TIPO_DE_NOTA] = tipo_de_nota
        linhas.append(linha)
    return linhas


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

    @property
    def colunas(self) -> list[str]:
        return list(self._colunas)

    def executar(self, arquivos: list[Path], destino: Path, substituir: bool = False) -> ResultadoProcessamento:
        """Processa os arquivos e grava uma planilha nova em destino.

        Nunca sobrescreve uma planilha existente sem substituir=True, e a execução
        sempre fica registrada no histórico com o resultado final, mesmo em caso de falha.
        """
        destino = Path(destino)
        resultado = ResultadoProcessamento()
        execucao = self._repositorio.iniciar_execucao(f"processar {len(arquivos)} documento(s)")
        try:
            if destino.exists() and not substituir:
                resultado.erros.append(ErroDocumento(destino.name, "a planilha de destino já existe"))
            else:
                self._processar_todos(execucao, arquivos, destino, resultado)
        except Exception as erro:
            self._repositorio.finalizar_execucao(execucao, "falhou", f"erro inesperado: {erro}")
            raise

        if not resultado.erros:
            situacao, erro = "concluida", None
        elif resultado.destino:
            situacao, erro = "concluida_com_erros", f"{len(resultado.erros)} erro(s)"
        else:
            situacao, erro = "falhou", f"{len(resultado.erros)} erro(s)"
        self._repositorio.finalizar_execucao(execucao, situacao, erro)
        return resultado

    def fechar(self) -> None:
        self._repositorio.fechar()
        fechar_assistente = getattr(self._assistente, "fechar", None)
        if fechar_assistente:
            fechar_assistente()

    def _processar_todos(
        self, execucao: int, arquivos: list[Path], destino: Path, resultado: ResultadoProcessamento
    ) -> None:
        for arquivo in arquivos:
            try:
                self._processar_um(execucao, Path(arquivo), resultado)
            except (RespostaInvalida, ErroServicoIA, OSError, ValueError) as erro:
                resultado.erros.append(ErroDocumento(Path(arquivo).name, str(erro)))

        if not resultado.linhas:
            return
        try:
            self._exportador.exportar(resultado.linhas, self._colunas, destino)
        except OSError as erro:
            resultado.erros.append(ErroDocumento(destino.name, f"não foi possível gravar a planilha: {erro}"))
            return
        self._repositorio.registrar_exportacao(execucao, destino, len(resultado.linhas))
        resultado.destino = destino

    def _processar_um(self, execucao: int, arquivo: Path, resultado: ResultadoProcessamento) -> None:
        conteudo = self._leitor.ler(arquivo)
        sugestoes = self._assistente.extrair_linhas(conteudo, self._colunas)
        if not sugestoes:
            raise RespostaInvalida("a IA não devolveu nenhuma linha para o documento")

        linhas = montar_linhas(sugestoes, conteudo, self._colunas)
        documento = self._repositorio.registrar_documento(execucao, conteudo, linhas)
        resultado.documentos.append(documento)
        resultado.linhas.extend((documento.nome, linha) for linha in linhas)
