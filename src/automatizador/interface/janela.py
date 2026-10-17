"""Janela principal mínima: escolher PDFs, processar e ver as linhas geradas."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from automatizador.aplicacao.processar_documento import ProcessarDocumentos, ResultadoProcessamento
from automatizador.configuracao import criar_processador

COR_PENDENTE = QColor("#FFF2CC")


class JanelaPrincipal(QMainWindow):
    def __init__(self, processador: ProcessarDocumentos):
        super().__init__()
        self._processador = processador
        self._arquivos: list[Path] = []
        self.setWindowTitle("Automatizador")
        self.resize(1100, 600)

        self.botao_adicionar = QPushButton("Adicionar PDFs…")
        self.botao_processar = QPushButton("Processar e exportar…")
        self.botao_processar.setEnabled(False)
        self.rotulo_arquivos = QLabel("Nenhum arquivo selecionado")
        self._colunas = processador.colunas
        self.tabela = QTableWidget(0, len(self._colunas))
        self.tabela.setHorizontalHeaderLabels(self._colunas)

        botoes = QHBoxLayout()
        botoes.addWidget(self.botao_adicionar)
        botoes.addWidget(self.botao_processar)
        botoes.addStretch()
        layout = QVBoxLayout()
        layout.addLayout(botoes)
        layout.addWidget(self.rotulo_arquivos)
        layout.addWidget(self.tabela)
        central = QWidget()
        central.setLayout(layout)
        self.setCentralWidget(central)

        self.botao_adicionar.clicked.connect(self._escolher_arquivos)
        self.botao_processar.clicked.connect(self._escolher_destino_e_processar)

    def definir_arquivos(self, arquivos: list[Path]) -> None:
        self._arquivos = [Path(a) for a in arquivos]
        self.rotulo_arquivos.setText(f"{len(self._arquivos)} arquivo(s) selecionado(s)")
        self.botao_processar.setEnabled(bool(self._arquivos))

    def processar(self, destino: Path, substituir: bool = False) -> ResultadoProcessamento:
        # Por enquanto roda na própria janela; com a IA real (ticket 02) passa para segundo plano.
        resultado = self._processador.executar(self._arquivos, destino, substituir=substituir)
        self._mostrar(resultado)
        return resultado

    def closeEvent(self, evento) -> None:
        self._processador.fechar()
        super().closeEvent(evento)

    def _escolher_arquivos(self) -> None:
        arquivos, _ = QFileDialog.getOpenFileNames(self, "Escolher documentos", "", "PDF (*.pdf)")
        if arquivos:
            self.definir_arquivos([Path(a) for a in arquivos])

    def _escolher_destino_e_processar(self) -> None:
        destino, _ = QFileDialog.getSaveFileName(self, "Salvar planilha", "controle.xlsx", "Excel (*.xlsx)")
        if not destino:
            return
        try:
            # O diálogo de salvar já pediu confirmação se o arquivo existia.
            resultado = self.processar(Path(destino), substituir=True)
        except Exception as erro:
            QMessageBox.critical(self, "Erro ao processar", f"O processamento falhou: {erro}")
            return
        if resultado.erros:
            detalhes = "\n".join(f"{e.arquivo}: {e.mensagem}" for e in resultado.erros)
            QMessageBox.warning(self, "Documentos com erro", detalhes)

    def _mostrar(self, resultado: ResultadoProcessamento) -> None:
        self.tabela.setRowCount(len(resultado.linhas))
        for numero, (_, linha) in enumerate(resultado.linhas):
            for indice, coluna in enumerate(self._colunas):
                valor = linha.valores[coluna]
                item = QTableWidgetItem(valor.valor_para_exportar or "")
                if not valor.confirmado:
                    item.setBackground(QBrush(COR_PENDENTE))
                    item.setToolTip(valor.pendencia or "")
                elif valor.trecho:
                    item.setToolTip(f"página {valor.pagina}: {valor.trecho}")
                self.tabela.setItem(numero, indice, item)
        mensagens = [f"{len(resultado.linhas)} linha(s) gerada(s)"]
        if resultado.destino:
            mensagens.append(f"planilha salva em {resultado.destino}")
        if resultado.erros:
            mensagens.append(f"{len(resultado.erros)} erro(s)")
        self.statusBar().showMessage("; ".join(mensagens))


def executar_janela(banco: Path | None = None) -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    janela = JanelaPrincipal(criar_processador(banco=banco))
    janela.show()
    return app.exec()
