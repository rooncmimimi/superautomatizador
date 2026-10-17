"""Testes de fumaça da linha de comando e da janela."""

from openpyxl import load_workbook

from automatizador.cli import main
from automatizador.configuracao import criar_processador
from automatizador.interface.janela import COR_PENDENTE, JanelaPrincipal


def test_linha_de_comando_gera_ficticio_e_processa(tmp_path):
    pasta = tmp_path / "docs"
    saida = tmp_path / "controle.xlsx"

    assert main(["gerar-ficticios", str(pasta)]) == 0
    codigo = main(
        ["processar", str(pasta / "cte_1234.pdf"), "--saida", str(saida), "--banco", str(tmp_path / "a.db"),
         "--aprovar-todas"]
    )

    assert codigo == 0
    assert load_workbook(saida)["Controle"].max_row == 2


def test_linha_de_comando_sem_aprovacao_nao_grava_planilha(tmp_path, capsys):
    pasta = tmp_path / "docs"
    saida = tmp_path / "controle.xlsx"
    main(["gerar-ficticios", str(pasta)])

    codigo = main(
        ["processar", str(pasta / "cte_1234.pdf"), "--saida", str(saida), "--banco", str(tmp_path / "a.db")]
    )

    assert codigo == 0
    assert not saida.exists()
    assert "--aprovar-todas" in capsys.readouterr().out


def test_so_ler_nao_reclama_de_planilha_existente(tmp_path, capsys):
    pasta = tmp_path / "docs"
    saida = tmp_path / "controle.xlsx"
    saida.write_bytes(b"planilha anterior")
    main(["gerar-ficticios", str(pasta)])

    codigo = main(
        ["processar", str(pasta / "cte_1234.pdf"), "--saida", str(saida), "--banco", str(tmp_path / "a.db")]
    )

    assert codigo == 0
    assert saida.read_bytes() == b"planilha anterior"


def test_linha_de_comando_falha_quando_nada_pode_ser_lido(tmp_path):
    invalido = tmp_path / "quebrado.pdf"
    invalido.write_bytes(b"isto nao e um pdf")

    codigo = main(
        ["processar", str(invalido), "--saida", str(tmp_path / "x.xlsx"), "--banco", str(tmp_path / "a.db")]
    )

    assert codigo == 1
    assert not (tmp_path / "x.xlsx").exists()


def _janela(qtbot, tmp_path, renderizador=None):
    janela = JanelaPrincipal(criar_processador(banco=tmp_path / "a.db"), renderizador=renderizador, usuario="ana")
    qtbot.addWidget(janela)
    return janela


def _coluna(janela, nome):
    cabecalhos = [janela.tabela.horizontalHeaderItem(i).text() for i in range(janela.tabela.columnCount())]
    return cabecalhos.index(nome)


def test_janela_mostra_linhas_e_destaca_pendentes(qtbot, tmp_path, cte_ficticio):
    janela = _janela(qtbot, tmp_path)

    janela.definir_arquivos([cte_ficticio.pdf])
    janela.ler()

    assert janela.tabela.rowCount() == 1
    fornecedor = janela.tabela.item(0, _coluna(janela, "FORNECEDOR"))
    codigo = janela.tabela.item(0, _coluna(janela, "CÓDIGO FORNECEDOR"))
    assert fornecedor.text() == "Transportadora Exemplo Ltda"
    assert codigo.text() == ""
    assert codigo.background().color() == COR_PENDENTE


def test_janela_corrige_aprova_e_exporta_so_as_aprovadas(qtbot, tmp_path, cte_ficticio, nfse_ficticia):
    janela = _janela(qtbot, tmp_path)
    janela.definir_arquivos([cte_ficticio.pdf, nfse_ficticia.pdf])
    lote = janela.ler()
    saida = tmp_path / "controle.xlsx"

    janela.tabela.item(0, _coluna(janela, "CÓDIGO FORNECEDOR")).setText("3100289")
    janela.tabela.setCurrentCell(0, _coluna(janela, "CT-e"))
    janela.aprovar_selecionadas()
    janela.exportar(saida)

    planilha = load_workbook(saida)["Controle"]
    assert planilha.max_row == 2
    assert planilha.cell(row=2, column=1).value == "1234"
    assert planilha.cell(row=2, column=5).value == "3100289"
    assert lote.linhas[0][1].valores["CÓDIGO FORNECEDOR"].origem == "manual"
    assert janela.tabela.item(0, _coluna(janela, "APROVADA")).text() == "✔"
    assert janela.tabela.item(1, _coluna(janela, "APROVADA")).text() == ""


