"""Imagem de uma página do PDF, com o trecho comprobatório destacado, para a tela de revisão."""

from __future__ import annotations

import io
from pathlib import Path

import pdfplumber


def renderizar_pagina(
    caminho: Path, numero: int, destaques: list[str] | None = None, resolucao: int = 100
) -> bytes:
    """Devolve a página `numero` (começando em 1) como PNG; o PDF original não é alterado.

    Destaca o primeiro texto de `destaques` encontrado na página (ex.: o trecho e, se ele
    ocupar mais de uma linha do PDF e não for achado inteiro, o próprio valor).
    """
    with pdfplumber.open(caminho) as pdf:
        if not 1 <= numero <= len(pdf.pages):
            raise ValueError(f"o documento não tem a página {numero}")
        pagina = pdf.pages[numero - 1]
        imagem = pagina.to_image(resolution=resolucao)
        for texto in filter(None, destaques or []):
            ocorrencias = pagina.search(texto, regex=False, case=False)
            if ocorrencias:
                imagem.draw_rects(ocorrencias, stroke=(220, 120, 0), stroke_width=2, fill=(255, 210, 0, 60))
                break
        saida = io.BytesIO()
        imagem.annotated.save(saida, format="PNG")
    return saida.getvalue()
