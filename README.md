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
automatizador processar exemplos\cte_1234.pdf exemplos\nfse_5501.pdf --saida saida\controle.xlsx --aprovar-todas
```

Sem `--aprovar-todas` o programa só lê e mostra o que encontrou, sem gravar planilha: nenhuma linha é gravada sem aprovação.

O aplicativo nunca sobrescreve uma planilha que já existe; use `--substituir` se for essa a intenção.

### Usar uma IA de verdade (OpenRouter)

Só com **documentos fictícios**: o programa se recusa a enviar a um serviço externo um PDF que não tenha a marca "DOCUMENTO FICTÍCIO".

1. Crie uma conta em https://openrouter.ai e gere uma chave em *Keys*.
2. No PowerShell, defina a chave e o modelo (valem só para aquela janela; a chave nunca vai para o código):

```powershell
$env:AUTOMATIZADOR_IA_CHAVE = "cole-a-chave-aqui"
$env:AUTOMATIZADOR_IA_MODELO = "openai/gpt-4o-mini"
```

3. Processe com a IA externa, ou compare modelos pela taxa de acerto nos fictícios:

```powershell
automatizador processar exemplos\nfse_5501.pdf --saida saida\ia.xlsx --ia externa --aprovar-todas
automatizador medir-acerto exemplos --modelo openai/gpt-4o-mini --modelo google/gemini-2.5-flash
```

Outros serviços compatíveis com a API da OpenAI funcionam trocando `AUTOMATIZADOR_IA_ENDERECO`.

Abrir a janela:

```powershell
automatizador janela
```

Na janela: **Adicionar PDFs…** → **Ler documentos** → revise a tabela (células amarelas estão pendentes; clique numa célula para ver o trecho e a página do PDF com o trecho destacado; dê dois cliques para corrigir) → **Aprovar** as linhas → **Exportar aprovadas…**. Cada correção fica no histórico como nova versão, com usuário e data.

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
