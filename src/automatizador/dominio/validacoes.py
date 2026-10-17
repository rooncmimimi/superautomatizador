"""Validações determinísticas, independentes da IA.

Um valor reprovado continua visível na rastreabilidade, mas ganha uma pendência e
deixa de ser exportado. Uma linha com pendência em coluna obrigatória fica pendente.
"""

from __future__ import annotations

import re
from datetime import date, datetime

from automatizador.dominio.modelo import ConteudoDocumento, Linha

COLUNAS_OBRIGATORIAS = ["CT-e", "TIPO DE NOTA", "FORNECEDOR", "VALOR TOTAL", "DATA DA NOTA"]

PENDENCIA_VALOR_INVALIDO = "valor não está no formato 1.234,56"
PENDENCIA_DATA_INVALIDA = "data inválida (esperado dd/mm/aaaa)"
PENDENCIA_SO_DIGITOS = "deveria conter só números"
PENDENCIA_VENCIMENTO_ANTES = "vencimento anterior à data da nota"
PENDENCIA_CNPJ = "CNPJ com dígito verificador inválido no documento"
PENDENCIA_CHAVE = "chave de acesso com dígito verificador inválido no documento"

_VALOR = re.compile(r"\d{1,3}(\.\d{3})*,\d{2}")
_CNPJ = re.compile(r"\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b")
_CHAVE = re.compile(r"(?<!\d)(?:\d{4}\s?){10}\d{4}(?!\d)")


def _data(texto: str) -> date | None:
    try:
        return datetime.strptime(texto.strip(), "%d/%m/%Y").date()
    except ValueError:
        return None


def _so_digitos(texto: str) -> bool:
    return texto.strip().isdigit()


# coluna -> (teste do valor, motivo da pendência quando reprovado)
REGRAS_DE_FORMATO = {
    "CT-e": (_so_digitos, PENDENCIA_SO_DIGITOS),
    "PEDIDO": (_so_digitos, PENDENCIA_SO_DIGITOS),
    "VALOR TOTAL": (lambda v: _VALOR.fullmatch(v.strip()) is not None, PENDENCIA_VALOR_INVALIDO),
    "DATA DA NOTA": (lambda v: _data(v) is not None, PENDENCIA_DATA_INVALIDA),
    "DATA DO VENCIMENTO": (lambda v: _data(v) is not None, PENDENCIA_DATA_INVALIDA),
}


def cnpj_valido(cnpj: str) -> bool:
    digitos = [int(c) for c in cnpj if c.isdigit()]
    if len(digitos) != 14 or len(set(digitos)) == 1:
        return False
    for tamanho in (12, 13):
        pesos = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2][-tamanho:]
        resto = sum(d * p for d, p in zip(digitos, pesos)) % 11
        if digitos[tamanho] != (0 if resto < 2 else 11 - resto):
            return False
    return True


def chave_acesso_valida(chave: str) -> bool:
    digitos = [int(c) for c in chave if c.isdigit()]
    if len(digitos) != 44:
        return False
    pesos = [2, 3, 4, 5, 6, 7, 8, 9]
    soma = sum(d * pesos[i % 8] for i, d in enumerate(reversed(digitos[:43])))
    resto = soma % 11
    return digitos[43] == (0 if resto < 2 else 11 - resto)


def validar_documento(conteudo: ConteudoDocumento) -> list[str]:
    """Problemas do documento como um todo: CNPJs e chave de acesso com dígito inválido."""
    texto = "\n".join(p.texto for p in conteudo.paginas)
    problemas = []
    if any(not cnpj_valido(c) for c in _CNPJ.findall(texto)):
        problemas.append(PENDENCIA_CNPJ)
    if any(not chave_acesso_valida(c) for c in _CHAVE.findall(texto)):
        problemas.append(PENDENCIA_CHAVE)
    return problemas


def validar_linha(linha: Linha, problemas_do_documento: list[str]) -> None:
    """Marca pendências nos valores reprovados e registra os motivos da linha."""
    for coluna, (teste, motivo) in REGRAS_DE_FORMATO.items():
        valor = linha.valores.get(coluna)
        if valor and valor.confirmado and not teste(valor.valor):
            valor.pendencia = motivo

    nota, vencimento = linha.valores.get("DATA DA NOTA"), linha.valores.get("DATA DO VENCIMENTO")
    if nota and vencimento and nota.confirmado and vencimento.confirmado:
        if _data(vencimento.valor) < _data(nota.valor):
            vencimento.pendencia = PENDENCIA_VENCIMENTO_ANTES

    linha.pendencias = list(problemas_do_documento)
    for coluna in COLUNAS_OBRIGATORIAS:
        valor = linha.valores.get(coluna)
        if valor is not None and not valor.confirmado:
            linha.pendencias.append(f"{coluna}: {valor.pendencia}")
