# Contratos das tools do MVP

## initialize_server_configuration

Salva a configuracao inicial do servidor.

Entradas principais:

- authentication_type
- aws_region
- athena_workgroup
- athena_catalog
- athena_databases opcional
- default_database opcional
- query_results_s3_bucket
- query_results_s3_prefix
- catalog_bucket
- catalog_prefix
- local_large_results_folder
- inline_result_max_bytes
- inline_result_max_rows
- aws_profile ou chaves AWS quando aplicavel

Observacao:

- quando o bucket ainda nao estiver definido, prefira listar os buckets acessiveis e pedir para o usuario escolher um da lista;
- o prefixo padrao sugerido para resultados e catalogo deve ser `mcp/athena/`, so pedindo digitacao manual quando o usuario quiser um prefixo personalizado.
- no onboarding interativo, faca uma pergunta por vez;
- nao junte regiao AWS, workgroup e databases na mesma pergunta;
- nao exija database padrao; se precisar registrar contexto, peca apenas uma lista opcional de databases em pergunta separada.

Saida:

- status configurado
- mensagem de sucesso

## get_server_configuration_status

Informa se a configuracao minima existe e quais campos faltam.

Saida adicional quando storage estiver incompleto:

- storage_selection_required
- storage_missing_fields
- available_s3_buckets quando a AWS puder ser consultada
- recommended_s3_prefix
- next_step

## list_accessible_s3_buckets

Lista os buckets S3 acessiveis com as credenciais AWS atuais para o fluxo de onboarding.

Saida:

- buckets
- recommended_prefix com valor `mcp/athena/`
- requires_bucket_selection
- message
- next_step

## update_server_configuration

Atualiza parcialmente a configuracao persistida.

Observacao:

- quando o bucket ainda nao estiver definido, prefira listar os buckets acessiveis e pedir para o usuario escolher um da lista;
- se o prefixo vier vazio, o servidor normaliza para `mcp/athena/`.

## search_table_catalog

Busca tabelas no indice resumido por termos textuais.

Saida:

- lista de itens com database_name, table_name, summary, tags e detail_file_s3_uri.

## get_table_skill

Retorna o markdown detalhado da tabela solicitada.

## create_or_update_table_skill

Persiste uma skill detalhada e sincroniza o resumo correspondente no catalogo.

## refresh_catalog_index

Recarrega o catalogo canonicamente armazenado e informa a quantidade de entradas.

## list_catalog_databases

Lista os databases conhecidos no catalogo.

## list_catalog_tables

Lista as tabelas conhecidas no indice do catalogo para um database especifico.

Entradas:

- database_name

Saida:

- lista de itens do indice com database_name, table_name, summary, tags e detail_file_s3_uri.

## list_aws_cli_profiles

Lista os perfis encontrados localmente nos arquivos do AWS CLI.

Saida:

- lista de nomes de perfil.

## aws_sso_login

Inicia `aws sso login` para um perfil especifico sem bloquear a tool.

Comportamento esperado:

- o AWS CLI deve tentar abrir o navegador padrao para o usuario aprovar o login;
- a tool retorna imediatamente com status de aguardando confirmacao do usuario;
- depois disso, o agente deve pedir ao usuario para confirmar que aprovou o login no navegador antes de seguir.

Entradas:

- profile
- timeout_seconds mantido apenas por compatibilidade da interface

Saida:

- success
- command
- status igual a `pending_user_confirmation`
- requires_user_confirmation igual a `true`
- next_step orientando o agente a pedir confirmacao ao usuario

## aws_sts_get_caller_identity

Valida a identidade AWS ativa usando AWS CLI.

Entradas:

- profile opcional

Saida:

- success
- identity quando o retorno JSON for valido

## list_athena_databases

Lista os databases diretamente no Athena, sem usar merge com o indice do catalogo.

Observacao:

- em ambientes com IAM restrito, essa tool pode falhar com access denied;
- quando o usuario ja souber o database, prefira pedir o nome digitado e seguir direto para `list_athena_tables` ou `get_athena_table_metadata`.

Entradas:

- catalog opcional

Saida:

- lista com name e sources.

## list_athena_tables

Lista as tabelas de um database diretamente no Athena, sem usar merge com o indice do catalogo.

Entradas:

- database_name
- catalog opcional
- name_prefix opcional para filtrar por prefixo

Saida:

- lista com database_name, table_name e sources.

## get_athena_table_metadata

Retorna as propriedades de uma tabela diretamente do Athena, derivando colunas, particoes e parametros a partir de `SHOW CREATE TABLE <nome_da_tabela>` executado no database informado.

Entradas:

- database_name
- table_name
- catalog opcional

Saida:

- database_name, table_name, catalog
- columns e partition_keys
- table_type e parameters
- sources

## sync_athena_database_to_catalog

Sincroniza tabelas de um database do Athena para o catalogo S3, gerando skills basicas automaticamente para enriquecer o indice.

Entradas:

- database_name
- catalog opcional
- name_prefix opcional para limitar o conjunto sincronizado
- max_tables opcional para limitar a quantidade processada
- overwrite_existing para substituir entradas ja existentes

Saida:

- database_name
- synced_tables e skipped_tables
- synced_count e skipped_count

## execute_athena_query

Executa uma SQL no Athena ou usa fallback local controlado para o MVP.

Saida:

- query_execution_id
- status
- output_location
- preview inline quando pequeno
- next_step quando o resultado for grande

Observacao:

- a tool aceita qualquer SQL suportada pelo Athena, incluindo consultas de descoberta como SHOW DATABASES, SHOW TABLES e DESCRIBE.

## get_query_execution_status

Consulta o estado persistido de uma execucao.

## fetch_query_result_preview

Retorna preview do resultado quando disponivel.

## materialize_large_result_locally

Baixa ou gera localmente o resultado final para a pasta configurada.

## list_local_result_files

Lista arquivos materializados localmente.