"""Gera DACTE (PDF de CT-e) fictícios com texto digital, o gabarito e a resposta simulada da IA.

Para cada documento `cte_<numero>.pdf` são criados:
- `cte_<numero>.gabarito.json`: os valores esperados na planilha, escritos a partir dos dados do gerador;
- `cte_<numero>.resposta.json`: a resposta que uma IA perfeita daria, usada pela IA simulada.
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
    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
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

    pdf = pasta / f"cte_{numero}.pdf"
    folha = canvas.Canvas(str(pdf), pagesize=A4)
    y = A4[1] - 60
    for texto in linhas_pdf:
        folha.drawString(50, y, texto)
        y -= 22
    folha.showPage()
    folha.save()

    # Cada campo: (valor esperado, linha do documento que o comprova)
    campos = {
        "CT-e": (str(numero), linha_numero),
        "TIPO DE NOTA": ("CT-e", linha_numero),
        "FORNECEDOR": ("Transportadora Exemplo Ltda", linha_emitente),
        "DESCRIÇÃO": ("Frete de botijões P13 - Rota Campinas/Sorocaba", linha_descricao),
        "VALOR TOTAL": ("1.850,40", linha_valor),
        "DATA DA NOTA": ("03/10/2026", linha_emissao),
        "DATA DO VENCIMENTO": ("02/11/2026", linha_vencimento),
    }

    gabarito = {"linhas": [{coluna: campos[coluna][0] if coluna in campos else None for coluna in COLUNAS_CONTROLE}]}
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

    arquivo_gabarito = pasta / f"cte_{numero}{SUFIXO_GABARITO}"
    arquivo_resposta = pasta / f"cte_{numero}{SUFIXO_RESPOSTA}"
    arquivo_gabarito.write_text(json.dumps(gabarito, ensure_ascii=False, indent=2), encoding="utf-8")
    arquivo_resposta.write_text(json.dumps(resposta, ensure_ascii=False, indent=2), encoding="utf-8")
    return DocumentoFicticio(pdf, arquivo_gabarito, arquivo_resposta)
