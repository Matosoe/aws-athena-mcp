# MCP Task Scheduler

Agendador de tarefas que fala diretamente com servidores MCP via JSON-RPC/stdio,
sem precisar do VS Code ou do GitHub Copilot no meio.

## Arquitetura

```
Windows Task Scheduler (schtasks)
        │
        ▼
  scheduler/cli.py        ← entry-point Python
        │
        ▼
  scheduler/task_runner.py ← lê YAML, executa steps sequenciais
        │
        ▼
  scheduler/mcp_client.py  ← cliente MCP (JSON-RPC 2.0 / stdio)
        │
        ▼
  MCP Server (athena_knowledge_mcp)  ← seu servidor existente
        │
        ▼
  AWS Athena / S3 / catálogo
```

## Pré-requisitos

```bash
pip install pyyaml
```

(O resto das dependências já está no `pyproject.toml` do projeto.)

## Uso rápido

### 1. Listar tools disponíveis no MCP

```bash
python -m scheduler.cli tools
```

### 2. Chamar uma tool manualmente

```bash
python -m scheduler.cli call get_server_configuration_status

python -m scheduler.cli call execute_athena_query --args '{"query": "SELECT 1", "database": "default"}'
```

### 3. Executar um arquivo de tarefa

```bash
python -m scheduler.cli run --file scheduler/tasks/01_daily_catalog_refresh.yaml
```

### 4. Executar todas as tarefas com uma tag

```bash
python -m scheduler.cli run --tag daily
```

### 5. Instalar no Windows Task Scheduler

```bash
# Tarefa diária às 08:00
python -m scheduler.cli install --preset daily --tag daily --time 08:00

# Tarefa semanal às segundas
python -m scheduler.cli install --preset weekly --tag weekly --time 07:00 --days MON
```

### 6. Ver tarefas agendadas

```bash
python -m scheduler.cli status
```

### 7. Remover uma tarefa agendada

```bash
python -m scheduler.cli uninstall --name Daily_daily
```

## Definindo tarefas (YAML)

Crie arquivos `.yaml` em `scheduler/tasks/`. Exemplo:

```yaml
id: minha_tarefa
name: "Descrição da tarefa"
tags: [daily, monitoring]
stop_on_failure: false

steps:
  - tool: get_server_configuration_status
    arguments: {}

  - tool: execute_athena_query
    arguments:
      query: "SELECT count(*) FROM meu_db.minha_tabela"
      database: "meu_db"
      wait_for_completion: true

  # Referência ao resultado do step anterior
  - tool: fetch_query_result_preview
    arguments:
      query_execution_id: "$ref:step_1.query_execution_id"
```

### Referências entre steps

Use `$ref:step_N.campo.subcampo` para passar resultados de um step como argumento do próximo.

- `$ref:step_0` → resultado inteiro do primeiro step
- `$ref:step_1.query_execution_id` → campo específico do segundo step

## Logs de auditoria

Toda execução gera um registro em `scheduler/logs/audit_YYYY-MM-DD.jsonl` (JSON Lines).

Cada linha contém:
- `task_id`, `task_name`
- `started_at`, `finished_at`
- `success` (bool)
- `steps[]` com tool, arguments, success, error, duration

## Exemplos incluídos

| Arquivo                         | Descrição                                  | Tags                  |
| ------------------------------- | ------------------------------------------ | --------------------- |
| `01_daily_catalog_refresh.yaml` | Refresh do catálogo + query de conferência | daily, catalog        |
| `02_sync_database.yaml`         | Sync de tabelas Athena → catálogo          | weekly, catalog, sync |
| `03_health_check.yaml`          | Queries de monitoramento                   | daily, monitoring     |

## Ambiente bancário — notas de segurança

- **Sem APIs externas**: tudo roda local, stdio entre processos Python
- **Sem credenciais hardcoded**: usa os profiles AWS CLI já configurados
- **Audit log completo**: cada execução é registrada com timestamp e resultado
- **Least privilege**: tarefas no Task Scheduler rodam com `LIMITED` (privilégio mínimo)
- **Sem rede extra**: não abre portas, não expõe HTTP — é processo → processo via pipe
