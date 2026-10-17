"""Caso de uso: medir a taxa de acerto de um serviço de IA contra os gabaritos dos documentos fictícios.

Não grava histórico nem planilha. Conta só as células em que o gabarito tem valor ou a IA
preencheu algo: células vazias dos dois lados não inflam a taxa.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from automatizador.aplicacao.portas import AssistenteIA, ErroServicoIA, LeitorDocumento, RespostaInvalida
from automatizador.aplicacao.processar_documento import ErroDocumento, montar_linhas
from automatizador.dominio.colunas import COLUNAS_CONTROLE


@dataclass(frozen=True)
class DocumentoComGabarito:
    pdf: Path
    linhas_esperadas: list[dict[str, str | None]]


@dataclass
class ResultadoAcerto:
    documentos: int = 0
    celulas: int = 0
    acertos: int = 0
    erros_por_coluna: Counter = field(default_factory=Counter)
    falhas: list[ErroDocumento] = field(default_factory=list)

    @property
    def taxa(self) -> float:
        return self.acertos / self.celulas if self.celulas else 0.0


class MedirAcerto:
    def __init__(self, leitor: LeitorDocumento, colunas: list[str] | None = None):
        self._leitor = leitor
        self._colunas = colunas or COLUNAS_CONTROLE

    def medir(self, assistente: AssistenteIA, documentos: list[DocumentoComGabarito]) -> ResultadoAcerto:
        resultado = ResultadoAcerto()
        for documento in documentos:
            resultado.documentos += 1
            try:
                conteudo = self._leitor.ler(documento.pdf)
                linhas = montar_linhas(assistente.extrair_linhas(conteudo, self._colunas), conteudo, self._colunas)
            except (RespostaInvalida, ErroServicoIA, OSError, ValueError) as erro:
                resultado.falhas.append(ErroDocumento(documento.pdf.name, str(erro)))
                linhas = []

            for indice, esperada in enumerate(documento.linhas_esperadas):
                obtida = linhas[indice].valores if indice < len(linhas) else {}
                for coluna in self._colunas:
                    valor_esperado = esperada.get(coluna)
                    valor_obtido = obtida[coluna].valor_para_exportar if coluna in obtida else None
                    if valor_esperado is None and valor_obtido is None:
                        continue
                    resultado.celulas += 1
                    if valor_obtido == valor_esperado:
                        resultado.acertos += 1
                    else:
                        resultado.erros_por_coluna[coluna] += 1
        return resultado
