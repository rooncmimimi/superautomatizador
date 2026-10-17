"""Validações determinísticas: cada regra com caso válido e inválido."""

import json

import pytest

from automatizador.adaptadores.leitor_pdf import LeitorPdf
from automatizador.dominio.modelo import ConteudoDocumento, Linha, Origem, Pagina, ValorCampo
from automatizador.dominio.validacoes import (
    PENDENCIA_CHAVE,
    PENDENCIA_CNPJ,
    PENDENCIA_DATA_INVALIDA,
    PENDENCIA_SO_DIGITOS,
    PENDENCIA_VALOR_INVALIDO,
    PENDENCIA_VENCIMENTO_ANTES,
    chave_acesso_valida,
    cnpj_valido,
    validar_documento,
    validar_linha,
)
from automatizador.ficticios.gerador import chave_acesso_cte, cnpj_ficticio


def _linha(**valores):
    linha = Linha(1)
    for coluna, valor in valores.items():
        linha.valores[coluna] = ValorCampo(coluna, valor, Origem.SUGERIDO_IA, trecho=valor, pagina=1)
    return linha


def _linha_do_gabarito(ficticio):
    gabarito = json.loads(ficticio.gabarito.read_text(encoding="utf-8"))["linhas"][0]
    return _linha(**{c: v for c, v in gabarito.items() if v is not None})


def test_cnpj():
    valido = cnpj_ficticio("12345678")
    assert cnpj_valido(valido)
    assert not cnpj_valido(valido[:-1] + str((int(valido[-1]) + 1) % 10))
    assert not cnpj_valido("11.111.111/1111-11")


def test_chave_de_acesso():
    chave = chave_acesso_cte(cnpj_ficticio("12345678"), 1234, "2610")
    assert chave_acesso_valida(chave)
    assert not chave_acesso_valida(chave[:-1] + str((int(chave[-1]) + 1) % 10))
    assert not chave_acesso_valida(chave[:-1])


@pytest.mark.parametrize("nome", ["cte_ficticio", "nfse_ficticia"])
def test_valores_do_gabarito_passam_em_todas_as_regras(nome, request):
    ficticio = request.getfixturevalue(nome)
    linha = _linha_do_gabarito(ficticio)

    validar_linha(linha, validar_documento(LeitorPdf().ler(ficticio.pdf)))

    assert not linha.pendente
    assert all(v.confirmado for v in linha.valores.values())


@pytest.mark.parametrize(
    ("coluna", "valor", "motivo"),
    [
        ("VALOR TOTAL", "1850,4", PENDENCIA_VALOR_INVALIDO),
        ("VALOR TOTAL", "R$ 1.850,40", PENDENCIA_VALOR_INVALIDO),
        ("DATA DA NOTA", "31/02/2026", PENDENCIA_DATA_INVALIDA),
        ("DATA DO VENCIMENTO", "2026-11-02", PENDENCIA_DATA_INVALIDA),
        ("CT-e", "12A4", PENDENCIA_SO_DIGITOS),
        ("PEDIDO", "45000-123", PENDENCIA_SO_DIGITOS),
    ],
)
def test_valor_reprovado_fica_pendente_e_nao_e_exportado(cte_ficticio, coluna, valor, motivo):
    linha = _linha_do_gabarito(cte_ficticio)
    linha.valores[coluna] = ValorCampo(coluna, valor, Origem.SUGERIDO_IA, trecho=valor, pagina=1)

    validar_linha(linha, [])

    assert linha.valores[coluna].pendencia == motivo
    assert linha.valores[coluna].valor_para_exportar is None


def test_vencimento_antes_da_data_da_nota(cte_ficticio):
    linha = _linha_do_gabarito(cte_ficticio)
    linha.valores["DATA DO VENCIMENTO"].valor = "01/10/2026"

    validar_linha(linha, [])

    assert linha.valores["DATA DO VENCIMENTO"].pendencia == PENDENCIA_VENCIMENTO_ANTES


def test_falta_de_coluna_obrigatoria_deixa_a_linha_pendente(cte_ficticio):
    linha = _linha_do_gabarito(cte_ficticio)
    linha.valores["FORNECEDOR"] = ValorCampo("FORNECEDOR", None, Origem.AUSENTE, pendencia="não encontrado no documento")

    validar_linha(linha, [])

    assert linha.pendente
    assert linha.pendencias == ["FORNECEDOR: não encontrado no documento"]


def test_documento_com_cnpj_e_chave_invalidos(tmp_path):
    cnpj = cnpj_ficticio("12345678")
    chave = chave_acesso_cte(cnpj, 1234, "2610")
    texto = f"CNPJ: {cnpj[:-1]}0\nChave: {chave[:-1]}{(int(chave[-1]) + 1) % 10}"
    conteudo = ConteudoDocumento(tmp_path / "x.pdf", "h", [Pagina(1, texto)])

    assert validar_documento(conteudo) == [PENDENCIA_CNPJ, PENDENCIA_CHAVE]
