from __future__ import annotations

import json
from pathlib import Path

from athena_knowledge_mcp.core.models import AwsSecretMaterial


class SecretsStore:
    def __init__(self, file_path: Path) -> None:
        self._file_path = file_path

    def load(self) -> AwsSecretMaterial:
        if not self._file_path.exists():
            return AwsSecretMaterial()
        raw_data = json.loads(self._file_path.read_text(encoding="utf-8"))
        return AwsSecretMaterial.model_validate(raw_data)

    def save(self, secrets: AwsSecretMaterial) -> None:
        self._file_path.parent.mkdir(parents=True, exist_ok=True)
        payload = secrets.model_dump(mode="json", exclude_none=True)
        self._file_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
