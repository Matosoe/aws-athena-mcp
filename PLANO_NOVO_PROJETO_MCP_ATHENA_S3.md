# Plano do novo projeto: MCP local para Athena + S3

## 1. Objetivo

Criar um novo repositório em Python para um servidor MCP executado localmente, acessado via GitHub Copilot Chat no VS Code, com dois papéis principais:

1. executar consultas genéricas no AWS Athena;
2. gerenciar conhecimento de tabelas no S3 em um modelo equivalente a `skills`, dividido em dois grupos de arquivos.

O servidor deve apoiar tanto usuários técnicos quanto não técnicos. A ideia é que a LLM:

- consulte um índice resumido das tabelas;
- escolha a tabela mais adequada;
- leia o arquivo detalhado da tabela;
- gere a SQL;
- peça ao MCP para executar a consulta no Athena.

---

## 2. Aprendizados do projeto atual

O repositório atual já fornece uma boa base arquitetural para o novo projeto. Os principais padrões que vale reutilizar são:

- separação entre `server`, `handlers`, `services`, `core` e `utils`;
- centralização de configuração em `config.py`;
- camada de serviços isolando chamadas AWS;
- validadores para entradas antes de chamar AWS;
- respostas padronizadas para o protocolo MCP;
- estrutura pronta para testes unitários.

### Limitações do projeto atual que o novo repositório deve resolver

- configuração depende de variáveis de ambiente e não de onboarding guiado;
- foco atual é apenas Athena;
- não existe camada para S3 como base de conhecimento/skills;
- não existe persistência local de configuração do usuário;
- não existe política de resposta diferente para resultado pequeno versus grande;
- não existe gerenciamento de arquivos detalhados por tabela.

---

## 3. Escopo funcional do novo repositório

### 3.1 Funcionalidades obrigatórias

1. **Onboarding inicial obrigatório**
   - No primeiro acesso ao MCP, independentemente da ferramenta chamada, o servidor deve detectar ausência de configuração.
   - Deve solicitar e persistir as configurações iniciais de AWS, Athena e S3.
   - Após salvo, o servidor passa a reutilizar essas configurações em todas as chamadas seguintes.

2. **Consulta genérica ao Athena**
   - Executar qualquer SQL enviada pela LLM.
   - Permitir informar `database`, `catalog`, `workgroup` e configurações relacionadas.
   - Registrar `query_execution_id`, tempo de execução, local do resultado no S3 e status final.

3. **Catálogo resumido para descoberta de tabelas**
   - Manter um índice vetorial/resumido com databases, tabelas, descrição curta e ponteiro para o arquivo detalhado no S3.
   - Esse índice é a primeira fonte consultada pela LLM para decidir qual tabela usar.

4. **Arquivos detalhados por tabela**
   - Cada tabela terá um arquivo próprio com descrição detalhada.
   - O conteúdo deve incluir colunas, domínios, principais usos, observações e exemplos de filtros/junções quando houver.

5. **Geração e atualização de skills de tabela**
   - O MCP deve possuir ferramenta para criar/atualizar o arquivo detalhado de uma tabela.
   - Ao criar/atualizar o detalhamento, também deve atualizar o índice resumido/vetorial.

6. **Dois modos de resposta para queries Athena**
   - **Resultado pequeno:** retornar conteúdo diretamente na resposta do MCP.
   - **Resultado grande:** detectar tamanho do arquivo gerado no S3 e expor um fluxo para salvar o resultado em pasta local configurada.

7. **Acesso a S3**
   - Ler e gravar arquivos do catálogo resumido.
   - Ler e gravar arquivos detalhados por tabela.
   - Inspecionar o tamanho do arquivo resultante de uma query Athena.

---

## 4. Público-alvo e modo de uso

### Público-alvo

- desenvolvedores de sistemas;
- analistas e usuários de negócio com apoio da LLM;
- usuários do GitHub Copilot Chat no VS Code.

### Fluxo esperado

1. Usuário conversa com a LLM no VS Code.
2. A LLM consulta o MCP para localizar tabelas candidatas.
3. A LLM lê o skill detalhado da tabela escolhida.
4. A LLM monta a SQL.
5. A LLM chama o MCP para executar a query.
6. O MCP devolve o resultado inline ou salva o arquivo localmente quando o volume for grande.

---

## 5. Decisões de arquitetura recomendadas

### 5.1 Stack

- **Linguagem:** Python 3.11+
- **Protocolo MCP:** SDK Python oficial do MCP
- **AWS SDK:** `boto3`
- **Modelagem/validação:** `pydantic`
- **Persistência local de configuração:** JSON + sistema seguro local para segredos
- **Vetorização/índice local:** `faiss-cpu` ou `chromadb` (preferência: `faiss-cpu` para simplicidade)
- **Embeddings:** provedor configurável, com fallback para índice textual simples
- **Testes:** `pytest`, `pytest-asyncio`
- **Qualidade:** `ruff`, `mypy`, `black`

