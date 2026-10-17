"""Leitura de PDFs com texto digital via pdfplumber."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pdfplumber

from automatizador.dominio.modelo import ConteudoDocumento, Pagina


class LeitorPdf:
    def ler(self, caminho: Path) -> ConteudoDocumento:
        caminho = Path(caminho)
        dados = caminho.read_bytes()
        try:
            with pdfplumber.open(caminho) as pdf:
                paginas = [
                    Pagina(numero=i, texto=pagina.extract_text() or "")
                    for i, pagina in enumerate(pdf.pages, start=1)
                ]
        except Exception as erro:  # pdfplumber levanta tipos variados para arquivos corrompidos
            raise ValueError(f"não foi possível ler o PDF: {erro}") from erro
        return ConteudoDocumento(
            caminho=caminho,
            hash_sha256=hashlib.sha256(dados).hexdigest(),
            paginas=paginas,
        )
