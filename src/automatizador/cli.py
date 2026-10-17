"""Linha de comando.

    automatizador gerar-ficticios PASTA [--quantidade N]
    automatizador processar PDF [PDF ...] --saida PLANILHA.xlsx [--banco ARQUIVO.db] [--respostas PASTA]
    automatizador janela
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from automatizador.configuracao import criar_processador
from automatizador.ficticios.gerador import gerar_cte_ficticio


def _gerar(args) -> int:
    for i in range(args.quantidade):
        documento = gerar_cte_ficticio(args.pasta, numero=1234 + i)
        print(f"gerado: {documento.pdf}")
    return 0


def _processar(args) -> int:
    processador = criar_processador(banco=args.banco, pasta_respostas=args.respostas)
    resultado = processador.executar(args.arquivos, args.saida)
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


def _janela(args) -> int:
    from automatizador.interface.janela import executar_janela

    return executar_janela(banco=args.banco)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="automatizador")
    sub = parser.add_subparsers(dest="comando", required=True)

    gerar = sub.add_parser("gerar-ficticios", help="gera CT-e fictícios para testes")
    gerar.add_argument("pasta", type=Path)
    gerar.add_argument("--quantidade", type=int, default=1)
    gerar.set_defaults(funcao=_gerar)

    processar = sub.add_parser("processar", help="lê PDFs e gera uma planilha nova")
    processar.add_argument("arquivos", type=Path, nargs="+")
    processar.add_argument("--saida", type=Path, required=True)
    processar.add_argument("--banco", type=Path)
    processar.add_argument("--respostas", type=Path, help="pasta com respostas gravadas da IA simulada")
    processar.set_defaults(funcao=_processar)

    janela = sub.add_parser("janela", help="abre a interface")
    janela.add_argument("--banco", type=Path)
    janela.set_defaults(funcao=_janela)

    args = parser.parse_args(argv)
    return args.funcao(args)


if __name__ == "__main__":
    sys.exit(main())
