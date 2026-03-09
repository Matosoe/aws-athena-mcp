from pathlib import Path

from athena_knowledge_mcp.utils.paths import resolve_runtime_path


def test_resolve_runtime_path_uses_runtime_home_for_relative_path(
    monkeypatch,
    tmp_path: Path,
) -> None:
    runtime_home = tmp_path / "runtime-home"
    monkeypatch.setenv("ATHENA_MCP_HOME", str(runtime_home))

    resolved = resolve_runtime_path("downloads")

    assert resolved == runtime_home / "downloads"


def test_resolve_runtime_path_preserves_absolute_path(tmp_path: Path) -> None:
    absolute_path = (tmp_path / "downloads").resolve()

    resolved = resolve_runtime_path(absolute_path)

    assert resolved == absolute_path