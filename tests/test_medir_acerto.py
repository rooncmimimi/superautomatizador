"""Medição da taxa de acerto contra os gabaritos (com a IA simulada no lugar de um modelo real)."""

import json

from automatizador.adaptadores.ia_simulada import IASimulada
from automatizador.adaptadores.leitor_pdf import LeitorPdf
from automatizador.aplicacao.medir_acerto import DocumentoComGabarito, MedirAcerto
from automatizador.cli import main


def _documento(ficticio):
    gabarito = json.loads(ficticio.gabarito.read_text(encoding="utf-8"))
    return DocumentoComGabarito(ficticio.pdf, gabarito["linhas"])


def test_ia_perfeita_acerta_tudo(cte_ficticio, nfse_ficticia):
    resultado = MedirAcerto(LeitorPdf()).medir(
        IASimulada(cte_ficticio.pdf.parent), [_documento(cte_ficticio), _documento(nfse_ficticia)]
    )

    assert resultado.documentos == 2
    assert resultado.taxa == 1.0
    assert resultado.celulas == 7 + 8  # só células com valor no gabarito ou preenchidas pela IA


def test_erros_sao_contados_por_coluna(cte_ficticio):
    resposta = json.loads(cte_ficticio.resposta_simulada.read_text(encoding="utf-8"))
    resposta["linhas"][0]["campos"]["VALOR TOTAL"]["valor"] = "9.999,99"
    cte_ficticio.resposta_simulada.write_text(json.dumps(resposta), encoding="utf-8")

    resultado = MedirAcerto(LeitorPdf()).medir(IASimulada(cte_ficticio.pdf.parent), [_documento(cte_ficticio)])

    assert resultado.erros_por_coluna == {"VALOR TOTAL": 1}
    assert resultado.acertos == resultado.celulas - 1


def test_documento_que_falha_conta_como_erro(cte_ficticio):
    cte_ficticio.resposta_simulada.unlink()

    resultado = MedirAcerto(LeitorPdf()).medir(IASimulada(cte_ficticio.pdf.parent), [_documento(cte_ficticio)])

    assert resultado.taxa == 0.0
    assert resultado.falhas


def test_comando_medir_acerto(tmp_path, capsys):
    pasta = tmp_path / "docs"
    main(["gerar-ficticios", str(pasta)])

    assert main(["medir-acerto", str(pasta), "--ia", "simulada"]) == 0
    assert "simulada: 100% de acerto" in capsys.readouterr().out
