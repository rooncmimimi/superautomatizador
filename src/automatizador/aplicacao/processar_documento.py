"""Caso de uso: ler documentos, pedir as linhas à IA, conferir a evidência, revisar e exportar."""

from __future__ import annotations

import getpass
from contextlib import contextmanager
from dataclasses import dataclass, field, replace
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
    PENDENCIA_AUSENTE,
    Linha,
    Origem,
    ValorCampo,
    conferir_campo,
    derivar_tipo_de_nota,
)
from automatizador.dominio.validacoes import validar_documento, validar_linha

COLUNA_TIPO_DE_NOTA = "TIPO DE NOTA"


def montar_linhas(
    sugestoes: list[dict[str, CampoSugerido]], conteudo: ConteudoDocumento, colunas: list[str]
) -> list[Linha]:
    """Confere cada sugestão da IA contra o documento, aplica as regras (TIPO DE NOTA) e valida."""
    tipo_de_nota = derivar_tipo_de_nota(COLUNA_TIPO_DE_NOTA, conteudo)
    problemas_do_documento = validar_documento(conteudo)
    linhas = []
    for ordem, sugestao in enumerate(sugestoes, start=1):
        linha = Linha(ordem)
        for coluna in colunas:
            linha.valores[coluna] = conferir_campo(coluna, sugestao.get(coluna), conteudo)
        if tipo_de_nota and COLUNA_TIPO_DE_NOTA in linha.valores:
            linha.valores[COLUNA_TIPO_DE_NOTA] = replace(tipo_de_nota)
        validar_linha(linha, problemas_do_documento)
        linhas.append(linha)
    return linhas


@dataclass
class ErroDocumento:
    arquivo: str
    mensagem: str


@dataclass
class ResultadoProcessamento:
    """Um lote: os documentos lidos e as linhas propostas, que o usuário revisa antes de exportar."""

    documentos: list[DocumentoRegistrado] = field(default_factory=list)
    linhas: list[tuple[str, Linha]] = field(default_factory=list)
    erros: list[ErroDocumento] = field(default_factory=list)
    destino: Path | None = None
    execucao: int | None = None
    # id da linha -> PDF de onde ela veio (dois PDFs podem ter o mesmo nome em pastas diferentes)
    caminhos: dict[int, Path] = field(default_factory=dict)

    @property
    def aprovadas(self) -> list[tuple[str, Linha]]:
        return [(nome, linha) for nome, linha in self.linhas if linha.aprovada]

    def caminho_da_linha(self, linha: Linha) -> Path | None:
        return self.caminhos.get(linha.id)


SITUACAO_EM_REVISAO = "aguardando_revisao"


