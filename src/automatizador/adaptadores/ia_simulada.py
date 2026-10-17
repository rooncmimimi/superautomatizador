"""IA simulada: devolve respostas gravadas, para testar o fluxo sem custo e sem rede.

Para o documento `nota.pdf`, procura `nota.resposta.json` na pasta de respostas.
"""

from __future__ import annotations

from pathlib import Path

from automatizador.adaptadores.contrato_ia import interpretar_resposta
from automatizador.aplicacao.portas import RespostaInvalida
from automatizador.dominio.modelo import CampoSugerido, ConteudoDocumento

SUFIXO_RESPOSTA = ".resposta.json"


class IASimulada:
    def __init__(self, pasta_respostas: Path | None = None):
        self._pasta = Path(pasta_respostas) if pasta_respostas else None

    def extrair_linhas(
        self, conteudo: ConteudoDocumento, colunas: list[str]
    ) -> list[dict[str, CampoSugerido]]:
        pasta = self._pasta or conteudo.caminho.parent
        arquivo = pasta / f"{conteudo.caminho.stem}{SUFIXO_RESPOSTA}"
        if not arquivo.exists():
            raise RespostaInvalida(f"sem resposta gravada para {conteudo.caminho.name}")
        return interpretar_resposta(arquivo.read_text(encoding="utf-8"), colunas)
