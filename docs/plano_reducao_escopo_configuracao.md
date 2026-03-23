# Plano: Redução de Escopo da Configuração Inicial

**Branch:** `feature/reduce-initial-config-scope`  
**Data:** 2026-03-23  
**Motivação:** O processo de onboarding atual exige que cada usuário configure manualmente bucket S3, prefixo, workgroup, região e outros campos de infraestrutura que são fixos no ambiente corporativo. Isso gera fricção desnecessária e erro humano. O único dado que varia por usuário é o perfil AWS (ou tipo de autenticação).

---

## 1. Objetivo

Tornar a configuração inicial do MCP trivial: o único passo necessário para um novo usuário é informar o **perfil AWS** (`aws_profile`) ou confirmar que usará credenciais padrão (`default_credentials`).

Todas as configurações de infraestrutura (bucket de resultados, bucket de catálogo, workgroup, região, catalog) ficam **fixas no código**, como constantes do repositório que o time de plataforma mantém.

O que é variável por natureza (databases, tabelas, skills) continua sendo gerenciado dinamicamente e persiste no S3.

---

## 2. O Que Muda

### 2.1 Novo arquivo de defaults corporativos: `core/company_defaults.py`

Criar um módulo com todas as constantes de infraestrutura do ambiente corporativo. Exemplo:

```python
# src/athena_knowledge_mcp/core/company_defaults.py

COMPANY_AWS_REGION = "us-east-1"
COMPANY_ATHENA_WORKGROUP = "primary"
COMPANY_ATHENA_CATALOG = "AwsDataCatalog"
COMPANY_QUERY_RESULTS_S3_BUCKET = "minha-empresa-athena-results"
COMPANY_QUERY_RESULTS_S3_PREFIX = "mcp/athena/results/"
COMPANY_CATALOG_S3_BUCKET = "minha-empresa-athena-results"
COMPANY_CATALOG_S3_PREFIX = "mcp/athena/catalog/"
COMPANY_DEFAULT_AUTHENTICATION_TYPE = "profile"  # ou "default_credentials"
```

> **Nota para o time de plataforma:** este arquivo é o único ponto de manutenção da infraestrutura corporativa. Ao publicar uma nova versão do EXE, basta atualizar as constantes aqui.

---

### 2.2 Simplificação de `ServerConfiguration` (models.py)

#### Estado atual — campos obrigatórios no onboarding:
| Campo                     | Situação atual                        |
| ------------------------- | ------------------------------------- |
| `authentication_type`     | Obrigatório pelo usuário              |
| `aws_region`              | Obrigatório pelo usuário              |
| `aws_profile`             | Opcional (só quando `auth = profile`) |
| `athena_workgroup`        | Obrigatório pelo usuário              |
| `athena_catalog`          | Tem default `"AwsDataCatalog"`        |
| `query_results_s3_bucket` | Obrigatório pelo usuário              |
| `query_results_s3_prefix` | Tem default                           |
| `catalog_bucket`          | Obrigatório pelo usuário              |
| `catalog_prefix`          | Tem default                           |
| `athena_databases`        | Opcional (variável)                   |
| `default_database`        | Opcional (variável)                   |

#### Estado desejado — o que o usuário precisa informar:
| Campo           | Nova situação                                                                   |
| --------------- | ------------------------------------------------------------------------------- |
| `aws_profile`   | **Único campo pedido ao usuário** (pode ser `None` se usar default_credentials) |
| Todos os demais | Preenchidos automaticamente a partir de `company_defaults.py`                   |

#### Mudança no modelo

O `ServerConfiguration` se torna simples — mantém apenas os campos que variam por usuário ou por sessão:

```python
class ServerConfiguration(BaseModel):
    # Único campo configurável pelo usuário
    aws_profile: str | None = None

    # Variáveis de sessão (gerenciadas automaticamente pelo MCP, não pelo usuário)
    athena_databases: list[str] = []
    default_database: str | None = None
    local_large_results_folder: Path = Path("downloads")
    inline_result_max_bytes: int = 500_000
    inline_result_max_rows: int = 200
    last_updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
```

Os campos de infraestrutura são removidos do modelo persistido. O `AppConfig` (ou um novo `ResolvedConfig`) os injeta em tempo de runtime a partir das constantes.

---

### 2.3 Novo `ResolvedConfig`: configuração completa em runtime

