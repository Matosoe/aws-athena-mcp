from __future__ import annotations

import json
from pathlib import Path

from athena_knowledge_mcp.core.models import QueryExecutionRecord


class QueryHistoryRepository:
    def __init__(self, file_path: Path) -> None:
        self._file_path = file_path

    def append(self, record: QueryExecutionRecord) -> None:
        self._file_path.parent.mkdir(parents=True, exist_ok=True)
        with self._file_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record.model_dump(mode="json"), ensure_ascii=True) + "\n")

    def list_all(self) -> list[QueryExecutionRecord]:
        if not self._file_path.exists():
            return []
        records: list[QueryExecutionRecord] = []
        for line in self._file_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            records.append(QueryExecutionRecord.model_validate_json(line))
        return records

    def get(self, query_execution_id: str) -> QueryExecutionRecord | None:
        for record in reversed(self.list_all()):
            if record.query_execution_id == query_execution_id:
                return record
        return None