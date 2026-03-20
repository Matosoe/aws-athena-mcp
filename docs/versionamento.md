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

No fluxo padrao do repositorio, o ponto de entrada deve ser `scripts\build_windows_exe.cmd`, que recria a `.venv` se necessario com Python 3.11 ou 3.12 e depois chama `scripts/build_windows_exe.py`.

O script gera:

- artefato versionado: `dist/aws-athena-mcp-v<versao>-<yyyymmdd-HHMMSS>.exe`
- alias estavel: `dist/aws-athena-mcp-latest.exe`
- metadados do ultimo build: `dist/LATEST_BUILD.txt`

Exemplo de artefato versionado:

`aws-athena-mcp-v0.1.0-20260311-154500.exe`

## Processo de release

1. Atualizar `project.version` no `pyproject.toml` conforme impacto da mudanca.
2. Atualizar changelog/release notes da entrega.
3. Executar build via `scripts\build_windows_exe.cmd`.
4. Publicar o artefato versionado gerado em `dist/`.
5. Usar `aws-athena-mcp-latest.exe` apenas como atalho local para desenvolvimento/execucao.

## Compatibilidade

Sempre que houver incremento de `MAJOR`, registrar explicitamente migracoes necessarias no README ou em documento de migracao.