def test_lote_de_20_documentos_revisado_com_a_pagina_dentro_do_aplicativo(qtbot, tmp_path):
    from automatizador.adaptadores.imagem_pagina import renderizar_pagina

    pasta = tmp_path / "docs"
    main(["gerar-ficticios", str(pasta), "--quantidade", "10"])
    janela = _janela(qtbot, tmp_path, renderizador=renderizar_pagina)
    janela.definir_arquivos(sorted(pasta.glob("*.pdf")))

    janela.ler()

    assert janela.tabela.rowCount() == 20
    for linha in range(20):
        janela.mostrar_detalhe(linha, _coluna(janela, "VALOR TOTAL"))
        assert not janela.imagem.pixmap().isNull()
        assert "Trecho (página 1)" in janela.detalhe.text()
    janela.aprovar_todas()
    janela.exportar(tmp_path / "lote.xlsx")
    assert load_workbook(tmp_path / "lote.xlsx")["Controle"].max_row == 21


def test_dica_da_celula_mostra_texto_do_documento_sem_interpretar_html(qtbot, tmp_path, cte_ficticio):
    janela = _janela(qtbot, tmp_path)
    janela.definir_arquivos([cte_ficticio.pdf])
    lote = janela.ler()
    lote.linhas[0][1].valores["FORNECEDOR"].trecho = "<b>Emitente</b>"

    janela.aprovar_todas()  # redesenha a linha

    dica = janela.tabela.item(0, _coluna(janela, "FORNECEDOR")).toolTip()
    assert "&lt;b&gt;Emitente&lt;/b&gt;" in dica


def test_correcao_que_falha_ao_gravar_avisa_e_volta_o_valor(qtbot, tmp_path, cte_ficticio, monkeypatch):
    import sqlite3

    from PySide6.QtWidgets import QMessageBox

    janela = _janela(qtbot, tmp_path)
    janela.definir_arquivos([cte_ficticio.pdf])
    janela.ler()
    avisos = []
    monkeypatch.setattr(QMessageBox, "critical", lambda *args: avisos.append(args[2]))

    def falha(*_):
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(janela._processador, "corrigir", falha)
    janela.tabela.item(0, _coluna(janela, "FORNECEDOR")).setText("Outro")

    assert janela.tabela.item(0, _coluna(janela, "FORNECEDOR")).text() == "Transportadora Exemplo Ltda"
    assert "database is locked" in avisos[0]


def test_pagina_que_nao_pode_ser_mostrada_limpa_a_imagem_anterior(qtbot, tmp_path, cte_ficticio):
    from automatizador.adaptadores.imagem_pagina import renderizar_pagina

    chamadas = []

    def renderizador(caminho, pagina, destaques):
        chamadas.append(caminho)
        if len(chamadas) > 1:
            raise RuntimeError("PDF corrompido")
        return renderizar_pagina(caminho, pagina, destaques)

    janela = _janela(qtbot, tmp_path, renderizador=renderizador)
    janela.definir_arquivos([cte_ficticio.pdf])
    janela.ler()
    janela.mostrar_detalhe(0, _coluna(janela, "VALOR TOTAL"))
    assert not janela.imagem.pixmap().isNull()

    janela.mostrar_detalhe(0, _coluna(janela, "FORNECEDOR"))

    assert janela.imagem.pixmap().isNull()
    assert "PDF corrompido" in janela.imagem.text()


def test_ler_outro_lote_limpa_o_painel_do_anterior(qtbot, tmp_path, cte_ficticio):
    from automatizador.adaptadores.imagem_pagina import renderizar_pagina

    janela = _janela(qtbot, tmp_path, renderizador=renderizar_pagina)
    janela.definir_arquivos([cte_ficticio.pdf])
    janela.ler()
    janela.mostrar_detalhe(0, _coluna(janela, "VALOR TOTAL"))

    janela.ler()

    assert janela.imagem.pixmap().isNull()
    assert "Trecho" not in janela.detalhe.text()


def test_reler_pede_confirmacao_quando_ha_linhas_aprovadas_nao_exportadas(qtbot, tmp_path, cte_ficticio, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    janela = _janela(qtbot, tmp_path)
    janela.definir_arquivos([cte_ficticio.pdf])
    lote = janela.ler()
    janela.aprovar_todas()
    perguntas = []
    monkeypatch.setattr(
        QMessageBox, "question", lambda *args, **kw: perguntas.append(args[2]) or QMessageBox.StandardButton.No
    )

    janela.botao_ler.click()

    assert perguntas
    assert janela._lote is lote
