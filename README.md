# Automatizador

Aplicativo desktop para Windows que lê documentos fiscais (CT-e e NFS-e em PDF), propõe as linhas da planilha de controle com a evidência de cada valor, e grava a planilha depois da revisão humana.

- Especificação do MVP: https://claude.ai/code/artifact/a72f604d-ea20-4d65-9f3b-10d0aa829414
- Tickets: aba Issues deste repositório

## Estado atual

Esqueleto de ponta a ponta (ticket 01): um CT-e ou uma NFS-e fictícios em PDF com texto viram uma linha numa planilha nova, usando uma **IA simulada** (respostas gravadas), com histórico em SQLite. A leitura por uma IA real entra no ticket 02.

Use apenas **documentos fictícios** no computador pessoal.

## Como rodar no Windows

Requer Python 3.12 ou mais novo.

```powershell
git clone https://github.com/rooncmimimi/superautomatizador.git
cd superautomatizador
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
```

Gerar um CT-e e uma NFS-e fictícios e processá-los:

```powershell
automatizador gerar-ficticios exemplos
automatizador processar exemplos\cte_1234.pdf exemplos\nfse_5501.pdf --saida saida\controle.xlsx
```

O aplicativo nunca sobrescreve uma planilha que já existe; use `--substituir` se for essa a intenção.

Abrir a janela:

```powershell
automatizador janela
```

Rodar os testes:

```powershell
pytest
```

O histórico fica em `%LOCALAPPDATA%\Automatizador\automatizador.db` (use `--banco` para outro arquivo).

## Organização do código

| Pasta | Papel |
| --- | --- |
| `src/automatizador/dominio` | Modelo de dados e regras; não depende de bibliotecas de E/S |
| `src/automatizador/aplicacao` | Casos de uso e as interfaces (portas) que os adaptadores implementam |
| `src/automatizador/adaptadores` | PDF, IA, Excel e SQLite |
| `src/automatizador/interface` | Janela PySide6; só chama casos de uso |
| `src/automatizador/ficticios` | Gerador de documentos fictícios com gabarito |

Regra principal: nenhum valor é exportado sem evidência. Um valor só sai preenchido na planilha quando o trecho citado existe na página indicada e o valor aparece dentro desse trecho; caso contrário, a célula sai vazia e destacada, e o motivo fica na aba **Rastreabilidade**.

Regras de preenchimento já definidas:

| Coluna | Regra |
| --- | --- |
| TIPO DE NOTA | Derivada do tipo de documento, não da IA: CT-e → `CT-e`; NFS-e → `Nota Fiscal` |
| VALOR TOTAL | Valor do serviço/prestação, antes das retenções (não o valor líquido) |
| PEDIDO, DATA DO VENCIMENTO | Na NFS-e costumam vir no texto livre da descrição do serviço |
| CÓDIGO FORNECEDOR, CONTA RAZÃO, CENTRO DE CUSTO / PEP | Não estão no documento; hoje são consultados no SAP (ME23N, pelo pedido). Ficam pendentes para preenchimento manual |
