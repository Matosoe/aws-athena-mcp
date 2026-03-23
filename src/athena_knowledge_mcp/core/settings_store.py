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
        # Migracao do formato antigo: descartar campos de infraestrutura que
        # agora sao definidos em company_defaults.py e nao pelo usuario.
        _LEGACY_INFRA_FIELDS = {
            "authentication_type",
            "aws_region",
            "athena_workgroup",
            "athena_catalog",
            "query_results_s3_bucket",
            "query_results_s3_prefix",
            "catalog_bucket",
            "catalog_prefix",
        }
        if any(field in raw_data for field in _LEGACY_INFRA_FIELDS):
            raw_data = {
                key: value
                for key, value in raw_data.items()
                if key not in _LEGACY_INFRA_FIELDS
            }
        return ServerConfiguration.model_validate(raw_data)

    def save(self, configuration: ServerConfiguration) -> None:
        self._file_path.parent.mkdir(parents=True, exist_ok=True)
        payload = configuration.model_dump(mode="json")
        self._file_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
