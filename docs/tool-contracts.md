# Contratos das tools do MVP

## initialize_server_configuration

Salva a configuracao inicial do servidor.

Entradas principais:

- authentication_type
- aws_region
- athena_workgroup
- athena_catalog
- default_database
- query_results_s3_bucket
- query_results_s3_prefix
- catalog_bucket
- catalog_prefix
- local_large_results_folder
- inline_result_max_bytes
- inline_result_max_rows
- aws_profile ou chaves AWS quando aplicavel

Saida:

- status configurado
- mensagem de sucesso

## get_server_configuration_status

Informa se a configuracao minima existe e quais campos faltam.

## update_server_configuration

Atualiza parcialmente a configuracao persistida.

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

Lista perfis encontrados nos arquivos locais da AWS CLI para o usuario escolher antes do login.

Saida:

- lista de nomes de profile.

## aws_sso_login

Executa o login SSO da AWS CLI para o profile escolhido em fluxo interativo de navegador.

Entradas:

- profile
- timeout_seconds opcional

Saida:

- success, exit_code, stdout, stderr e command
- profile usado no login
- verification_url retornada pela AWS CLI
- user_code para fallback manual
- browser_opened indicando se o navegador padrao foi acionado

Observacao:

- o fluxo recomendado continua sendo listar os profiles primeiro, deixar o usuario escolher um deles e entao chamar `aws_sso_login`.

## list_athena_databases

Lista os databases diretamente no Athena via `SHOW DATABASES`, sem usar merge com o indice do catalogo.

Observacao:

- quando o usuario ja souber o database, prefira pedir o nome digitado e seguir direto para `list_athena_tables` ou `get_athena_table_metadata`.

Entradas:

- catalog opcional

Saida:

- lista com name e sources.

## list_athena_tables

Lista as tabelas de um database diretamente no Athena via `SHOW TABLES IN <database>`, sem usar merge com o indice do catalogo.

Entradas:

- database_name
- catalog opcional
- name_prefix opcional para filtrar por prefixo no resultado da query

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