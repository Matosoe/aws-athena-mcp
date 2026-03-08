from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from time import sleep
from typing import Any
from uuid import uuid4

from athena_knowledge_mcp.core.exceptions import QueryExecutionError
from athena_knowledge_mcp.core.models import (
    AthenaQueryRequest,
    QueryExecutionRecord,
    QueryResultPreview,
    ServerConfiguration,
)
from athena_knowledge_mcp.repositories.query_history_repository import QueryHistoryRepository
from athena_knowledge_mcp.utils.formatters import format_large_result_message


@dataclass(slots=True)
class AthenaService:
    history_repository: QueryHistoryRepository
    athena_client: Any | None = None
    s3_client: Any | None = None

    def execute_query(
        self,
        request: AthenaQueryRequest,
        configuration: ServerConfiguration,
    ) -> QueryExecutionRecord:
        if self.athena_client is None or self.s3_client is None:
            record = self._execute_stub(request, configuration)
        else:
            record = self._execute_remote(request, configuration)
        self.history_repository.append(record)
        return record

    def get_query_status(self, query_execution_id: str) -> QueryExecutionRecord:
        record = self.history_repository.get(query_execution_id)
        if record is None:
            raise QueryExecutionError(f"Execucao {query_execution_id} nao encontrada")
        return record

    def fetch_result_preview(self, query_execution_id: str) -> QueryResultPreview:
        record = self.get_query_status(query_execution_id)
        if record.preview is None:
            raise QueryExecutionError("Preview indisponivel para esta execucao")
        return record.preview

    def _execute_stub(
        self,
        request: AthenaQueryRequest,
        configuration: ServerConfiguration,
    ) -> QueryExecutionRecord:
        query_execution_id = f"stub-{uuid4().hex[:12]}"
        lower_query = request.query.lower()
        result_size_bytes = 2_000_000 if "large_result" in lower_query else 256
        preview = None
        next_step = None
        completion_reason = None
        if result_size_bytes <= configuration.inline_result_max_bytes:
            preview = QueryResultPreview(
                columns=["example_column", "query_excerpt"],
                rows=[["ok", request.query[:80]]],
                row_count=1,
            )
        else:
            next_step = "materialize_large_result_locally"
            completion_reason = format_large_result_message(
                QueryExecutionRecord(
                    query_execution_id=query_execution_id,
                    status="SUCCEEDED",
                    submitted_query=request.query,
                    database=request.database or configuration.default_database,
                    catalog=request.catalog or configuration.athena_catalog,
                    workgroup=request.workgroup or configuration.athena_workgroup,
                    output_location=(
                        f"s3://{configuration.query_results_s3_bucket}/"
                        f"{configuration.query_results_s3_prefix.strip('/')}/{query_execution_id}.csv"
                    ),
                    result_size_bytes=result_size_bytes,
                )
            )

        return QueryExecutionRecord(
            query_execution_id=query_execution_id,
            status="SUCCEEDED",
            submitted_query=request.query,
            database=request.database or configuration.default_database,
            catalog=request.catalog or configuration.athena_catalog,
            workgroup=request.workgroup or configuration.athena_workgroup,
            output_location=(
                f"s3://{configuration.query_results_s3_bucket}/"
                f"{configuration.query_results_s3_prefix.strip('/')}/{query_execution_id}.csv"
            ),
            result_size_bytes=result_size_bytes,
            completion_reason=completion_reason,
            execution_time_ms=50,
            preview=preview,
            next_step=next_step,
        )

    def _execute_remote(
        self,
        request: AthenaQueryRequest,
        configuration: ServerConfiguration,
    ) -> QueryExecutionRecord:
        assert self.athena_client is not None
        response: dict[str, Any] = self.athena_client.start_query_execution(
            QueryString=request.query,
            QueryExecutionContext={
                "Database": request.database or configuration.default_database,
                "Catalog": request.catalog or configuration.athena_catalog,
            },
            WorkGroup=request.workgroup or configuration.athena_workgroup,
            ResultConfiguration={
                "OutputLocation": (
                    f"s3://{configuration.query_results_s3_bucket}/"
                    f"{configuration.query_results_s3_prefix.strip('/')}"
                )
            },
        )
        query_execution_id = response["QueryExecutionId"]
        status_response = self._wait_for_completion(
            query_execution_id,
            request.max_wait_seconds,
        )
        query_execution = status_response["QueryExecution"]
        status = query_execution["Status"]["State"]
        output_location = query_execution["ResultConfiguration"].get("OutputLocation")
        execution_time_ms = query_execution.get("Statistics", {}).get("EngineExecutionTimeInMillis")

        if status != "SUCCEEDED":
            raise QueryExecutionError(
                query_execution["Status"].get("StateChangeReason", "Falha na query")
            )

        result_size_bytes = self._head_result_size(output_location) if output_location else None
        preview = None
        next_step = None
        completion_reason = None
        if (
            result_size_bytes is not None
            and result_size_bytes <= configuration.inline_result_max_bytes
        ):
            preview = self._load_preview(query_execution_id, configuration.inline_result_max_rows)
        else:
            next_step = "materialize_large_result_locally"
            completion_reason = format_large_result_message(
                QueryExecutionRecord(
                    query_execution_id=query_execution_id,
                    status=status,
                    submitted_query=request.query,
                    database=request.database or configuration.default_database,
                    catalog=request.catalog or configuration.athena_catalog,
                    workgroup=request.workgroup or configuration.athena_workgroup,
                    output_location=output_location,
                    result_size_bytes=result_size_bytes,
                )
            )

        return QueryExecutionRecord(
            query_execution_id=query_execution_id,
            status=status,
            submitted_query=request.query,
            database=request.database or configuration.default_database,
            catalog=request.catalog or configuration.athena_catalog,
            workgroup=request.workgroup or configuration.athena_workgroup,
            output_location=output_location,
            result_size_bytes=result_size_bytes,
            completion_reason=completion_reason,
            execution_time_ms=execution_time_ms,
            preview=preview,
            next_step=next_step,
        )

    def _wait_for_completion(
        self,
        query_execution_id: str,
        max_wait_seconds: int,
    ) -> dict[str, Any]:
        assert self.athena_client is not None
        waited_seconds = 0
        while waited_seconds < max_wait_seconds:
            response: dict[str, Any] = self.athena_client.get_query_execution(
                QueryExecutionId=query_execution_id
            )
            state = response["QueryExecution"]["Status"]["State"]
            if state in {"SUCCEEDED", "FAILED", "CANCELLED"}:
                return response
            sleep(1)
            waited_seconds += 1
        raise QueryExecutionError("Tempo limite excedido aguardando a finalizacao da query")

    def _head_result_size(self, output_location: str) -> int | None:
        if not output_location.startswith("s3://"):
            return None
        assert self.s3_client is not None
        without_prefix = output_location[5:]
        bucket, _, key = without_prefix.partition("/")
        response = self.s3_client.head_object(Bucket=bucket, Key=key)
        return int(response["ContentLength"])

    def _load_preview(self, query_execution_id: str, max_rows: int) -> QueryResultPreview:
        assert self.athena_client is not None
        response: dict[str, Any] = self.athena_client.get_query_results(
            QueryExecutionId=query_execution_id,
            MaxResults=max_rows + 1,
        )
        rows = response["ResultSet"]["Rows"]
        if not rows:
            return QueryResultPreview(columns=[], rows=[], row_count=0)
        columns = [item.get("VarCharValue", "") for item in rows[0].get("Data", [])]
        values: list[list[str | None]] = []
        for row in rows[1:]:
            values.append([column.get("VarCharValue") for column in row.get("Data", [])])
        return QueryResultPreview(columns=columns, rows=values, row_count=len(values))

    def build_stub_csv(self, record: QueryExecutionRecord) -> bytes:
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(
            record.preview.columns if record.preview else ["query_execution_id", "status"]
        )
        if record.preview:
            writer.writerows(record.preview.rows)
        else:
            writer.writerow([record.query_execution_id, record.status])
        return buffer.getvalue().encode("utf-8")