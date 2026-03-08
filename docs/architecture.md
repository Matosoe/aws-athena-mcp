# Arquitetura minima do MVP

## Fluxo principal

1. O cliente MCP inicia o servidor local via stdio.
2. O servidor registra tools de onboarding, catalogo, skill e Athena.
3. Cada tool consulta o estado persistido em state/runtime_settings.json.
4. Quando a configuracao existe, os handlers constroem os services necessarios para a operacao.
5. O catalogo e as skills usam repositories dedicados para S3 ou fallback local em testes.
6. A camada Athena decide entre preview inline e materializacao local a partir do tamanho final do resultado.

## Camadas

- core: modelos, excecoes e persistencia basica.
- repositories: acesso a configuracao local, historico, catalogo e skills.
- services: regras de negocio e integracao com AWS.
- handlers: adaptadores entre tools MCP e services.
- server: bootstrap do MCP e montagem das dependencias.

## Observacoes do MVP

- a busca no catalogo e textual, sem indice vetorial;
- o armazenamento de segredos permanece local para esta primeira versao;
- existe fallback controlado para execucao local de testes sem AWS real.