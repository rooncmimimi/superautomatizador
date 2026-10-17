"""Gera CT-e e NFS-e fictícios em PDF com texto digital, o gabarito e a resposta simulada da IA.

Para cada documento `<nome>.pdf` são criados:
- `<nome>.gabarito.json`: os valores esperados na planilha, escritos a partir dos dados do gerador;
- `<nome>.resposta.json`: a resposta que uma IA perfeita daria, usada pela IA simulada.

TIPO DE NOTA não entra na resposta da IA: é derivado por regra a partir do tipo de documento.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from automatizador.adaptadores.ia_simulada import SUFIXO_RESPOSTA
from automatizador.dominio.colunas import COLUNAS_CONTROLE

SUFIXO_GABARITO = ".gabarito.json"


@dataclass(frozen=True)
class DocumentoFicticio:
    pdf: Path
    gabarito: Path
    resposta_simulada: Path


def _digito_cnpj(base: str) -> str:
    pesos = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2][-len(base):]
    resto = sum(int(d) * p for d, p in zip(base, pesos)) % 11
    return "0" if resto < 2 else str(11 - resto)


def cnpj_ficticio(raiz: str) -> str:
    """Monta um CNPJ com dígitos verificadores válidos a partir de 8 dígitos de raiz."""
    base = f"{raiz}0001"
    base += _digito_cnpj(base)
    base += _digito_cnpj(base)
    return f"{base[:2]}.{base[2:5]}.{base[5:8]}/{base[8:12]}-{base[12:]}"


def _digito_chave(chave43: str) -> str:
    pesos = [2, 3, 4, 5, 6, 7, 8, 9]
    soma = sum(int(d) * pesos[i % 8] for i, d in enumerate(reversed(chave43)))
    resto = soma % 11
    return "0" if resto < 2 else str(11 - resto)


def chave_acesso_cte(cnpj: str, numero: int, ano_mes: str, uf: str = "35", serie: int = 1) -> str:
    """Chave de 44 dígitos no leiaute do CT-e (modelo 57), com dígito verificador válido."""
    cnpj_digitos = "".join(c for c in cnpj if c.isdigit())
    chave43 = f"{uf}{ano_mes}{cnpj_digitos}57{serie:03d}{numero:09d}1{numero:08d}"
    return chave43 + _digito_chave(chave43)


def gerar_cte_ficticio(pasta: Path, numero: int = 1234) -> DocumentoFicticio:
    cnpj = cnpj_ficticio("12345678")
    chave = chave_acesso_cte(cnpj, numero, "2610")
    chave_formatada = " ".join(chave[i : i + 4] for i in range(0, 44, 4))

    linha_numero = f"CT-e nº {numero} - Série 1"
    linha_emitente = "Emitente: Transportadora Exemplo Ltda"
    linha_descricao = "Descrição do serviço: Frete de botijões P13 - Rota Campinas/Sorocaba"
    linha_valor = "Valor total da prestação: R$ 1.850,40"
    linha_emissao = "Data de emissão: 03/10/2026"
    linha_vencimento = "Vencimento: 02/11/2026"
    linhas_pdf = [
        "DACTE - Documento Auxiliar do Conhecimento de Transporte Eletrônico",
        "DOCUMENTO FICTÍCIO - SEM VALOR FISCAL",
        linha_numero,
        f"Chave de acesso: {chave_formatada}",
        linha_emitente,
        f"CNPJ do emitente: {cnpj}",
        "Tomador: Empresa Fictícia de Gás S.A.",
        linha_emissao,
        linha_descricao,
        linha_valor,
        linha_vencimento,
    ]
    campos = {
        "CT-e": (str(numero), linha_numero),
        "FORNECEDOR": ("Transportadora Exemplo Ltda", linha_emitente),
        "DESCRIÇÃO": ("Frete de botijões P13 - Rota Campinas/Sorocaba", linha_descricao),
        "VALOR TOTAL": ("1.850,40", linha_valor),
        "DATA DA NOTA": ("03/10/2026", linha_emissao),
        "DATA DO VENCIMENTO": ("02/11/2026", linha_vencimento),
    }
    return _gravar(Path(pasta), f"cte_{numero}", linhas_pdf, campos, tipo_de_nota="CT-e")


def gerar_nfse_ficticia(pasta: Path, numero: int = 5501) -> DocumentoFicticio:
    """NFS-e no leiaute do DANFSe nacional: rótulos numa linha e valores na linha de baixo.

    Pedido e vencimento vêm dentro do texto livre da descrição do serviço, como nas notas reais.
    VALOR TOTAL é o valor do serviço (antes das retenções), não o valor líquido.
    """
    cnpj = cnpj_ficticio("23456789")
    rotulo_numero = "NÚMERO DA NFS-E COMPETÊNCIA DA NFS-E DATA E HORA DA EMISSÃO DA NFS-E"
    valores_numero = f"{numero} 09/2026 17/09/2026 09:47:20"
    rotulo_nome = "NOME / NOME EMPRESARIAL MUNICÍPIO / SIGLA UF"
    valores_nome = "REQUALIFICADORA EXEMPLO LTDA CIDADE FICTICIA/SP"
    descricao = "Requalificação de Recipiente P-45 - Qtde 12 x Valor Unit. R$ 95,00 = Total R$ 1.140,00."
    linha_pedido = "Pedido: 4500012345 10 Vencimento: 15/01/2027"
    rotulo_valor = "VALOR DA OPERAÇÃO / SERVIÇO DESCONTO CONDICIONADO DESCONTO INCONDICIONADO"
    valores_valor = "1.140,00 0,00 0,00"
    linhas_pdf = [
        "DANFSe v2.0 - Documento Auxiliar da NFS-e",
        "DOCUMENTO FICTÍCIO - SEM VALOR FISCAL",
        rotulo_numero,
        valores_numero,
        "PRESTADOR",
        f"CNPJ: {cnpj}",
        rotulo_nome,
        valores_nome,
        "TOMADOR / ADQUIRENTE",
        "EMPRESA FICTÍCIA DE GÁS S.A.",
        "DESCRIÇÃO DO SERVIÇO",
        descricao,
        linha_pedido,
        "VALOR TOTAL DA NFS-E",
        rotulo_valor,
        valores_valor,
        "TOTAL DAS RETENÇÕES (ISSQN / FEDERAIS) VALOR LÍQUIDO DA NFS-E",
        "53,01 1.086,99",
    ]
    campos = {
        "CT-e": (str(numero), f"{rotulo_numero} {valores_numero}"),
        "FORNECEDOR": ("REQUALIFICADORA EXEMPLO LTDA", f"{rotulo_nome} {valores_nome}"),
        "DESCRIÇÃO": (descricao, descricao),
        "VALOR TOTAL": ("1.140,00", f"{rotulo_valor} {valores_valor}"),
        "PEDIDO": ("4500012345", linha_pedido),
        "DATA DA NOTA": ("17/09/2026", f"{rotulo_numero} {valores_numero}"),
        "DATA DO VENCIMENTO": ("15/01/2027", linha_pedido),
    }
    return _gravar(Path(pasta), f"nfse_{numero}", linhas_pdf, campos, tipo_de_nota="Nota fiscal")


def _gravar(
    pasta: Path, nome: str, linhas_pdf: list[str], campos: dict[str, tuple[str, str]], tipo_de_nota: str
) -> DocumentoFicticio:
    """Grava o PDF, o gabarito e a resposta simulada. `campos`: coluna -> (valor, trecho que o comprova)."""
    pasta.mkdir(parents=True, exist_ok=True)
    pdf = pasta / f"{nome}.pdf"
    folha = canvas.Canvas(str(pdf), pagesize=A4)
    y = A4[1] - 60
    for texto in linhas_pdf:
        folha.drawString(50, y, texto)
        y -= 22
    folha.showPage()
    folha.save()

    esperados = {coluna: valor for coluna, (valor, _) in campos.items()} | {"TIPO DE NOTA": tipo_de_nota}
    gabarito = {"linhas": [{coluna: esperados.get(coluna) for coluna in COLUNAS_CONTROLE}]}
    resposta = {
        "linhas": [
            {
                "campos": {
                    coluna: (
                        {"valor": campos[coluna][0], "trecho": campos[coluna][1], "pagina": 1, "confianca": 0.95}
                        if coluna in campos
                        else {"valor": None, "trecho": None, "pagina": None, "confianca": 0.0}
                    )
                    for coluna in COLUNAS_CONTROLE
                }
            }
        ]
    }

    arquivo_gabarito = pasta / f"{nome}{SUFIXO_GABARITO}"
    arquivo_resposta = pasta / f"{nome}{SUFIXO_RESPOSTA}"
    arquivo_gabarito.write_text(json.dumps(gabarito, ensure_ascii=False, indent=2), encoding="utf-8")
    arquivo_resposta.write_text(json.dumps(resposta, ensure_ascii=False, indent=2), encoding="utf-8")
    return DocumentoFicticio(pdf, arquivo_gabarito, arquivo_resposta)
