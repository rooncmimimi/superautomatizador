"""Interfaces que os adaptadores implementam.

Trocar a IA (simulada, OpenRouter, Copilot) ou o formato de saída não muda os casos de uso.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol

from automatizador.dominio.modelo import CampoSugerido, ConteudoDocumento, Linha


class RespostaInvalida(Exception):
    """A IA respondeu fora do contrato de extração."""


class LeitorDocumento(Protocol):
    def ler(self, caminho: Path) -> ConteudoDocumento: ...


class AssistenteIA(Protocol):
    def extrair_linhas(
        self, conteudo: ConteudoDocumento, colunas: list[str]
    ) -> list[dict[str, CampoSugerido]]:
        """Devolve uma lista de linhas (uma por item); cada linha mapeia coluna -> sugestão.

        Levanta RespostaInvalida quando a resposta não segue o contrato.
        """
        ...


class Exportador(Protocol):
    def exportar(self, linhas: list[tuple[str, Linha]], colunas: list[str], destino: Path) -> None:
        """Grava as linhas; cada item é (nome do documento de origem, linha)."""
        ...


@dataclass(frozen=True)
class DocumentoRegistrado:
    id: int
    nome: str


@dataclass(frozen=True)
class ValorRegistrado:
    linha: int
    coluna: str
    valor: str | None
    origem: str
    trecho: str | None
    pagina: int | None
    confianca: float | None
    pendencia: str | None


@dataclass(frozen=True)
class ExecucaoRegistrada:
    id: int
    inicio: datetime
    fim: datetime | None
    resultado: str
    erro: str | None


class Repositorio(Protocol):
    def iniciar_execucao(self, descricao: str) -> int: ...

    def finalizar_execucao(self, execucao_id: int, resultado: str, erro: str | None = None) -> None: ...

    def registrar_documento(
        self, execucao_id: int, conteudo: ConteudoDocumento, linhas: list[Linha]
    ) -> DocumentoRegistrado:
        """Grava o documento e as linhas juntos: ou tudo fica no histórico, ou nada."""
        ...

    def registrar_exportacao(self, execucao_id: int, destino: Path, quantidade_linhas: int) -> None: ...

    def valores_do_documento(self, documento_id: int) -> list[ValorRegistrado]: ...

    def execucoes(self) -> list[ExecucaoRegistrada]: ...

    def fechar(self) -> None: ...

