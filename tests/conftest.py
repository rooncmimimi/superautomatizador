import os

import pytest

from automatizador.ficticios.gerador import gerar_cte_ficticio

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture
def cte_ficticio(tmp_path):
    """Gera um CT-e fictício (PDF + gabarito + resposta simulada da IA) numa pasta temporária."""
    pasta = tmp_path / "documentos"
    return gerar_cte_ficticio(pasta, numero=1234)
