"""Entidades do domínio.

Nenhum valor existe sozinho: cada valor de campo carrega a origem, a evidência
(trecho e página do documento) e, quando não pode ser confirmado, o motivo da pendência.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path


class Origem(StrEnum):
    SUGERIDO_IA = "sugerido_ia"
    DERIVADO_REGRA = "derivado_regra"
    MANUAL = "manual"
    AUSENTE = "ausente"


PENDENCIA_AUSENTE = "não encontrado no documento"
PENDENCIA_SEM_TRECHO = "sem trecho comprobatório"
PENDENCIA_TRECHO_NAO_ENCONTRADO = "trecho não encontrado no documento"
PENDENCIA_VALOR_FORA_DO_TRECHO = "valor não aparece no trecho citado"


@dataclass(frozen=True)
class Pagina:
    numero: int
    texto: str


@dataclass(frozen=True)
class ConteudoDocumento:
    caminho: Path
    hash_sha256: str
    paginas: list[Pagina]

    def pagina(self, numero: int) -> Pagina | None:
        return next((p for p in self.paginas if p.numero == numero), None)


@dataclass(frozen=True)
class CampoSugerido:
    """Um valor como a IA o sugeriu, antes de qualquer conferência."""

    valor: str | None
    trecho: str | None
    pagina: int | None
    confianca: float


@dataclass
class ValorCampo:
    coluna: str
    valor: str | None
    origem: Origem
    trecho: str | None = None
    pagina: int | None = None
    confianca: float | None = None
    pendencia: str | None = None

    @property
    def confirmado(self) -> bool:
        return self.valor is not None and self.pendencia is None

    @property
    def valor_para_exportar(self) -> str | None:
        """Valores pendentes saem vazios: nunca exportamos um palpite."""
        return self.valor if self.confirmado else None


@dataclass
class Linha:
    ordem: int
    valores: dict[str, ValorCampo] = field(default_factory=dict)
    pendencias: list[str] = field(default_factory=list)
    problemas_documento: list[str] = field(default_factory=list)
    id: int | None = None
    aprovada: bool = False

    @property
    def pendente(self) -> bool:
        """Falta algo obrigatório ou o documento tem problema: a linha precisa de revisão."""
        return bool(self.pendencias)


def _normalizar(texto: str) -> str:
    return re.sub(r"\s+", " ", texto).strip().casefold()


def _valor_aparece_no_trecho(valor: str, trecho: str) -> bool:
    """O valor precisa aparecer inteiro: "1,40" não conta como presente em "1.850,40"."""
    padrao = r"(?<!\w)(?<!\d[.,/-])" + re.escape(_normalizar(valor)) + r"(?!\w)(?![.,/-]\d)"
    return re.search(padrao, _normalizar(trecho)) is not None


def conferir_campo(coluna: str, sugerido: CampoSugerido | None, conteudo: ConteudoDocumento) -> ValorCampo:
    """Transforma uma sugestão da IA em valor de campo, conferindo a evidência no documento.

    Um valor só fica sem pendência quando o trecho citado existe na página indicada
    e o próprio valor aparece dentro desse trecho.
    """
    if sugerido is None or sugerido.valor is None or not sugerido.valor.strip():
        return ValorCampo(coluna, None, Origem.AUSENTE, pendencia=PENDENCIA_AUSENTE)

    valor = ValorCampo(
        coluna,
        sugerido.valor,
        Origem.SUGERIDO_IA,
        trecho=sugerido.trecho,
        pagina=sugerido.pagina,
        confianca=sugerido.confianca,
    )
    if not sugerido.trecho or sugerido.pagina is None:
        valor.pendencia = PENDENCIA_SEM_TRECHO
        return valor

    pagina = conteudo.pagina(sugerido.pagina)
    if pagina is None or _normalizar(sugerido.trecho) not in _normalizar(pagina.texto):
        valor.pendencia = PENDENCIA_TRECHO_NAO_ENCONTRADO
    elif not _valor_aparece_no_trecho(sugerido.valor, sugerido.trecho):
        valor.pendencia = PENDENCIA_VALOR_FORA_DO_TRECHO
    return valor


# Marca no texto do documento -> como o tipo é escrito na planilha de controle.
TIPOS_DE_NOTA = [
    ("Conhecimento de Transporte", "CT-e"),
    ("NFS-e", "Nota Fiscal"),
]


def derivar_tipo_de_nota(coluna: str, conteudo: ConteudoDocumento) -> ValorCampo | None:
    """TIPO DE NOTA vem de regra, não da IA: procura a marca do tipo de documento no texto."""
    for pagina in conteudo.paginas:
        texto = _normalizar(pagina.texto)
        for marca, tipo in TIPOS_DE_NOTA:
            if _normalizar(marca) in texto:
                return ValorCampo(coluna, tipo, Origem.DERIVADO_REGRA, trecho=marca, pagina=pagina.numero)
    return None
