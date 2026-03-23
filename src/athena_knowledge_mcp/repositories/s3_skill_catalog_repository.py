from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from athena_knowledge_mcp.core.models import SkillCatalogEntry


class S3SkillCatalogRepository:
    def __init__(
        self,
        bucket: str,
        prefix: str,
        s3_client: Any | None = None,
        local_root: Path | None = None,
    ) -> None:
        self._bucket = bucket
        self._prefix = prefix.strip("/")
        self._s3_client = s3_client
        self._local_root = local_root

    def load_entries(self) -> list[SkillCatalogEntry]:
        if self._local_root is not None:
            file_path = self._local_root / "skill_index.jsonl"
            if not file_path.exists():
                return []
            return [
                SkillCatalogEntry.model_validate_json(line)
                for line in file_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]

        if self._s3_client is None:
            raise RuntimeError("S3 client nao configurado")
        try:
            response = self._s3_client.get_object(
                Bucket=self._bucket,
                Key=self._catalog_key(),
            )
        except Exception as exc:
            if self._is_missing_key_error(exc):
                return []
            raise
        body = response["Body"].read().decode("utf-8")
        return [
            SkillCatalogEntry.model_validate_json(line)
            for line in body.splitlines()
            if line.strip()
        ]

    def save_entries(self, entries: list[SkillCatalogEntry]) -> None:
        payload = "\n".join(json.dumps(item.model_dump(mode="json")) for item in entries)
        if self._local_root is not None:
            self._local_root.mkdir(parents=True, exist_ok=True)
            (self._local_root / "skill_index.jsonl").write_text(payload, encoding="utf-8")
            return

        if self._s3_client is None:
            raise RuntimeError("S3 client nao configurado")
        self._s3_client.put_object(
            Bucket=self._bucket,
            Key=self._catalog_key(),
            Body=payload.encode("utf-8"),
        )

    def _catalog_key(self) -> str:
        if not self._prefix:
            return "skill_catalog/skill_index.jsonl"
        return f"{self._prefix}/skill_catalog/skill_index.jsonl"

    @staticmethod
    def _is_missing_key_error(exc: Exception) -> bool:
        response = getattr(exc, "response", None)
        if not isinstance(response, dict):
            return False
        error = response.get("Error")
        if not isinstance(error, dict):
            return False
        return error.get("Code") in {"NoSuchKey", "404", "NotFound"}
