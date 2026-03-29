from __future__ import annotations

import json
from pathlib import Path

from athena_knowledge_mcp.core.models import ServerConfiguration


class SettingsStore:
    def __init__(self, file_path: Path) -> None:
        self._file_path = file_path

    @property
    def file_path(self) -> Path:
        return self._file_path

    def exists(self) -> bool:
        return self._file_path.exists()

    def load(self) -> ServerConfiguration | None:
        if not self.exists():
            return None
        raw_data = json.loads(self._file_path.read_text(encoding="utf-8"))
        return ServerConfiguration.model_validate(raw_data)

    def save(self, configuration: ServerConfiguration) -> None:
        self._file_path.parent.mkdir(parents=True, exist_ok=True)
        payload = configuration.model_dump(mode="json")
        self._file_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
