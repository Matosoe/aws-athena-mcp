# AWS Athena Knowledge MCP

Servidor MCP local em Python para executar consultas no AWS Athena e manter um catálogo de tabelas com skills detalhados no S3.

## Escopo desta primeira versão

- onboarding inicial com persistência local de configuração;
- execução genérica de SQL no Athena;
- descoberta de databases, tabelas e propriedades direto no Athena por tools explícitas;
- listagens indexadas de databases e tabelas a partir do catálogo S3 para baixa latência;
- descoberta direta no Athena somente por tools explícitas, sem merge automático com o índice;
- retorno inline para resultados pequenos e sinalização para resultados grandes;
- busca textual simples no catálogo de tabelas armazenado no S3;
- leitura e atualização de skill detalhado por tabela.

## Requisitos

- Python 3.11+
- credenciais AWS válidas no ambiente local ou informadas no onboarding;
- acesso ao bucket de resultados do Athena e ao bucket do catálogo.

## Instalação

O projeto não exige criar um ambiente virtual local; instale as dependências diretamente no Python do sistema (3.11+ recomendado):

```cmd
py -3.11 -m pip install -e .[dev]
```

Se o launcher `py` não estiver disponível, use o executável `python` no PATH:

```cmd
python -m pip install -e .[dev]
```

## Distribuição simplificada

Para cliente final, o caminho mais simples agora é distribuir o executável Windows.

### Opcao: executavel Windows

Publicador do servidor:

```cmd
# usa o Python do PATH; argumento opcional pode ser fornecido
scripts\build_windows_exe.py
```

O build gera:

- binario versionado em `dist/aws-athena-mcp-v<versao>-<yyyymmdd-HHMMSS>.exe`;
- alias estavel em `dist/aws-athena-mcp-latest.exe`;
- metadados do ultimo build em `dist/LATEST_BUILD.txt`.

Politica completa de versionamento: `docs/versionamento.md`.

Cliente final via MCP por `stdio`:

```json
{
	"servers": {
		"aws-athena-mcp": {
			"type": "stdio",
			"command": "C:/athena-mcp/aws-athena-mcp-latest.exe",
			"args": []
		}
	},
	"inputs": []
}
```

Observacoes:

- o executavel nao exige Python instalado na maquina do cliente;
- por padrao, o `.exe` salva `state/` e `downloads/` ao lado do binario, o que evita depender do diretorio atual do processo;
- se quiser mudar esse local, defina a variavel de ambiente `ATHENA_MCP_HOME` antes de iniciar o processo.

Exemplo pronto de configuracao MCP fica em `.vscode/mcp.windows-exe.json`.

## Executar localmente

```cmd
python main.py
```

O servidor utiliza transporte `stdio`, adequado para integração com GitHub Copilot Chat no VS Code.

## Smoke Test Real

O fluxo abaixo valida o servidor MCP de ponta a ponta, sem depender da integração do editor:

- inicializa uma sessão MCP via `stdio`;
- persiste uma configuração real com AWS válida;
- grava um skill de tabela no S3;
- consulta o catálogo;
- executa uma query real no Athena;
- lê o preview do resultado.

### Pré-requisitos

- credenciais AWS válidas no ambiente local;
- workgroup Athena existente;
- bucket S3 com permissão de leitura e escrita para catálogo e resultados;
- dependências instaladas no interpretador atual.

Antes do smoke test, vale confirmar a identidade AWS ativa:

```cmd
aws sts get-caller-identity
```

### Executar o smoke test

No `cmd.exe`, salve o script abaixo como `smoke_test_real.py` e execute:

```cmd
python smoke_test_real.py
```

Conteudo de `smoke_test_real.py`:

```python
import json
from datetime import UTC, datetime

import anyio
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

WORKDIR = r"C:\projetos\aws-athena-mcp"
prefix_root = datetime.now(UTC).strftime("mcp-smoke/%Y%m%d-%H%M%S")
query_prefix = f"{prefix_root}/results"
catalog_prefix = f"{prefix_root}/catalog"


def dump(label, value):
	print(f"\n=== {label} ===")
	print(json.dumps(value, indent=2, ensure_ascii=False, default=str))


async def main() -> None:
	params = StdioServerParameters(command="python", args=["main.py"], cwd=WORKDIR)

	async with stdio_client(params) as streams:
		async with ClientSession(*streams) as session:
			await session.initialize()

			init_config = await session.call_tool(
				"initialize_server_configuration",
				{
					"authentication_type": "default_credentials",
					"aws_region": "us-east-1",
					"athena_workgroup": "primary",
					"default_database": "default",
					"query_results_s3_bucket": "my-athena-results-bucket",
					"query_results_s3_prefix": query_prefix,
					"catalog_bucket": "my-athena-catalog-bucket",
					"catalog_prefix": catalog_prefix,
					"athena_catalog": "AwsDataCatalog",
					"local_large_results_folder": "downloads",
					"inline_result_max_bytes": 500000,
					"inline_result_max_rows": 200,
					"skip_aws_validation": False,
				},
			)
			dump("initialize_server_configuration", init_config.model_dump(mode="json"))

			upsert_skill = await session.call_tool(
				"create_or_update_table_skill",
				{
					"database_name": "default",
					"table_name": "mcp_smoke_test_table",
					"description": "Tabela sintética para smoke test do servidor MCP.",
					"content_markdown": "# Smoke Test\n\nTabela criada durante smoke test automatizado.",
					"summary": "Registro sintético de smoke test",
					"business_context": "Validação de integração MCP, S3 e catálogo.",
					"common_use_cases": ["verificar catálogo", "validar leitura de skill"],
					"tags": ["smoke", "test"],
				},
			)
			dump("create_or_update_table_skill", upsert_skill.model_dump(mode="json"))

			databases = await session.call_tool("list_catalog_databases")
			dump("list_catalog_databases", databases.model_dump(mode="json"))

			search = await session.call_tool(
				"search_table_catalog",
				{"query": "smoke", "limit": 5},
			)
			dump("search_table_catalog", search.model_dump(mode="json"))

			query = await session.call_tool(
				"execute_athena_query",
				{
					"query": "SELECT 1 AS smoke_test",
					"database": "default",
					"catalog": "AwsDataCatalog",
					"workgroup": "primary",
					"wait_for_completion": True,
					"max_wait_seconds": 60,
				},
			)
			dump("execute_athena_query", query.model_dump(mode="json"))

			structured = query.structuredContent or {}
			query_execution_id = structured.get("query_execution_id")
			if query_execution_id:
				preview = await session.call_tool(
					"fetch_query_result_preview",
					{"query_execution_id": query_execution_id},
				)
				dump("fetch_query_result_preview", preview.model_dump(mode="json"))


anyio.run(main)
```

