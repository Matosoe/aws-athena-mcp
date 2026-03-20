from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from athena_knowledge_mcp.core.aws_errors import raise_if_aws_access_denied
from athena_knowledge_mcp.core.models import MaterializedResult, QueryExecutionRecord
from athena_knowledge_mcp.services.athena_service import AthenaService


@dataclass(slots=True)
class ResultMaterializationService:
    athena_service: AthenaService
    s3_client: Any | None = None

    def materialize(self, record: QueryExecutionRecord, target_folder: Path) -> MaterializedResult:
        target_folder.mkdir(parents=True, exist_ok=True)
        local_path = target_folder / f"{record.query_execution_id}.csv"

        if self.s3_client is None or not record.output_location:
            local_path.write_bytes(self.athena_service.build_stub_csv(record))
        else:
            bucket, key = self._split_s3_uri(record.output_location)
            try:
                self.s3_client.download_file(bucket, key, str(local_path))
            except Exception as exc:
                raise_if_aws_access_denied(exc, "S3")
                raise

        metadata_path = target_folder / f"{record.query_execution_id}.metadata.json"
        metadata_path.write_text(
            json.dumps(record.model_dump(mode="json"), indent=2),
            encoding="utf-8",
        )
        return MaterializedResult(
            query_execution_id=record.query_execution_id,
            local_path=local_path,
            source_s3_uri=record.output_location or "local://stub",
            size_bytes=local_path.stat().st_size,
        )

    def list_materialized_files(self, target_folder: Path) -> list[str]:
        target_folder.mkdir(parents=True, exist_ok=True)
        return sorted(path.name for path in target_folder.iterdir() if path.is_file())

    def _split_s3_uri(self, value: str) -> tuple[str, str]:
        without_prefix = value[5:]
        bucket, _, key = without_prefix.partition("/")
        return bucket, key