# Politica de Versionamento

Este projeto adota Semantic Versioning (SemVer) no formato `MAJOR.MINOR.PATCH`.

## Regras SemVer

- `MAJOR`: alteracoes incompativeis com versoes anteriores (quebra de contrato de tool, mudanca de comportamento sem compatibilidade, remocao de campos esperados).
- `MINOR`: novas funcionalidades compativeis (novas tools, novos campos opcionais, melhorias sem quebra).
- `PATCH`: correcao de bugs e ajustes internos sem alteracao de contrato publico.

## Fonte de versao oficial

A versao oficial do repositorio fica em `pyproject.toml`, no campo `project.version`.

## Politica para build do executavel

Todo build Windows deve ser feito por `scripts/build_windows_exe.py`.

O script gera:

- executavel estavel: `dist/aws-athena-mcp-latest.exe`
- metadados do ultimo build: `dist/LATEST_BUILD.txt`

## Processo de release

1. Atualizar `project.version` no `pyproject.toml` conforme impacto da mudanca.
2. Atualizar changelog/release notes da entrega.
3. Executar build via script `scripts/build_windows_exe.py`.
4. Publicar `dist/aws-athena-mcp-latest.exe`.
5. Se precisar rastreabilidade adicional de release, use a versao de `pyproject.toml` e o conteudo de `dist/LATEST_BUILD.txt`.

## Compatibilidade

Sempre que houver incremento de `MAJOR`, registrar explicitamente migracoes necessarias no README ou em documento de migracao.
