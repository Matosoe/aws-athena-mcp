# Plano de execucao do MVP

Este plano operacionaliza o escopo descrito em PLANO_NOVO_PROJETO_MCP_ATHENA_S3.md em passos pequenos, com validacao ao fim de cada etapa.

## Etapa 1 - Fundacao do servidor

- montar o bootstrap MCP em stdio;
- registrar as ferramentas principais;
- organizar container, handlers, services e repositories.

Validacao:

- checagem estrutural do projeto;
- validacao de erros do editor;
- execucao de testes unitarios do nucleo quando o Python global estiver disponivel.

## Etapa 2 - Configuracao e onboarding

- persistir configuracoes locais;
- persistir segredos localmente para o MVP;
- validar campos obrigatorios;
- expor initialize_server_configuration, get_server_configuration_status e update_server_configuration.

Validacao:

- testes unitarios de persistencia e servico de onboarding;
- leitura da configuracao salva e recalculo do status.

## Etapa 3 - Catalogo e skill de tabela

- carregar e salvar catalogo resumido;
- implementar busca textual simples por tabela;
- ler e atualizar skills detalhados;
- sincronizar o resumo do catalogo quando uma skill for alterada.

Validacao:

- testes unitarios de busca e leitura/escrita de skill;
- verificacao de consistencia entre skill e indice resumido.

## Etapa 4 - Athena e resultado grande

- executar query no Athena quando houver cliente AWS disponivel;
- usar fallback local para o MVP quando nao houver cliente AWS em testes;
- decidir entre preview inline e materializacao local;
- expor status, preview, materializacao e listagem de downloads.

Validacao:

- testes unitarios da politica inline versus resultado grande;
- validacao estrutural dos handlers e services.

## Etapa 5 - Documentacao operacional

- descrever arquitetura minima;
- documentar contratos das tools;
- manter README alinhado ao escopo real da primeira versao.

Validacao:

- revisao da coerencia entre README, contratos e tools registradas.