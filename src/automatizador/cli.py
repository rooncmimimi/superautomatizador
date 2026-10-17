"""Linha de comando.

    automatizador gerar-ficticios PASTA [--quantidade N]
    automatizador processar PDF [PDF ...] --saida PLANILHA.xlsx [--substituir] [--banco ARQUIVO.db]
                            [--ia simulada|externa] [--modelo MODELO] [--respostas PASTA]
    automatizador medir-acerto PASTA [--modelo MODELO ...] [--ia simulada|externa]
    automatizador janela
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from automatizador.adaptadores.leitor_pdf import LeitorPdf
from automatizador.aplicacao.medir_acerto import DocumentoComGabarito, MedirAcerto
from automatizador.configuracao import IA_EXTERNA, IA_SIMULADA, ConfiguracaoAusente, criar_assistente, criar_processador
from automatizador.ficticios.gerador import SUFIXO_GABARITO, gerar_cte_ficticio, gerar_nfse_ficticia


def _gerar(args) -> int:
    for i in range(args.quantidade):
        for documento in (
            gerar_cte_ficticio(args.pasta, numero=1234 + i),
            gerar_nfse_ficticia(args.pasta, numero=5501 + i),
        ):
            print(f"gerado: {documento.pdf}")
    return 0


def _processar(args) -> int:
    try:
        processador = criar_processador(
            banco=args.banco, pasta_respostas=args.respostas, ia=args.ia, modelo=args.modelo
        )
    except ConfiguracaoAusente as erro:
        print(f"configuração ausente: {erro}", file=sys.stderr)
        return 1
    try:
        resultado = processador.executar(args.arquivos, args.saida, substituir=args.substituir)
    finally:
        processador.fechar()
    for erro in resultado.erros:
        print(f"erro em {erro.arquivo}: {erro.mensagem}", file=sys.stderr)
    if resultado.destino is None:
        print("nenhuma linha gerada; planilha não criada", file=sys.stderr)
        return 1
    pendentes = sum(
        1 for _, linha in resultado.linhas for valor in linha.valores.values() if not valor.confirmado
    )
    print(f"{len(resultado.linhas)} linha(s) gravada(s) em {resultado.destino}; {pendentes} campo(s) pendente(s)")
    return 0 if not resultado.erros else 2


def _medir(args) -> int:
    documentos = [
        DocumentoComGabarito(pdf, json.loads(gabarito.read_text(encoding="utf-8"))["linhas"])
        for pdf in sorted(args.pasta.glob("*.pdf"))
        if (gabarito := pdf.with_name(pdf.stem + SUFIXO_GABARITO)).exists()
    ]
    if not documentos:
        print(f"nenhum PDF com gabarito em {args.pasta}", file=sys.stderr)
        return 1
    medidor = MedirAcerto(LeitorPdf())
    for modelo in args.modelo or [None]:
        try:
            assistente = criar_assistente(args.ia, modelo=modelo)
        except ConfiguracaoAusente as erro:
            print(f"configuração ausente: {erro}", file=sys.stderr)
            return 1
        try:
            resultado = medidor.medir(assistente, documentos)
        finally:
            if fechar := getattr(assistente, "fechar", None):
                fechar()
        nome = modelo or args.ia
        print(f"{nome}: {resultado.taxa:.0%} de acerto ({resultado.acertos}/{resultado.celulas} células, "
              f"{resultado.documentos} documento(s))")
        for coluna, quantidade in resultado.erros_por_coluna.most_common():
            print(f"  {coluna}: {quantidade} erro(s)")
        for falha in resultado.falhas:
            print(f"  falha em {falha.arquivo}: {falha.mensagem}")
    return 0


def _janela(args) -> int:
    from automatizador.interface.janela import executar_janela

    return executar_janela(banco=args.banco)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="automatizador")
    sub = parser.add_subparsers(dest="comando", required=True)

    gerar = sub.add_parser("gerar-ficticios", help="gera CT-e e NFS-e fictícios para testes")
    gerar.add_argument("pasta", type=Path)
    gerar.add_argument("--quantidade", type=int, default=1)
    gerar.set_defaults(funcao=_gerar)

    processar = sub.add_parser("processar", help="lê PDFs e gera uma planilha nova")
    processar.add_argument("arquivos", type=Path, nargs="+")
    processar.add_argument("--saida", type=Path, required=True)
    processar.add_argument("--banco", type=Path)
    processar.add_argument("--respostas", type=Path, help="pasta com respostas gravadas da IA simulada")
    processar.add_argument("--ia", choices=[IA_SIMULADA, IA_EXTERNA], default=IA_SIMULADA)
    processar.add_argument("--modelo", help="modelo do serviço de IA externo (ex.: openai/gpt-4o-mini)")
    processar.add_argument("--substituir", action="store_true", help="substitui a planilha de saída se já existir")
    processar.set_defaults(funcao=_processar)

    medir = sub.add_parser("medir-acerto", help="mede a taxa de acerto da IA nos documentos fictícios")
    medir.add_argument("pasta", type=Path)
    medir.add_argument("--modelo", action="append", help="pode repetir para comparar modelos")
    medir.add_argument("--ia", choices=[IA_SIMULADA, IA_EXTERNA], default=IA_EXTERNA)
    medir.set_defaults(funcao=_medir)

    janela = sub.add_parser("janela", help="abre a interface")
    janela.add_argument("--banco", type=Path)
    janela.set_defaults(funcao=_janela)

    args = parser.parse_args(argv)
    return args.funcao(args)


if __name__ == "__main__":
    sys.exit(main())
