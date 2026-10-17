"""O exportador nunca grava texto vindo de documento como fórmula."""

from openpyxl import load_workbook

from automatizador.adaptadores.exportador_xlsx import ExportadorXlsx
from automatizador.dominio.modelo import Linha, Origem, ValorCampo


def test_texto_que_parece_formula_e_gravado_como_texto(tmp_path):
    perigoso = '=HYPERLINK("http://exemplo.invalido","clique")'
    linha = Linha(1, {"DESCRIÇÃO": ValorCampo("DESCRIÇÃO", perigoso, Origem.SUGERIDO_IA, trecho=perigoso, pagina=1)})
    saida = tmp_path / "saida.xlsx"

    ExportadorXlsx().exportar([("doc.pdf", linha)], ["DESCRIÇÃO"], saida)

    livro = load_workbook(saida)
    celula = livro["Controle"]["A2"]
    assert celula.value == perigoso
    assert celula.data_type == "s"
    for celula in livro["Rastreabilidade"][2]:
        assert celula.data_type != "f"