Para não romper as chamadas internas que dependem dos campos de infraestrutura (serviços, repositórios), criar um objeto que une os defaults corporativos com os dados do usuário:

```python
@dataclass
class ResolvedConfig:
    # Vem de company_defaults.py (fixo)
    aws_region: str
    athena_workgroup: str
    athena_catalog: str
    query_results_s3_bucket: str
    query_results_s3_prefix: str
    catalog_bucket: str
    catalog_prefix: str
    authentication_type: AwsAuthenticationType

    # Vem de ServerConfiguration (variável por usuário)
    aws_profile: str | None
    athena_databases: list[str]
    default_database: str | None
    local_large_results_folder: Path
    inline_result_max_bytes: int
    inline_result_max_rows: int
```

`AppConfig.get_resolved()` constrói este objeto combinando `company_defaults` + `ServerConfiguration` carregado do disco.

---

### 2.4 Simplificação do Onboarding Service

#### Fluxo atual (muitas perguntas):
```
1. Tipo de autenticação?
2. Região AWS?
3. Workgroup Athena?
4. Bucket de resultados?  ← lista S3 disponível
5. Prefixo do bucket?
6. Bucket do catálogo?
7. Prefixo do catálogo?
8. Perfil AWS? (se profile)
```

#### Fluxo desejado (uma única pergunta):
```
1. Qual o nome do seu perfil AWS? (ex: "default", "minha-empresa-prod")
   → ou confirmar que usará credenciais do ambiente (IAM role, env vars)
```

#### `REQUIRED_FIELDS` no `OnboardingService` — novo estado:

```python
# Nenhum campo é estritamente obrigatório agora; sem perfil, usa default_credentials
REQUIRED_FIELDS = []  # ou apenas validação de que AWS responde ao STS call
```

A validação de conectividade AWS (STS `get_caller_identity`) permanece como etapa de confirmação.

---

### 2.5 Simplificação das Tools MCP

#### `initialize_server_configuration` — novo contrato:
```
Parâmetros:
  - aws_profile (str | None) — nome do perfil AWS; se None, usa default credentials
  - skip_aws_validation (bool) — default False
```

Remove todos os outros parâmetros de infraestrutura da assinatura da tool.

#### `update_server_configuration` — novo contrato:
```
Parâmetros:
  - aws_profile (str | None)
  - default_database (str | None)
  - athena_databases (list[str] | None)
  - inline_result_max_bytes (int | None)
  - inline_result_max_rows (int | None)
  - skip_aws_validation (bool)
```

#### `get_server_configuration_status` — permanece igual, mas passa a mostrar os defaults fixos como informação de contexto (não editável).

#### `list_accessible_s3_buckets` — **remover esta tool** ou mantê-la como ferramenta de diagnóstico. Não faz mais parte do fluxo de onboarding.

---

### 2.6 O Que Permanece Variável e Persiste no S3

Os seguintes dados continuam sendo gerenciados dinamicamente, sem alteração:

| Dado                   | Onde persiste                                                          | Quem gerencia                                                    |
| ---------------------- | ---------------------------------------------------------------------- | ---------------------------------------------------------------- |
| `athena_databases`     | `state/runtime_settings.json` (local)                                  | Tool `update_server_configuration`                               |
| `default_database`     | `state/runtime_settings.json` (local)                                  | Tool `update_server_configuration`                               |
| **Índice de catálogo** | `s3://{CATALOG_BUCKET}/{CATALOG_PREFIX}/catalog/catalog_index.jsonl`   | Tools `sync_athena_database_to_catalog`, `refresh_catalog_index` |
| **Skills de tabelas**  | `s3://{CATALOG_BUCKET}/{CATALOG_PREFIX}/skills/tables/{db}/{table}.md` | Tool `create_or_update_table_skill`                              |

---

## 3. Impacto por Camada

### `core/`
| Arquivo               | Mudança                                                             |
| --------------------- | ------------------------------------------------------------------- |
| `models.py`           | Simplificar `ServerConfiguration`; remover campos de infra          |
| `config.py`           | Adicionar `get_resolved() -> ResolvedConfig` que injeta defaults    |
| `company_defaults.py` | **Novo arquivo** — centraliza todas as constantes de infraestrutura |

