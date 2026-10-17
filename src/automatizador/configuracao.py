"""Montagem do caso de uso com os adaptadores padrão (composição em um único lugar)."""

from __future__ import annotations

import os
from pathlib import Path

from automatizador.adaptadores.exportador_xlsx import ExportadorXlsx
from automatizador.adaptadores.ia_simulada import IASimulada
from automatizador.adaptadores.leitor_pdf import LeitorPdf
from automatizador.adaptadores.repositorio_sqlite import RepositorioSqlite
from automatizador.aplicacao.processar_documento import ProcessarDocumentos


def pasta_dados() -> Path:
    """Pasta local do aplicativo: %LOCALAPPDATA%\\Automatizador no Windows, ~/.automatizador fora dele."""
    base = os.environ.get("LOCALAPPDATA")
    return Path(base) / "Automatizador" if base else Path.home() / ".automatizador"


def criar_processador(banco: Path | None = None, pasta_respostas: Path | None = None) -> ProcessarDocumentos:
    return ProcessarDocumentos(
        leitor=LeitorPdf(),
        assistente=IASimulada(pasta_respostas),
        repositorio=RepositorioSqlite(banco or pasta_dados() / "automatizador.db"),
        exportador=ExportadorXlsx(),
    )
