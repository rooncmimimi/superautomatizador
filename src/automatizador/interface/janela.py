"""Janela principal: ler PDFs, revisar as linhas propostas (corrigir e aprovar) e exportar só as aprovadas."""

from __future__ import annotations

import sys
from collections.abc import Callable
from html import escape
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from automatizador.aplicacao.processar_documento import ProcessarDocumentos, ResultadoProcessamento, usuario_atual
from automatizador.configuracao import criar_processador

COR_PENDENTE = QColor("#FFF2CC")
COR_APROVADA = QColor("#E2F0D9")
COLUNA_APROVADA = "APROVADA"
COLUNA_DOCUMENTO = "DOCUMENTO"
COLUNAS_FIXAS = [COLUNA_APROVADA, COLUNA_DOCUMENTO]

# (caminho do PDF, página, textos a destacar em ordem de preferência) -> imagem PNG
Renderizador = Callable[[Path, int, list[str]], bytes]


class JanelaPrincipal(QMainWindow):
    def __init__(
        self,
        processador: ProcessarDocumentos,
        renderizador: Renderizador | None = None,
        usuario: str | None = None,
    ):
        super().__init__()
        self._processador = processador
        self._renderizador = renderizador
        self._usuario = usuario or usuario_atual()
        self._arquivos: list[Path] = []
        self._lote: ResultadoProcessamento | None = None
        self._colunas = processador.colunas
        self._atualizando = False
        self.setWindowTitle("Automatizador")
        self.resize(1300, 700)

        self.botao_adicionar = QPushButton("Adicionar PDFs…")
        self.botao_ler = QPushButton("Ler documentos")
        self.botao_aprovar = QPushButton("Aprovar linhas selecionadas")
        self.botao_aprovar_todas = QPushButton("Aprovar todas")
        self.botao_exportar = QPushButton("Exportar aprovadas…")
        for botao in (self.botao_ler, self.botao_aprovar, self.botao_aprovar_todas, self.botao_exportar):
            botao.setEnabled(False)
        self.rotulo_arquivos = QLabel("Nenhum arquivo selecionado")

        self.tabela = QTableWidget(0, len(COLUNAS_FIXAS) + len(self._colunas))
        self.tabela.setHorizontalHeaderLabels(COLUNAS_FIXAS + self._colunas)
        self.tabela.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectItems)

        self.detalhe = QLabel("Selecione uma célula para ver de onde veio o valor.")
        self.detalhe.setWordWrap(True)
        self.detalhe.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.imagem = QLabel()
        self.imagem.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        self._rolagem = rolagem = QScrollArea()
        rolagem.setWidget(self.imagem)
        rolagem.setWidgetResizable(True)
        lateral = QWidget()
        layout_lateral = QVBoxLayout(lateral)
        layout_lateral.addWidget(self.detalhe)
        layout_lateral.addWidget(rolagem, stretch=1)

        divisor = QSplitter()
        divisor.addWidget(self.tabela)
        divisor.addWidget(lateral)
        divisor.setSizes([850, 450])

        botoes = QHBoxLayout()
        for botao in (
            self.botao_adicionar,
            self.botao_ler,
            self.botao_aprovar,
            self.botao_aprovar_todas,
            self.botao_exportar,
        ):
            botoes.addWidget(botao)
        botoes.addStretch()
        layout = QVBoxLayout()
        layout.addLayout(botoes)
        layout.addWidget(self.rotulo_arquivos)
        layout.addWidget(divisor, stretch=1)
        central = QWidget()
        central.setLayout(layout)
        self.setCentralWidget(central)

        self.botao_adicionar.clicked.connect(self._escolher_arquivos)
        self.botao_ler.clicked.connect(self._ler_com_avisos)
        self.botao_aprovar.clicked.connect(self.aprovar_selecionadas)
        self.botao_aprovar_todas.clicked.connect(self.aprovar_todas)
        self.botao_exportar.clicked.connect(self._escolher_destino_e_exportar)
        self.tabela.itemChanged.connect(self._ao_editar)
        self.tabela.currentCellChanged.connect(lambda linha, coluna, *_: self.mostrar_detalhe(linha, coluna))

    # Ações (chamadas pelos botões e pelos testes)

    def definir_arquivos(self, arquivos: list[Path]) -> None:
        self._arquivos = [Path(a) for a in arquivos]
        self.rotulo_arquivos.setText(f"{len(self._arquivos)} arquivo(s) selecionado(s)")
        self.botao_ler.setEnabled(bool(self._arquivos))

    def ler(self) -> ResultadoProcessamento:
        # Por enquanto roda na própria janela; com documentos maiores passa para segundo plano.
        self._lote = self._processador.ler(self._arquivos)
        self._mostrar_tudo()
        tem_linhas = bool(self._lote.linhas)
        self.botao_aprovar.setEnabled(tem_linhas)
        self.botao_aprovar_todas.setEnabled(tem_linhas)
        self.botao_exportar.setEnabled(tem_linhas)
        return self._lote

    def aprovar_selecionadas(self) -> None:
        indices = sorted({item.row() for item in self.tabela.selectedItems()})
        self._aprovar(indices)

    def aprovar_todas(self) -> None:
        if self._lote:
            self._aprovar(list(range(len(self._lote.linhas))))

    def exportar(self, destino: Path, substituir: bool = False) -> ResultadoProcessamento:
        erros_antes = len(self._lote.erros)
        self._processador.exportar(self._lote, destino, substituir=substituir)
        novos_erros = self._lote.erros[erros_antes:]
        if novos_erros:
            self.statusBar().showMessage("; ".join(e.mensagem for e in novos_erros))
        else:
            self.statusBar().showMessage(f"{len(self._lote.aprovadas)} linha(s) gravada(s) em {destino}")
        return self._lote

    def mostrar_detalhe(self, indice_linha: int, indice_coluna: int) -> None:
        if not self._lote or indice_linha < 0 or indice_coluna < len(COLUNAS_FIXAS):
            return
        documento, linha = self._lote.linhas[indice_linha]
        coluna = self._colunas[indice_coluna - len(COLUNAS_FIXAS)]
        valor = linha.valores[coluna]
        # Texto vindo do documento é escapado: o rótulo interpreta HTML.
        partes = [f"<b>{escape(coluna)}</b> — origem: {valor.origem}"]
        if valor.trecho:
            partes.append(f"Trecho (página {valor.pagina}): “{escape(valor.trecho)}”")
        if valor.pendencia:
            partes.append(f"<span style='color:#B45F06'>Pendência: {escape(valor.pendencia)}</span>")
        if linha.pendencias:
            partes.append("Linha precisa de revisão: " + escape("; ".join(linha.pendencias)))
        self.detalhe.setText("<br>".join(partes))
        destaques = [valor.trecho, valor.valor] if valor.trecho else []
        self._mostrar_pagina(self._lote.caminhos.get(documento), valor.pagina or 1, destaques)

    def closeEvent(self, evento) -> None:
        self._processador.fechar()
        super().closeEvent(evento)

    # Internos

    def _aprovar(self, indices: list[int]) -> None:
        if not self._lote or not indices:
            return
        self._processador.aprovar([self._lote.linhas[i][1] for i in indices], self._usuario)
        for indice in indices:
            self._mostrar_linha(indice)
        self._atualizar_status()

    def _ao_editar(self, item: QTableWidgetItem) -> None:
        if self._atualizando or not self._lote or item.column() < len(COLUNAS_FIXAS):
            return
        indice_linha, indice_coluna, texto = item.row(), item.column(), item.text()
        _, linha = self._lote.linhas[indice_linha]
        coluna = self._colunas[indice_coluna - len(COLUNAS_FIXAS)]
        anterior = linha.valores[coluna].valor_para_exportar or ""
        if texto.strip() == anterior:
            return
        self._processador.corrigir(linha, coluna, texto, self._usuario)
        self._mostrar_linha(indice_linha)
        self._atualizar_status()
        self.mostrar_detalhe(indice_linha, indice_coluna)

    def _mostrar_tudo(self) -> None:
        self.tabela.setRowCount(len(self._lote.linhas))
        for indice in range(len(self._lote.linhas)):
            self._mostrar_linha(indice)
        self._atualizar_status()

    def _mostrar_linha(self, indice: int) -> None:
        documento, linha = self._lote.linhas[indice]
        fundo_fixo = QBrush(COR_APROVADA) if linha.aprovada else QBrush()
        self._atualizando = True
        try:
            self._preencher(indice, 0, "✔" if linha.aprovada else "", fundo_fixo, "", editavel=False)
            self._preencher(indice, 1, documento, fundo_fixo, "", editavel=False)
            for posicao, coluna in enumerate(self._colunas, start=len(COLUNAS_FIXAS)):
                valor = linha.valores[coluna]
                if not valor.confirmado:
                    fundo, dica = QBrush(COR_PENDENTE), valor.pendencia or ""
                else:
                    fundo, dica = QBrush(), f"página {valor.pagina}: {valor.trecho}" if valor.trecho else ""
                self._preencher(indice, posicao, valor.valor_para_exportar or "", fundo, dica)
            cabecalho = QTableWidgetItem("⚠" if linha.pendente else str(indice + 1))
            cabecalho.setToolTip("\n".join(linha.pendencias))
            self.tabela.setVerticalHeaderItem(indice, cabecalho)
        finally:
            self._atualizando = False

    def _preencher(
        self, linha: int, coluna: int, texto: str, fundo: QBrush, dica: str, editavel: bool = True
    ) -> None:
        """Atualiza a célula no lugar (sem recriar o item, que pode estar sendo editado)."""
        item = self.tabela.item(linha, coluna)
        if item is None:
            item = QTableWidgetItem()
            if not editavel:
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.tabela.setItem(linha, coluna, item)
        item.setText(texto)
        item.setBackground(fundo)
        item.setToolTip(dica)

    def _atualizar_status(self) -> None:
        total = len(self._lote.linhas)
        aprovadas = len(self._lote.aprovadas)
        pendentes = sum(1 for _, linha in self._lote.linhas if linha.pendente)
        mensagens = [f"{total} linha(s)", f"{aprovadas} aprovada(s)", f"{pendentes} precisando de revisão"]
        if self._lote.erros:
            mensagens.append(f"{len(self._lote.erros)} erro(s)")
        self.statusBar().showMessage("; ".join(mensagens))

    def _mostrar_pagina(self, caminho: Path | None, pagina: int, destaques: list[str]) -> None:
        if not self._renderizador or caminho is None:
            return
        try:
            png = self._renderizador(caminho, pagina, destaques)
        except (OSError, ValueError) as erro:
            self.imagem.setText(f"Não foi possível mostrar a página: {erro}")
            return
        imagem = QPixmap()
        imagem.loadFromData(png)
        largura = max(self._rolagem.viewport().width() - 10, 200)
        self.imagem.setPixmap(imagem.scaledToWidth(largura, Qt.TransformationMode.SmoothTransformation))

    def _escolher_arquivos(self) -> None:
        arquivos, _ = QFileDialog.getOpenFileNames(self, "Escolher documentos", "", "PDF (*.pdf)")
        if arquivos:
            self.definir_arquivos([Path(a) for a in arquivos])

    def _ler_com_avisos(self) -> None:
        try:
            lote = self.ler()
        except Exception as erro:
            QMessageBox.critical(self, "Erro ao ler", f"A leitura falhou: {erro}")
            return
        if lote.erros:
            detalhes = "\n".join(f"{e.arquivo}: {e.mensagem}" for e in lote.erros)
            QMessageBox.warning(self, "Documentos com erro", detalhes)

    def _escolher_destino_e_exportar(self) -> None:
        if not self._lote.aprovadas:
            QMessageBox.information(self, "Nada aprovado", "Aprove pelo menos uma linha antes de exportar.")
            return
        destino, _ = QFileDialog.getSaveFileName(self, "Salvar planilha", "controle.xlsx", "Excel (*.xlsx)")
        if not destino:
            return
        erros_antes = len(self._lote.erros)
        try:
            # O diálogo de salvar já pediu confirmação se o arquivo existia.
            self.exportar(Path(destino), substituir=True)
        except Exception as erro:
            QMessageBox.critical(self, "Erro ao exportar", f"A exportação falhou: {erro}")
            return
        novos_erros = self._lote.erros[erros_antes:]
        if novos_erros:
            QMessageBox.warning(self, "Erro ao exportar", "\n".join(e.mensagem for e in novos_erros))


def executar_janela(banco: Path | None = None) -> int:
    from automatizador.adaptadores.imagem_pagina import renderizar_pagina

    app = QApplication.instance() or QApplication(sys.argv)
    janela = JanelaPrincipal(criar_processador(banco=banco), renderizador=renderizar_pagina)
    janela.show()
    return app.exec()