### `services/`
| Arquivo                  | Mudança                                                                                |
| ------------------------ | -------------------------------------------------------------------------------------- |
| `onboarding_service.py`  | Simplificar `REQUIRED_FIELDS`; remover `_enrich_storage_guidance()`; simplificar fluxo |
| `aws_session_service.py` | Usar `ResolvedConfig` em vez de `ServerConfiguration` diretamente                      |
| `athena_service.py`      | Usar `ResolvedConfig`                                                                  |
| `s3_catalog_service.py`  | Usar `ResolvedConfig`                                                                  |

### `handlers/`
| Arquivo                  | Mudança                                                                                          |
| ------------------------ | ------------------------------------------------------------------------------------------------ |
| `onboarding_handlers.py` | Remover parâmetros de infra de `initialize_server_configuration` e `update_server_configuration` |

### `server/app.py`
| Mudança                                                     |
| ----------------------------------------------------------- |
| Simplificar assinatura de `initialize_server_configuration` |
| Simplificar assinatura de `update_server_configuration`     |
| Remover ou reclassificar `list_accessible_s3_buckets`       |

### `tests/`
| Arquivo                             | Mudança                                                           |
| ----------------------------------- | ----------------------------------------------------------------- |
| `test_onboarding_service.py`        | Atualizar fixtures para o novo `ServerConfiguration` simplificado |
| `test_athena_service.py`            | Atualizar para `ResolvedConfig`                                   |
| `test_catalog_and_skill_service.py` | Atualizar para `ResolvedConfig`                                   |

---

## 4. Sequência de Execução

```
Etapa 1 — Criar company_defaults.py com as constantes do ambiente corporativo
Etapa 2 — Simplificar ServerConfiguration em models.py
Etapa 3 — Criar ResolvedConfig e atualizar AppConfig
Etapa 4 — Atualizar OnboardingService (REQUIRED_FIELDS, fluxo, remover storage guidance)
Etapa 5 — Atualizar handlers de onboarding (assinaturas)
Etapa 6 — Atualizar app.py (contratos das tools)
Etapa 7 — Propagar ResolvedConfig nos serviços que consomem configuração (aws_session, athena, s3_catalog)
Etapa 8 — Atualizar testes unitários
Etapa 9 — Validar com get_errors e execução de testes
```

---

## 5. Experiência do Usuário Após a Mudança

### Antes:
```
Usuário: quero usar o MCP
Agente: qual o tipo de autenticação? (default, profile, access_key...)
Usuário: profile
Agente: qual a região AWS?
Usuário: us-east-1
Agente: qual o workgroup do Athena?
Usuário: primary
Agente: aqui estão os buckets S3 disponíveis, qual usar para resultados?
Usuário: minha-empresa-athena-results
Agente: qual prefixo? (pressione Enter para usar mcp/athena/)
[... mais 3 perguntas ...]
```

### Depois:
```
Usuário: quero usar o MCP
Agente: qual o nome do seu perfil AWS configurado localmente?
         (ou pressione Enter para usar as credenciais padrão do ambiente)
Usuário: minha-empresa-prod
Agente: configuração salva. Testando conexão... ✓ Conectado como arn:aws:iam::123456789:user/eduardop
```

---

## 6. Riscos e Mitigações

| Risco                                                            | Mitigação                                                                                                                                                             |
| ---------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Environments diferentes (dev/prod/staging) com buckets distintos | Versões diferentes do EXE compiladas com `company_defaults.py` diferente por ambiente; ou variável de ambiente `ATHENA_MCP_ENV` que seleciona um conjunto de defaults |
| Usuário precisa usar bucket próprio temporariamente              | Manter `update_server_configuration` com parâmetros opcionais de override de bucket (modo avançado, documentado)                                                      |
| Migração de configuração existente salva em disco                | `SettingsStore.load()` detecta configuração no formato antigo (presença de `query_results_s3_bucket`) e faz migração automática para o novo formato                   |

---

## 7. Definição de Pronto

- [ ] `company_defaults.py` criado com todos os valores do ambiente corporativo preenchidos
- [ ] `ServerConfiguration` simplificado — apenas `aws_profile` e campos de sessão
- [ ] `ResolvedConfig` implementado e usado em todos os serviços
- [ ] Onboarding: único parâmetro pedido ao usuário
- [ ] `get_server_configuration_status` exibe defaults fixos como contexto
- [ ] Todos os testes passando
- [ ] `get_errors` sem erros de tipo
