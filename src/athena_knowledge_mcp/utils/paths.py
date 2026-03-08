from __future__ import annotations

from pathlib import Path


def normalize_local_path(value: str | Path) -> Path:
    return Path(value).expanduser().resolve()