### Resultado esperado

- `initialize_server_configuration` retorna `is_configured: true`;
- `create_or_update_table_skill` retorna o `detail_file_s3_uri` salvo no S3;
- `list_catalog_databases` inclui o database usado no teste;
- `search_table_catalog` encontra a tabela `mcp_smoke_test_table`;
- `execute_athena_query` retorna `status: SUCCEEDED`;
- `fetch_query_result_preview` retorna uma linha com o valor `1`.

## Ferramentas MCP expostas

- `initialize_server_configuration`
- `get_server_configuration_status`
- `update_server_configuration`
- `search_table_catalog`
- `get_table_skill`
- `create_or_update_table_skill`
- `refresh_catalog_index`
- `list_catalog_databases`
- `list_catalog_tables`
- `list_aws_cli_profiles`
- `aws_sso_login`
- `aws_sts_get_caller_identity`
- `list_athena_databases`
- `list_athena_tables`
- `get_athena_table_metadata`
- `sync_athena_database_to_catalog`
- `execute_athena_query`
- `get_query_execution_status`
- `fetch_query_result_preview`
- `materialize_large_result_locally`
- `list_local_result_files`

## Tools auxiliares de autenticacao AWS CLI

Para reduzir atrito no fluxo de login SSO, o servidor expoe tools especificas da AWS CLI (sem execucao generica de shell):

- `list_aws_cli_profiles`: lista perfis encontrados em `~/.aws/config` e `~/.aws/credentials`.
- `aws_sso_login`: executa `aws sso login --profile <profile>`.
- `aws_sts_get_caller_identity`: valida a sessao ativa com `aws sts get-caller-identity`.

Fluxo recomendado para perfil SSO:

1. Chamar `list_aws_cli_profiles` para escolher o profile.
2. Chamar `aws_sso_login` com esse profile.
3. Chamar `aws_sts_get_caller_identity` para confirmar identidade e conta.
4. Usar `update_server_configuration` com `authentication_type="profile"` e `aws_profile="<profile>"`.

## Descoberta de catálogo

As listagens padrão do servidor usam apenas o índice resumido mantido no S3. Isso mantém baixa latência e evita misturar dados ainda não catalogados com o inventário curado.

Quando for necessário consultar o catálogo real do Athena, use as tools explícitas `list_athena_tables` e `get_athena_table_metadata` com o `database_name` informado pelo usuário. Em ambientes com IAM restrito, `list_athena_databases` pode retornar access denied.

`get_athena_table_metadata` passa a derivar colunas, partições e propriedades a partir de `SHOW CREATE TABLE <nome_da_tabela>` no database informado, evitando depender da permissão `GetTableMetadata`.

Quando o usuário quiser enriquecer o índice com tabelas descobertas no Athena, use `sync_athena_database_to_catalog` para gerar skills básicas e atualizar o catálogo S3 de forma controlada.

Para ações genéricas no Athena, continue usando `execute_athena_query`. Isso cobre consultas de metadados e qualquer SQL suportada pelo Athena no workgroup configurado.

## Qualidade

```cmd
pytest
ruff check .
mypy src
```

## Protecao contra segredos em commit

O repositorio inclui um hook local de pre-commit em `.githooks/pre-commit` que bloqueia commits com sinais comuns de segredos em arquivos staged, incluindo:

- access key AWS com prefixo `AKIA` ou `ASIA`;
- `aws_secret_access_key` ou `AWS_SECRET_ACCESS_KEY` com valor preenchido;
- `aws_session_token` ou `AWS_SESSION_TOKEN` com valor preenchido;
- chaves privadas e arquivos sensiveis como `.pem`, `.key`, `.p12` e `.pfx`.

Ative o hook localmente com:

```cmd
git config core.hooksPath .githooks
```

Para validar manualmente antes de commitar:

```cmd
set PYTHONPATH=src && python -m athena_knowledge_mcp.utils.secret_scanner --staged
```