class ProcessarDocumentos:
    """Ler documentos, revisar (corrigir e aprovar) e exportar só as linhas aprovadas."""

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

    def ler(self, arquivos: list[Path]) -> ResultadoProcessamento:
        """Lê os documentos e propõe as linhas; nada é exportado aqui."""
        lote = ResultadoProcessamento()
        lote.execucao = self._repositorio.iniciar_execucao(f"processar {len(arquivos)} documento(s)")
        with self._finalizando_em_caso_de_erro(lote):
            for arquivo in arquivos:
                try:
                    self._processar_um(lote, Path(arquivo))
                except (RespostaInvalida, ErroServicoIA, OSError, ValueError) as erro:
                    lote.erros.append(ErroDocumento(Path(arquivo).name, str(erro)))
        if lote.linhas:
            erro = f"{len(lote.erros)} erro(s)" if lote.erros else None
            self._repositorio.finalizar_execucao(lote.execucao, SITUACAO_EM_REVISAO, erro)
        else:
            self._repositorio.finalizar_execucao(lote.execucao, "falhou", f"{len(lote.erros)} erro(s)")
        return lote

    def corrigir(self, linha: Linha, coluna: str, novo_valor: str | None, usuario: str) -> ValorCampo:
        """Troca um valor pelo informado pelo usuário, registrando nova versão com usuário e data.

        A linha volta a precisar de aprovação, e as validações rodam de novo sobre o valor corrigido.
        A linha só muda depois de a correção ficar gravada no histórico.
        """
        novo_valor = (novo_valor or "").strip() or None
        valor = ValorCampo(
            coluna, novo_valor, Origem.MANUAL, pendencia=None if novo_valor else PENDENCIA_AUSENTE
        )
        corrigida = replace(linha, valores={c: replace(v) for c, v in linha.valores.items()})
        corrigida.valores[coluna] = valor
        validar_linha(corrigida, linha.problemas_documento)

        self._repositorio.registrar_correcao(linha.id, valor, usuario)
        if linha.aprovada:
            self._repositorio.cancelar_aprovacao(linha.id)
        linha.valores = corrigida.valores
        linha.pendencias = corrigida.pendencias
        linha.aprovada = False
        return valor

    def aprovar(self, linhas: list[Linha], usuario: str) -> None:
        for linha in linhas:
            self._repositorio.registrar_aprovacao(linha.id, usuario)
            linha.aprovada = True

    def exportar(self, lote: ResultadoProcessamento, destino: Path, substituir: bool = False) -> ResultadoProcessamento:
        """Grava numa planilha nova só as linhas aprovadas. Nunca sobrescreve sem substituir=True."""
        destino = Path(destino)
        with self._finalizando_em_caso_de_erro(lote):
            aprovadas = lote.aprovadas
            if not aprovadas:
                lote.erros.append(ErroDocumento(destino.name, "nenhuma linha aprovada para exportar"))
            elif destino.exists() and not substituir:
                lote.erros.append(ErroDocumento(destino.name, "a planilha de destino já existe"))
            else:
                try:
                    self._exportador.exportar(aprovadas, self._colunas, destino)
                except OSError as erro:
                    lote.erros.append(ErroDocumento(destino.name, f"não foi possível gravar a planilha: {erro}"))
                else:
                    self._repositorio.registrar_exportacao(lote.execucao, destino, len(aprovadas))
                    lote.destino = destino

        if not lote.erros:
            situacao, erro = "concluida", None
        elif lote.destino:
            situacao, erro = "concluida_com_erros", f"{len(lote.erros)} erro(s)"
        else:
            situacao, erro = "falhou", f"{len(lote.erros)} erro(s)"
        self._repositorio.finalizar_execucao(lote.execucao, situacao, erro)
        return lote

    def executar(
        self, arquivos: list[Path], destino: Path, substituir: bool = False, aprovar_todas: bool = False
    ) -> ResultadoProcessamento:
        """Ler e exportar de uma vez (linha de comando). Exporta só se o usuário aprovou todas."""
        destino = Path(destino)
        if aprovar_todas and destino.exists() and not substituir:
            lote = ResultadoProcessamento()
            lote.execucao = self._repositorio.iniciar_execucao(f"processar {len(arquivos)} documento(s)")
            lote.erros.append(ErroDocumento(destino.name, "a planilha de destino já existe"))
            self._repositorio.finalizar_execucao(lote.execucao, "falhou", "1 erro(s)")
            return lote
        lote = self.ler(arquivos)
        if not lote.linhas or not aprovar_todas:
            return lote
        self.aprovar([linha for _, linha in lote.linhas], usuario_atual())
        return self.exportar(lote, destino, substituir)

    def fechar(self) -> None:
        self._repositorio.fechar()
        fechar_assistente = getattr(self._assistente, "fechar", None)
        if fechar_assistente:
            fechar_assistente()

    @contextmanager
    def _finalizando_em_caso_de_erro(self, lote: ResultadoProcessamento):
        """Erro inesperado: a execução fica registrada como falha antes de o erro seguir adiante."""
        try:
            yield
        except Exception as erro:
            self._repositorio.finalizar_execucao(lote.execucao, "falhou", f"erro inesperado: {erro}")
            raise

    def _processar_um(self, lote: ResultadoProcessamento, arquivo: Path) -> None:
        conteudo = self._leitor.ler(arquivo)
        sugestoes = self._assistente.extrair_linhas(conteudo, self._colunas)
        if not sugestoes:
            raise RespostaInvalida("a IA não devolveu nenhuma linha para o documento")

        linhas = montar_linhas(sugestoes, conteudo, self._colunas)
        documento = self._repositorio.registrar_documento(lote.execucao, conteudo, linhas)
        lote.documentos.append(documento)
        lote.caminhos.update((linha.id, conteudo.caminho) for linha in linhas)
        lote.linhas.extend((documento.nome, linha) for linha in linhas)


def usuario_atual() -> str:
    """Usuário do Windows (ou do sistema) que está usando o aplicativo."""
    try:
        return getpass.getuser()
    except (OSError, KeyError):
        return "desconhecido"