### 5.2 Diretriz importante sobre segurança

Embora a especificação mencione armazenar chaves de AWS no grupo de configuração, a recomendação é:

- **segredos não devem ficar no S3**;
- `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN` e similares devem ficar somente em armazenamento local seguro;
- no S3 devem ficar apenas configurações não sensíveis e metadados do catálogo.

### 5.3 Execução local

O servidor deve rodar localmente via `stdio`, para uso direto como servidor MCP no VS Code.

---

## 6. Estrutura sugerida do novo repositório

```text
aws-athena-knowledge-mcp/
├── src/
│   └── athena_knowledge_mcp/
│       ├── core/
│       │   ├── config.py
│       │   ├── settings_store.py
│       │   ├── secrets_store.py
│       │   ├── exceptions.py
│       │   └── models.py
│       ├── server/
│       │   ├── app.py
│       │   ├── lifecycle.py
│       │   └── middleware.py
│       ├── handlers/
│       │   ├── onboarding_handlers.py
│       │   ├── catalog_handlers.py
│       │   ├── athena_handlers.py
│       │   └── file_handlers.py
│       ├── services/
│       │   ├── aws_session_service.py
│       │   ├── athena_service.py
│       │   ├── s3_catalog_service.py
│       │   ├── table_skill_service.py
│       │   ├── vector_index_service.py
│       │   ├── onboarding_service.py
│       │   └── result_materialization_service.py
│       ├── repositories/
│       │   ├── local_config_repository.py
│       │   ├── s3_catalog_repository.py
│       │   ├── s3_skill_repository.py
│       │   └── query_history_repository.py
│       ├── utils/
│       │   ├── validators.py
│       │   ├── formatters.py
│       │   ├── prompts.py
│       │   └── paths.py
│       └── __init__.py
├── tests/
│   ├── unit/
│   ├── integration/
│   └── e2e/
├── docs/
│   ├── architecture.md
│   ├── tool-contracts.md
│   └── onboarding.md
├── main.py
├── pyproject.toml
├── README.md
└── .env.example
```

---

## 7. Modelo de dados e armazenamento

## 7.1 Grupo 1: configuração geral + índice resumido

Este grupo representa o “catálogo mestre”.

### Arquivos sugeridos

#### Local

- `state/runtime_settings.json`
- `state/query_history.jsonl`
- `state/vector/catalog.index`
- `state/vector/catalog_metadata.jsonl`
- `downloads/` para resultados grandes

#### S3

- `s3://<bucket>/<prefix>/catalog/catalog_manifest.json`
- `s3://<bucket>/<prefix>/catalog/catalog_index.jsonl`
- `s3://<bucket>/<prefix>/catalog/databases/<database>.json`

### Conteúdo esperado do manifesto

- região AWS
- workgroup Athena
- data source / catalog
- bucket/prefix de saída de queries
- bucket/prefix dos arquivos de catálogo
- pasta local de download para resultados grandes
- política de limiar para inline vs arquivo
- versão do catálogo
- data da última sincronização

### Conteúdo esperado do índice resumido

Cada item deve conter pelo menos:

- `database_name`
- `table_name`
- `summary`
- `business_context`
- `common_use_cases`
- `detail_file_s3_uri`
- `tags`
- `last_updated_at`
- vetor/embedding associado ou chave para índice local

> Observação: o índice vetorial pode ser mantido localmente para performance, com o JSONL no S3 como fonte canônica.

## 7.2 Grupo 2: arquivos detalhados por tabela

Cada tabela terá um arquivo próprio, por exemplo:

- `s3://<bucket>/<prefix>/skills/tables/<database>/<table>.md`
- ou `s3://<bucket>/<prefix>/skills/tables/<database>/<table>.json`

### Estrutura mínima do arquivo detalhado

- nome do database
- nome da tabela
- descrição funcional
- granularidade dos dados
- lista de colunas
- tipo lógico/tipo Athena
- domínio esperado de cada coluna
- chaves principais ou identificadores de negócio
- filtros comuns
- junções comuns
- restrições de uso
- exemplos de perguntas que a tabela responde
- exemplos de SQL
- observações de qualidade dos dados
- owner/responsável, se existir

A recomendação é manter:

- **Markdown** para leitura amigável pela LLM;
- **JSON** opcional para consumo estruturado pelo servidor.

---

## 8. Onboarding inicial obrigatório

## 8.1 Comportamento esperado

Na primeira chamada ao servidor, qualquer ferramenta deve passar por uma checagem de configuração.

Se não houver configuração válida:

