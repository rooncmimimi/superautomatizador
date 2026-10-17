import os

import pytest

from automatizador.ficticios.gerador import gerar_cte_ficticio, gerar_nfse_ficticia

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture
def cte_ficticio(tmp_path):
    """Gera um CT-e fictício (PDF + gabarito + resposta simulada da IA) numa pasta temporária."""
    pasta = tmp_path / "documentos"
    return gerar_cte_ficticio(pasta, numero=1234)


@pytest.fixture
def nfse_ficticia(tmp_path):
    """Gera uma NFS-e fictícia no leiaute do DANFSe (rótulo numa linha, valor na de baixo)."""
    return gerar_nfse_ficticia(tmp_path / "documentos", numero=5501)
