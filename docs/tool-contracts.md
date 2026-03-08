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

## execute_athena_query

Executa uma SQL no Athena ou usa fallback local controlado para o MVP.

Saida:

- query_execution_id
- status
- output_location
- preview inline quando pequeno
- next_step quando o resultado for grande

## get_query_execution_status

Consulta o estado persistido de uma execucao.

## fetch_query_result_preview

Retorna preview do resultado quando disponivel.

## materialize_large_result_locally

Baixa ou gera localmente o resultado final para a pasta configurada.

## list_local_result_files

Lista arquivos materializados localmente.