- o servidor não executa a operação pedida;
- retorna instrução para chamar a ferramenta de inicialização;
- informa exatamente quais campos faltam.

## 8.2 Ferramenta de inicialização sugerida

### `initialize_server_configuration`

Responsável por receber e validar:

- tipo de autenticação AWS (`profile`, `access_key`, `session_token`, `default_credentials`)
- `aws_region`
- `aws_profile` quando aplicável
- `aws_access_key_id` e `aws_secret_access_key` quando aplicável
- `aws_session_token` quando aplicável
- `athena_workgroup`
- `athena_catalog`
- `default_database`
- `query_results_s3_bucket`
- `query_results_s3_prefix`
- `catalog_bucket`
- `catalog_prefix`
- `local_large_results_folder`
- `inline_result_max_bytes`
- `inline_result_max_rows`

## 8.3 Persistência recomendada

- configurações não sensíveis em arquivo local JSON;
- segredos em keyring/credential manager do sistema operacional;
- opção de exportar/importar configuração sem segredos.

---

## 9. Ferramentas MCP sugeridas

## 9.1 Ferramentas de configuração

1. `initialize_server_configuration`
   - cria a configuração inicial;
   - valida conectividade com Athena e S3.

2. `get_server_configuration_status`
   - informa se o servidor está pronto;
   - lista campos faltantes;
   - mostra última sincronização do catálogo.

3. `update_server_configuration`
   - altera parte da configuração sem refazer tudo.

## 9.2 Ferramentas de catálogo/skills

4. `search_table_catalog`
   - busca no índice vetorial/resumido;
   - retorna tabelas candidatas com descrição curta.

5. `get_table_skill`
   - lê o arquivo detalhado de uma tabela.

6. `create_or_update_table_skill`
   - cria/atualiza o skill detalhado de uma tabela;
   - atualiza resumo no índice vetorial.

7. `refresh_catalog_index`
   - recompõe o índice vetorial a partir dos arquivos do S3.

8. `list_catalog_databases`
   - lista databases conhecidos no catálogo resumido.

## 9.3 Ferramentas de Athena

9. `execute_athena_query`
   - executa SQL genérica;
   - aceita `query`, `database`, `catalog`, `workgroup` e flags de retorno.

10. `get_query_execution_status`
    - retorna status, tempo, localização do resultado e metadados.

11. `fetch_query_result_preview`
    - lê preview do resultado para inspeção rápida.

## 9.4 Ferramentas para resultado grande

12. `materialize_large_result_locally`
    - baixa/copía o arquivo final do S3 para a pasta local configurada;
    - devolve o caminho local.

13. `list_local_result_files`
    - mostra arquivos já materializados localmente.

---

## 10. Fluxo da consulta Athena

## 10.1 Execução padrão

1. Receber SQL.
2. Validar configuração.
3. Enviar query ao Athena.
4. Aguardar finalização.
5. Ler `OutputLocation` da execução.
6. Consultar o S3 para descobrir o tamanho do arquivo gerado.
7. Aplicar a política de resposta.

## 10.2 Política de resposta

### Caso A: resultado pequeno

Critérios sugeridos:

- arquivo no S3 abaixo de um limiar configurável, por exemplo 1 MB;
- e número de linhas retornadas dentro de um limite seguro.

Resposta MCP:

- `query_execution_id`
- metadados da execução
- colunas
- linhas retornadas inline
- caminho S3 do resultado

### Caso B: resultado grande

Critérios sugeridos:

- arquivo acima do limiar configurado;
- ou paginação/leitura inline seria cara para a LLM.

Resposta MCP:

- `query_execution_id`
- tamanho do arquivo
- localização S3
- mensagem informando que o resultado é grande
- instrução para chamar `materialize_large_result_locally`

### Caso C: materialização local

A ferramenta de materialização deve:

- validar a pasta local configurada;
- criar subpastas por data/query id;
- baixar o arquivo do S3;
- opcionalmente gerar `metadata.json` ao lado do arquivo com SQL, timestamp e contexto.

---

## 11. Contrato recomendado para os arquivos de skill

## 11.1 Resumo no índice vetorial

Exemplo de campos lógicos:

```json
{
  "database": "analytics",
  "table": "orders",
  "summary": "Pedidos finalizados e em andamento do e-commerce.",
  "business_context": "Usada para acompanhar volume, ticket médio e status dos pedidos.",
  "common_use_cases": [
    "vendas por período",
    "pedidos por status",
    "análise por canal"
  ],
  "detail_file_s3_uri": "s3://company-bucket/catalog/skills/tables/analytics/orders.md",
  "tags": ["sales", "orders", "ecommerce"]
}
```

## 11.2 Skill detalhado por tabela

Exemplo de seções:

