"""Montagem do caso de uso com os adaptadores padrão (composição em um único lugar)."""

from __future__ import annotations

import os
from pathlib import Path

from automatizador.adaptadores.exportador_xlsx import ExportadorXlsx
from automatizador.adaptadores.ia_openai import ENDERECO_OPENROUTER, ConfiguracaoIA, IACompativelOpenAI
from automatizador.adaptadores.ia_simulada import IASimulada
from automatizador.adaptadores.leitor_pdf import LeitorPdf
from automatizador.adaptadores.repositorio_sqlite import RepositorioSqlite
from automatizador.aplicacao.portas import AssistenteIA
from automatizador.aplicacao.processar_documento import ProcessarDocumentos

IA_SIMULADA = "simulada"
IA_EXTERNA = "externa"


def pasta_dados() -> Path:
    """Pasta local do aplicativo: %LOCALAPPDATA%\\Automatizador no Windows, ~/.automatizador fora dele."""
    base = os.environ.get("LOCALAPPDATA")
    return Path(base) / "Automatizador" if base else Path.home() / ".automatizador"


class ConfiguracaoAusente(Exception):
    """Falta uma configuração obrigatória (ex.: a chave do serviço de IA)."""


def configuracao_ia(modelo: str | None = None, ambiente: dict[str, str] | None = None) -> ConfiguracaoIA:
    """Lê a configuração do serviço de IA das variáveis de ambiente; a chave nunca fica no código.

    AUTOMATIZADOR_IA_CHAVE (ou OPENROUTER_API_KEY), AUTOMATIZADOR_IA_MODELO, AUTOMATIZADOR_IA_ENDERECO
    e AUTOMATIZADOR_IA_PERMITE_REAIS=sim (só depois de aprovação; por padrão só documentos fictícios).
    """
    ambiente = os.environ if ambiente is None else ambiente
    chave = ambiente.get("AUTOMATIZADOR_IA_CHAVE") or ambiente.get("OPENROUTER_API_KEY")
    modelo = modelo or ambiente.get("AUTOMATIZADOR_IA_MODELO")
    if not chave:
        raise ConfiguracaoAusente("defina AUTOMATIZADOR_IA_CHAVE com a chave do serviço de IA")
    if not modelo:
        raise ConfiguracaoAusente("defina AUTOMATIZADOR_IA_MODELO ou use --modelo")
    return ConfiguracaoIA(
        modelo=modelo,
        chave=chave,
        endereco=ambiente.get("AUTOMATIZADOR_IA_ENDERECO") or ENDERECO_OPENROUTER,
        permite_documentos_reais=ambiente.get("AUTOMATIZADOR_IA_PERMITE_REAIS", "").casefold() == "sim",
    )


def criar_assistente(ia: str = IA_SIMULADA, pasta_respostas: Path | None = None, modelo: str | None = None) -> AssistenteIA:
    if ia == IA_EXTERNA:
        return IACompativelOpenAI(configuracao_ia(modelo))
    return IASimulada(pasta_respostas)


def criar_processador(
    banco: Path | None = None,
    pasta_respostas: Path | None = None,
    ia: str = IA_SIMULADA,
    modelo: str | None = None,
) -> ProcessarDocumentos:
    return ProcessarDocumentos(
        leitor=LeitorPdf(),
        assistente=criar_assistente(ia, pasta_respostas, modelo),
        repositorio=RepositorioSqlite(banco or pasta_dados() / "automatizador.db"),
        exportador=ExportadorXlsx(),
    )
