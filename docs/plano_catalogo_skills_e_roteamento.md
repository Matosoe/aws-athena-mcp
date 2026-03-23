# Plano 2: Catalogo de Skills + Roteamento Catalogo-Primeiro

**Branch:** `feature/reduce-initial-config-scope`  
**Data:** 2026-03-23  
**Motivacao:** Durante comandos em linguagem natural, o agente passou a usar varredura direta no Athena (SHOW DATABASES/SHOW TABLES) antes de usar conhecimento ja indexado. Isso aumenta latencia e custo, e piora UX quando a resposta ja existe como skill.

---

## 1. Objetivo

1. Criar uma segunda estrutura de catalogo dedicada a skills, separada do catalogo de tabelas.
2. Priorizar busca em indices locais/S3 (catalogo de tabelas ou catalogo de skills) antes de chamar varredura no Athena.
3. Introduzir roteamento explicito para orientar o agente:
   - Se o usuario mencionar database/tabela: priorizar indice de tabelas.
   - Se o usuario fizer pedido sem contexto tecnico (db/tabela): priorizar indice de skills.
   - So usar varredura no Athena quando os indices nao trouxerem contexto suficiente.

---

## 2. Problema Atual

- Existe apenas indice de catalogo por tabela (`catalog_index.jsonl`).
- Skills detalhadas existem como markdown por tabela, mas sem indice dedicado por habilidade/tema.
- O agente pode escolher tools de descoberta no Athena cedo demais, gerando varredura lenta.

---

## 3. Solucao Proposta

### 3.1 Novo indice de skills

Criar `skill_index.jsonl` com metadados de skill orientados a busca sem depender de db/tabela como ponto de entrada.

Estrutura sugerida por entrada:

- `skill_id`: identificador estavel (ex.: `analytics.orders`)
- `title`: nome amigavel da skill (usa `description` atual como titulo)
- `summary`
- `tags`
- `database_name` (opcional para contexto)
- `table_name` (opcional para contexto)
- `detail_file_s3_uri`
- `last_updated_at`

### 3.2 Servico dedicado de skill catalog

Adicionar camada de servico com operacoes:

- `search(query, limit)`
- `list_skills()`
- `get_entry(skill_id)`
- `upsert_entry(entry)`
- `refresh_index()`

### 3.3 Integracao no fluxo de escrita de skill

Ao executar `create_or_update_table_skill`:

1. Persistir markdown da skill (como hoje).
2. Atualizar catalogo de tabelas (como hoje).
3. Atualizar tambem catalogo de skills (novo passo).

### 3.4 Novas tools MCP para skill-first

Adicionar tools:

- `search_skill_catalog(query, limit=5)`
- `list_catalog_skills()`

Adicionar tool de roteamento:

- `route_user_request_context(user_request, database_name=None, table_name=None, limit=5)`

Saida da tool de roteamento:

- `route`: `table_catalog` ou `skill_catalog`
- `reason`
- `table_matches`
- `skill_matches`
- `should_scan_athena` (default `false`)
- `next_recommended_tools`

### 3.5 Politica catalogo-primeiro

Atualizar descricoes das tools para orientar explicitamente:

- Use primeiro `search_table_catalog`, `search_skill_catalog` e `route_user_request_context`.
- Use `list_athena_databases` / `list_athena_tables` apenas quando os indices nao forem suficientes.

---

## 4. Impacto por Camada

### core

- `models.py`: adicionar `SkillCatalogEntry`.

### repositories

- Novo `s3_skill_catalog_repository.py` para `skill_index.jsonl`.

### services

- Novo `skill_catalog_service.py`.
- `table_skill_service.py`: atualizar para sincronizar tambem o indice de skills.
- Novo `request_routing_service.py` para decidir rota por heuristica simples.

### handlers

- `catalog_handlers.py`: expor busca/listagem de skills.
- Novo `routing_handlers.py`: expor roteamento.
- `file_handlers.py`: continuar recebendo create/update, agora refletindo nos dois indices.

### server

- `app.py`: registrar novas tools e reforcar descricoes catalogo-primeiro.

### tests

- `test_catalog_and_skill_service.py`: cobrir sincronizacao do skill index e busca de skills.
- Novo `test_request_routing_service.py`: cobrir heuristicas e fallback.

---

## 5. Sequencia de Execucao

1. Criar `SkillCatalogEntry` e repositorio de indice de skills.
2. Criar `SkillCatalogService`.
3. Integrar `TableSkillService` para atualizar ambos os indices.
4. Expor handlers e tools de busca/listagem de skills.
5. Criar `RequestRoutingService` + tool `route_user_request_context`.
6. Atualizar descricoes das tools de Athena para catalogo-primeiro.
7. Atualizar testes e validar com pytest.

---

## 6. Resultado Esperado

- Menos chamadas de descoberta no Athena.
- Menor latencia para perguntas em linguagem natural.
- Melhor UX para usuarios que descrevem necessidade por habilidade de negocio (skill) em vez de nome tecnico de tabela.
- Fluxo de consulta mais deterministico e previsivel para o agente.