- objetivo da tabela;
- quando usar;
- quando não usar;
- colunas principais;
- filtros típicos;
- joins frequentes;
- armadilhas comuns;
- exemplos de perguntas respondidas;
- exemplos de SQL válidas.

---

## 12. Serviços internos recomendados

### `OnboardingService`
- detecta ausência de configuração;
- valida credenciais e conectividade.

### `AwsSessionService`
- cria sessão `boto3` para Athena e S3;
- suporta `profile`, `access_key` e credenciais padrão.

### `AthenaService`
- executa query;
- consulta status;
- localiza arquivo de saída.

### `S3CatalogService`
- lê e grava manifesto e índice resumido;
- busca arquivos de skill.

### `TableSkillService`
- cria/atualiza skill detalhado;
- atualiza resumo do índice.

### `VectorIndexService`
- monta índice local a partir do JSONL do S3;
- faz busca semântica por tabela/assunto.

### `ResultMaterializationService`
- avalia tamanho do resultado;
- baixa arquivo do S3 para pasta local.

---

## 13. Regras de negócio importantes

1. O servidor não deve executar nenhuma operação de negócio antes da configuração inicial.
2. Toda consulta Athena deve registrar `query_execution_id`.
3. O tamanho do resultado deve ser decidido com base no arquivo efetivamente gerado no S3.
4. O skill detalhado deve ter um identificador estável por `database.table`.
5. Atualizar skill detalhado deve sempre atualizar o resumo correspondente no índice.
6. O retorno inline deve ser limitado para não saturar o contexto da LLM.
7. Os caminhos locais devem ser normalizados para Windows, já que o uso principal será no VS Code local.

---

## 14. Plano de implementação por fases

## Fase 1 — Fundação do repositório

- criar estrutura base do projeto;
- configurar `pyproject.toml`, testes e lint;
- implementar servidor MCP básico;
- implementar modelos e configuração central.

## Fase 2 — Onboarding e persistência

- implementar `initialize_server_configuration`;
- salvar configurações locais;
- integrar armazenamento seguro de segredos;
- validar acesso ao Athena e ao S3.

## Fase 3 — Athena genérico

- implementar `execute_athena_query`;
- monitorar status;
- devolver preview inline.

## Fase 4 — Catálogo resumido + skills

- criar manifesto de catálogo;
- criar leitura/escrita de skills no S3;
- implementar `create_or_update_table_skill`;
- implementar `get_table_skill`.

## Fase 5 — Busca vetorial

- gerar embeddings do catálogo resumido;
- criar índice local;
- implementar `search_table_catalog`.

## Fase 6 — Resultado grande

- medir tamanho do arquivo no S3;
- implementar política inline vs arquivo;
- implementar `materialize_large_result_locally`.

## Fase 7 — Robustez

- testes unitários;
- testes integrados com AWS mockado;
- logs estruturados;
- documentação final.

---

## 15. Critérios de aceite

O novo repositório estará pronto quando:

- o primeiro acesso exigir configuração inicial;
- a configuração ficar persistida para chamadas futuras;
- a LLM conseguir buscar tabelas por resumo;
- a LLM conseguir ler um skill detalhado por tabela;
- o servidor conseguir executar query genérica no Athena;
- resultados pequenos voltarem inline;
- resultados grandes puderem ser baixados para pasta local;
- a atualização de um skill também atualizar o índice resumido;
- o uso via GitHub Copilot Chat no VS Code funcionar localmente.

---

## 16. Riscos e mitigação

### Risco 1: armazenar segredos de forma insegura
**Mitigação:** usar keyring/credential manager local e não salvar segredos em S3.

### Risco 2: índice vetorial ficar inconsistente com os skills
**Mitigação:** toda atualização de skill dispara atualização do item resumido e reindexação incremental.

### Risco 3: resultados muito grandes degradarem o contexto da LLM
**Mitigação:** retorno inline com limites rígidos e materialização local via ferramenta separada.

### Risco 4: múltiplos ambientes AWS
**Mitigação:** suportar perfis/configurações nomeadas no futuro, iniciando com um perfil ativo.

---

## 17. Sugestão de nome do repositório

Opções objetivas:

- `aws-athena-knowledge-mcp`
- `athena-s3-skills-mcp`
- `athena-local-mcp-server`
- `copilot-athena-catalog-mcp`

Minha sugestão principal: `aws-athena-knowledge-mcp`.

---

## 18. Próximo passo recomendado

Depois deste plano, o próximo passo ideal é criar um **MVP do novo repositório** com:

1. servidor MCP local;
2. onboarding inicial;
3. execução genérica de query Athena;
4. leitura/gravação do catálogo resumido no S3;
5. criação e leitura de skill detalhado por tabela;
6. tratamento de resultado pequeno/grande.
