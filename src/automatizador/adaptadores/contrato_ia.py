"""Contrato da resposta de extração que qualquer serviço de IA deve seguir.

Por documento: uma lista de linhas; por linha, para cada coluna, o valor (ou nulo),
o trecho do documento que o comprova, a página e a confiança declarada.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, ValidationError

from automatizador.aplicacao.portas import RespostaInvalida
from automatizador.dominio.modelo import CampoSugerido


class CampoExtraido(BaseModel):
    valor: str | None = None
    trecho: str | None = None
    pagina: int | None = Field(default=None, ge=1)
    confianca: float = Field(default=0.0, ge=0.0, le=1.0)


class LinhaExtraida(BaseModel):
    campos: dict[str, CampoExtraido]


class RespostaExtracao(BaseModel):
    linhas: list[LinhaExtraida]


def interpretar_resposta(texto_json: str, colunas: list[str]) -> list[dict[str, CampoSugerido]]:
    """Valida a resposta e devolve só as colunas pedidas; colunas desconhecidas são ignoradas."""
    try:
        resposta = RespostaExtracao.model_validate_json(texto_json)
    except ValidationError as erro:
        raise RespostaInvalida(f"resposta da IA fora do contrato: {erro.error_count()} erro(s)") from erro

    return [
        {
            coluna: CampoSugerido(campo.valor, campo.trecho, campo.pagina, campo.confianca)
            for coluna, campo in linha.campos.items()
            if coluna in colunas
        }
        for linha in resposta.linhas
    ]
