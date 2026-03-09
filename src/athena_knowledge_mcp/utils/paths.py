from __future__ import annotations

import os
import sys
from pathlib import Path


RUNTIME_HOME_ENV_VAR = "ATHENA_MCP_HOME"


def normalize_local_path(value: str | Path) -> Path:
    return Path(value).expanduser().resolve()


def resolve_runtime_home() -> Path:
    configured_home = os.getenv(RUNTIME_HOME_ENV_VAR)
    if configured_home:
        return normalize_local_path(configured_home)
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path.cwd().resolve()


def resolve_runtime_path(value: str | Path, *, base_dir: Path | None = None) -> Path:
    path = Path(value).expanduser()
    if path.is_absolute():
        return path.resolve()
    root = resolve_runtime_home() if base_dir is None else normalize_local_path(base_dir)
    return (root / path).resolve()
