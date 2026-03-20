from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass
from time import sleep
from typing import Any
from uuid import uuid4

from athena_knowledge_mcp.core.aws_errors import raise_if_aws_access_denied
from athena_knowledge_mcp.core.exceptions import QueryExecutionError
from athena_knowledge_mcp.core.models import (
    AthenaColumnMetadata,
    AthenaDatabaseSummary,
    AthenaQueryRequest,
    AthenaTableMetadata,
    AthenaTableSummary,
    QueryExecutionRecord,
    QueryResultPreview,
    ServerConfiguration,
    TableSkill,
)
from athena_knowledge_mcp.repositories.query_history_repository import QueryHistoryRepository
from athena_knowledge_mcp.services.table_skill_service import TableSkillService
from athena_knowledge_mcp.utils.formatters import format_large_result_message


@dataclass(slots=True)
class AthenaService:
    history_repository: QueryHistoryRepository
    athena_client: Any | None = None
    s3_client: Any | None = None

    def list_databases(
        self,
        configuration: ServerConfiguration,
        catalog: str | None = None,
    ) -> list[AthenaDatabaseSummary]:
        if self.athena_client is None:
            raise QueryExecutionError(
                "Cliente Athena nao configurado para consultar databases remotamente"
            )

        remote_database_names = self._list_databases_via_show(
            configuration,
            catalog or configuration.athena_catalog,
        )
        return [
            AthenaDatabaseSummary(
                name=database_name,
                sources=["athena"],
            )
            for database_name in remote_database_names
        ]

    def list_tables(
        self,
        configuration: ServerConfiguration,
        database_name: str,
        catalog: str | None = None,
        name_prefix: str | None = None,
    ) -> list[AthenaTableSummary]:
        if self.athena_client is None:
            raise QueryExecutionError(
                "Cliente Athena nao configurado para consultar tabelas remotamente"
            )

        remote_tables = self._list_tables_via_show(
            configuration,
            database_name=database_name,
            catalog=catalog or configuration.athena_catalog,
            name_prefix=name_prefix,
        )
        return [
            AthenaTableSummary(
                database_name=database_name,
                table_name=table_name,
                sources=["athena"],
            )
            for table_name in remote_tables
        ]

    def get_table_metadata(
        self,
        configuration: ServerConfiguration,
        database_name: str,
        table_name: str,
        catalog: str | None = None,
    ) -> AthenaTableMetadata:
        resolved_catalog = catalog or configuration.athena_catalog

        if self.athena_client is None:
            raise QueryExecutionError(
                "Cliente Athena nao configurado para consultar propriedades da tabela"
            )

        ddl = self._fetch_show_create_table_statement(
            configuration,
            database_name=database_name,
            table_name=table_name,
            catalog=resolved_catalog,
        )
        return self._parse_show_create_table(
            database_name=database_name,
            table_name=table_name,
            catalog=resolved_catalog,
            ddl=ddl,
        )

    def sync_database_to_catalog(
        self,
        configuration: ServerConfiguration,
        database_name: str,
        table_skill_service: TableSkillService,
        catalog: str | None = None,
        name_prefix: str | None = None,
        max_tables: int | None = None,
        overwrite_existing: bool = False,
    ) -> dict[str, object]:
        tables = self.list_tables(
            configuration,
            database_name=database_name,
            catalog=catalog,
            name_prefix=name_prefix,
        )
        if max_tables is not None:
            tables = tables[:max_tables]

        synced_tables: list[str] = []
        skipped_tables: list[str] = []
        for table in tables:
            if not overwrite_existing and table_skill_service.catalog_service.get_entry(
                database_name,
                table.table_name,
            ) is not None:
                skipped_tables.append(table.table_name)
                continue

            metadata = self.get_table_metadata(
                configuration,
                database_name=database_name,
                table_name=table.table_name,
                catalog=catalog,
            )
            generated_skill = self._build_generated_table_skill(metadata)
            table_skill_service.create_or_update_table_skill(generated_skill)
            synced_tables.append(table.table_name)

        return {
            "database_name": database_name,
            "synced_tables": synced_tables,
            "skipped_tables": skipped_tables,
            "synced_count": len(synced_tables),
            "skipped_count": len(skipped_tables),
        }

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
        database = self._resolve_database(request, configuration)
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
                    database=database,
                    catalog=request.catalog or configuration.athena_catalog,
                    workgroup=(
                        request.workgroup
                        or configuration.athena_workgroup
                    ),
                    output_location=(
                        f"s3://{configuration.query_results_s3_bucket}/"
                        f"{configuration.query_results_s3_prefix.strip('/')}"
                        f"/{query_execution_id}.csv"
                    ),
                    result_size_bytes=result_size_bytes,
                )
            )

        return QueryExecutionRecord(
            query_execution_id=query_execution_id,
            status="SUCCEEDED",
            submitted_query=request.query,
            database=database,
            catalog=request.catalog or configuration.athena_catalog,
            workgroup=request.workgroup or configuration.athena_workgroup,
            output_location=(
                f"s3://{configuration.query_results_s3_bucket}/"
                f"{configuration.query_results_s3_prefix.strip('/')}"
                f"/{query_execution_id}.csv"
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
        database = self._resolve_database(request, configuration)
        query_context = {
            "Catalog": request.catalog or configuration.athena_catalog,
        }
        if database:
            query_context["Database"] = database
        try:
            response: dict[str, Any] = self.athena_client.start_query_execution(
                QueryString=request.query,
                QueryExecutionContext=query_context,
                WorkGroup=request.workgroup or configuration.athena_workgroup,
                ResultConfiguration={
                    "OutputLocation": (
                        f"s3://{configuration.query_results_s3_bucket}/"
                        f"{configuration.query_results_s3_prefix.strip('/')}"
                    )
                },
            )
        except Exception as exc:
            raise_if_aws_access_denied(exc, "Athena")
            raise
        query_execution_id = response["QueryExecutionId"]
        status_response = self._wait_for_completion(
            query_execution_id,
            request.max_wait_seconds,
        )
        query_execution = status_response["QueryExecution"]
        status = query_execution["Status"]["State"]
        output_location = query_execution["ResultConfiguration"].get(
            "OutputLocation"
        )
        execution_time_ms = query_execution.get(
            "Statistics", {}
        ).get("EngineExecutionTimeInMillis")

        if status != "SUCCEEDED":
            raise QueryExecutionError(
                query_execution["Status"].get(
                    "StateChangeReason",
                    "Falha na query",
                )
            )

        result_size_bytes = (
            self._head_result_size(output_location)
            if output_location
            else None
        )
        preview = None
        next_step = None
        completion_reason = None
        if (
            result_size_bytes is not None
            and result_size_bytes <= configuration.inline_result_max_bytes
        ):
            preview = self._load_preview(
                query_execution_id,
                configuration.inline_result_max_rows,
            )
        else:
            next_step = "materialize_large_result_locally"
            completion_reason = format_large_result_message(
                QueryExecutionRecord(
                    query_execution_id=query_execution_id,
                    status=status,
                    submitted_query=request.query,
                    database=database,
                    catalog=request.catalog or configuration.athena_catalog,
                    workgroup=(
                        request.workgroup
                        or configuration.athena_workgroup
                    ),
                    output_location=output_location,
                    result_size_bytes=result_size_bytes,
                )
            )

        return QueryExecutionRecord(
            query_execution_id=query_execution_id,
            status=status,
            submitted_query=request.query,
            database=database,
            catalog=request.catalog or configuration.athena_catalog,
            workgroup=request.workgroup or configuration.athena_workgroup,
            output_location=output_location,
            result_size_bytes=result_size_bytes,
            completion_reason=completion_reason,
            execution_time_ms=execution_time_ms,
            preview=preview,
            next_step=next_step,
        )

    def _resolve_database(
        self,
        request: AthenaQueryRequest,
        configuration: ServerConfiguration,
    ) -> str | None:
        if request.database and request.database.strip():
            return request.database.strip()
        if (
            configuration.default_database
            and configuration.default_database.strip()
        ):
            return configuration.default_database.strip()
        return None

    def _wait_for_completion(
        self,
        query_execution_id: str,
        max_wait_seconds: int,
    ) -> dict[str, Any]:
        assert self.athena_client is not None
        waited_seconds = 0
        while waited_seconds < max_wait_seconds:
            try:
                response: dict[str, Any] = self.athena_client.get_query_execution(
                    QueryExecutionId=query_execution_id
                )
            except Exception as exc:
                raise_if_aws_access_denied(exc, "Athena")
                raise
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
        try:
            response = self.s3_client.head_object(Bucket=bucket, Key=key)
        except Exception as exc:
            raise_if_aws_access_denied(exc, "S3")
            raise
        return int(response["ContentLength"])

    def _load_preview(
        self,
        query_execution_id: str,
        max_rows: int,
        query: str | None = None,
    ) -> QueryResultPreview:
        assert self.athena_client is not None
        try:
            response: dict[str, Any] = self.athena_client.get_query_results(
                QueryExecutionId=query_execution_id,
                MaxResults=max_rows + 1,
            )
        except Exception as exc:
            raise_if_aws_access_denied(exc, "Athena")
            raise
        columns, values = self._parse_query_results_table(response, query_hint=query)
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

    def _list_databases_via_show(
        self,
        configuration: ServerConfiguration,
        catalog: str,
    ) -> list[str]:
        rows = self._execute_metadata_query(
            configuration,
            query="SHOW DATABASES",
            catalog=catalog,
        )
        databases = sorted(
            {
                row[0]
                for row in rows
                if row and row[0]
            }
        )
        return databases

    def _list_tables_via_show(
        self,
        configuration: ServerConfiguration,
        database_name: str,
        catalog: str,
        name_prefix: str | None = None,
    ) -> list[str]:
        rows = self._execute_metadata_query(
            configuration,
            query=(
                "SHOW TABLES IN "
                f"{self._quote_sql_identifier(database_name)}"
            ),
            database=database_name,
            catalog=catalog,
        )
        tables = [
            row[0]
            for row in rows
            if row and row[0]
        ]
        if name_prefix:
            normalized_prefix = name_prefix.lower()
            tables = [
                table_name
                for table_name in tables
                if table_name.lower().startswith(normalized_prefix)
            ]
        return sorted(set(tables))

    def _execute_metadata_query(
        self,
        configuration: ServerConfiguration,
        query: str,
        catalog: str,
        database: str | None = None,
        max_results: int = 1000,
    ) -> list[list[str | None]]:
        assert self.athena_client is not None
        try:
            response: dict[str, Any] = self.athena_client.start_query_execution(
                QueryString=query,
                QueryExecutionContext={
                    "Database": database or configuration.default_database,
                    "Catalog": catalog,
                },
                WorkGroup=configuration.athena_workgroup,
                ResultConfiguration={
                    "OutputLocation": (
                        f"s3://{configuration.query_results_s3_bucket}/"
                        f"{configuration.query_results_s3_prefix.strip('/')}"
                    )
                },
            )
        except Exception as exc:
            raise_if_aws_access_denied(exc, "Athena")
            raise
        query_execution_id = response["QueryExecutionId"]
        status_response = self._wait_for_completion(query_execution_id, max_wait_seconds=60)
        query_execution = status_response["QueryExecution"]
        status = query_execution["Status"]["State"]
        if status != "SUCCEEDED":
            raise QueryExecutionError(
                query_execution["Status"].get("StateChangeReason", "Falha na query")
            )

        try:
            result_response: dict[str, Any] = self.athena_client.get_query_results(
                QueryExecutionId=query_execution_id,
                MaxResults=max_results,
            )
        except Exception as exc:
            raise_if_aws_access_denied(exc, "Athena")
            raise
        return self._extract_rows_from_query_results(result_response)

    def _fetch_show_create_table_statement(
        self,
        configuration: ServerConfiguration,
        database_name: str,
        table_name: str,
        catalog: str,
    ) -> str:
        assert self.athena_client is not None
        try:
            response: dict[str, Any] = self.athena_client.start_query_execution(
                QueryString=f"SHOW CREATE TABLE {self._quote_sql_identifier(table_name)}",
                QueryExecutionContext={
                    "Database": database_name,
                    "Catalog": catalog,
                },
                WorkGroup=configuration.athena_workgroup,
                ResultConfiguration={
                    "OutputLocation": (
                        f"s3://{configuration.query_results_s3_bucket}/"
                        f"{configuration.query_results_s3_prefix.strip('/')}"
                    )
                },
            )
        except Exception as exc:
            raise_if_aws_access_denied(exc, "Athena")
            raise
        query_execution_id = response["QueryExecutionId"]
        status_response = self._wait_for_completion(query_execution_id, max_wait_seconds=60)
        query_execution = status_response["QueryExecution"]
        status = query_execution["Status"]["State"]
        if status != "SUCCEEDED":
            raise QueryExecutionError(
                query_execution["Status"].get("StateChangeReason", "Falha na query")
            )

        try:
            result_response: dict[str, Any] = self.athena_client.get_query_results(
                QueryExecutionId=query_execution_id,
                MaxResults=20,
            )
        except Exception as exc:
            raise_if_aws_access_denied(exc, "Athena")
            raise
        rows = self._extract_rows_from_query_results(result_response)
        statement_parts: list[str] = []
        for row in rows:
            statement = row[0] if row else None
            if statement:
                statement_parts.append(statement)

        ddl = "\n".join(statement_parts).strip()
        if not ddl:
            raise QueryExecutionError(
                f"SHOW CREATE TABLE nao retornou DDL para {database_name}.{table_name}"
            )
        return ddl

    @staticmethod
    def _extract_rows_from_query_results(
        result_response: dict[str, Any],
    ) -> list[list[str | None]]:
        _, data_rows = AthenaService._parse_query_results_table(result_response)
        return data_rows

    @staticmethod
    def _parse_query_results_table(
        result_response: dict[str, Any],
        query_hint: str | None = None,
    ) -> tuple[list[str], list[list[str | None]]]:
        result_set = result_response.get("ResultSet", {})
        rows = result_set.get("Rows", [])
        if not rows:
            return [], []

        metadata = result_set.get("ResultSetMetadata", {})
        column_info = metadata.get("ColumnInfo", [])
        metadata_columns = [
            str(column.get("Name", ""))
            for column in column_info
            if str(column.get("Name", ""))
        ]

        parsed_rows = [
            [column.get("VarCharValue") for column in row.get("Data", [])]
            for row in rows
        ]
        if metadata_columns:
            if parsed_rows and parsed_rows[0] == metadata_columns:
                parsed_rows = parsed_rows[1:]
            return metadata_columns, parsed_rows

        inferred_columns = AthenaService._infer_columns_from_query_hint(query_hint)
        if inferred_columns:
            return inferred_columns, parsed_rows

        columns = [item.get("VarCharValue", "") for item in rows[0].get("Data", [])]
        return columns, parsed_rows[1:]

    @staticmethod
    def _infer_columns_from_query_hint(query_hint: str | None) -> list[str]:
        if query_hint is None:
            return []

        normalized_query = " ".join(query_hint.strip().lower().split())
        if normalized_query.startswith("show tables"):
            return ["tab_name"]
        if normalized_query.startswith("show databases"):
            return ["database_name"]
        return []

    def _parse_show_create_table(
        self,
        database_name: str,
        table_name: str,
        catalog: str,
        ddl: str,
    ) -> AthenaTableMetadata:
        header_match = re.search(
            r"CREATE\s+(?P<external>EXTERNAL\s+)?TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(?:`[^`]+`|\"[^\"]+\"|[^\s(]+)\s*\(",
            ddl,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if header_match is None:
            raise QueryExecutionError(
                f"Nao foi possivel interpretar o DDL retornado para {database_name}.{table_name}"
            )

        columns_block, columns_end = self._extract_parenthesized_block(ddl, header_match.end() - 1)
        suffix = ddl[columns_end:]

        partition_keys: list[AthenaColumnMetadata] = []
        partition_match = re.search(
            r"\bPARTITIONED\s+BY\s*\(",
            suffix,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if partition_match is not None:
            partition_block, _ = self._extract_parenthesized_block(
                suffix,
                partition_match.end() - 1,
            )
            partition_keys = self._parse_column_block(partition_block)

        parameters: dict[str, str | None] = {}
        properties_match = re.search(
            r"\bTBLPROPERTIES\s*\(",
            suffix,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if properties_match is not None:
            properties_block, _ = self._extract_parenthesized_block(
                suffix,
                properties_match.end() - 1,
            )
            parameters = self._parse_table_properties(properties_block)

        return AthenaTableMetadata(
            database_name=database_name,
            table_name=table_name,
            catalog=catalog,
            sources=["athena"],
            table_type=(
                "EXTERNAL_TABLE"
                if header_match.group("external") is not None
                else "TABLE"
            ),
            columns=self._parse_column_block(columns_block),
            partition_keys=partition_keys,
            parameters=parameters,
        )

    def _extract_parenthesized_block(self, text: str, start_index: int) -> tuple[str, int]:
        if start_index >= len(text) or text[start_index] != "(":
            raise QueryExecutionError("DDL invalido: bloco entre parenteses nao encontrado")

        depth = 0
        quote: str | None = None
        cursor = start_index
        content_start = start_index + 1
        while cursor < len(text):
            char = text[cursor]
            if quote is not None:
                if char == quote:
                    if cursor + 1 < len(text) and text[cursor + 1] == quote:
                        cursor += 2
                        continue
                    quote = None
                cursor += 1
                continue

            if char in {"'", '"', "`"}:
                quote = char
                cursor += 1
                continue

            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
                if depth == 0:
                    return text[content_start:cursor], cursor + 1
            cursor += 1

        raise QueryExecutionError("DDL invalido: parenteses desbalanceados")

    def _split_top_level_items(self, content: str) -> list[str]:
        items: list[str] = []
        current: list[str] = []
        quote: str | None = None
        round_depth = 0
        angle_depth = 0
        square_depth = 0
        curly_depth = 0
        cursor = 0

        while cursor < len(content):
            char = content[cursor]
            if quote is not None:
                current.append(char)
                if char == quote:
                    if cursor + 1 < len(content) and content[cursor + 1] == quote:
                        current.append(content[cursor + 1])
                        cursor += 2
                        continue
                    quote = None
                cursor += 1
                continue

            if char in {"'", '"', "`"}:
                quote = char
                current.append(char)
                cursor += 1
                continue

            if char == "(":
                round_depth += 1
            elif char == ")":
                round_depth = max(0, round_depth - 1)
            elif char == "<":
                angle_depth += 1
            elif char == ">":
                angle_depth = max(0, angle_depth - 1)
            elif char == "[":
                square_depth += 1
            elif char == "]":
                square_depth = max(0, square_depth - 1)
            elif char == "{":
                curly_depth += 1
            elif char == "}":
                curly_depth = max(0, curly_depth - 1)
            elif (
                char == ","
                and round_depth == 0
                and angle_depth == 0
                and square_depth == 0
                and curly_depth == 0
            ):
                item = "".join(current).strip()
                if item:
                    items.append(item)
                current = []
                cursor += 1
                continue

            current.append(char)
            cursor += 1

        item = "".join(current).strip()
        if item:
            items.append(item)
        return items

    def _parse_column_block(self, content: str) -> list[AthenaColumnMetadata]:
        columns: list[AthenaColumnMetadata] = []
        for definition in self._split_top_level_items(content):
            name, tail = self._parse_definition_name_and_tail(definition)
            comment: str | None = None
            comment_match = re.search(
                r"\s+COMMENT\s+'((?:''|[^'])*)'\s*$",
                tail,
                flags=re.IGNORECASE | re.DOTALL,
            )
            if comment_match is not None:
                comment = comment_match.group(1).replace("''", "'")
                tail = tail[:comment_match.start()].strip()
            if not tail:
                continue
            columns.append(
                AthenaColumnMetadata(
                    name=name,
                    type=tail,
                    comment=comment,
                )
            )
        return columns

    def _parse_definition_name_and_tail(self, definition: str) -> tuple[str, str]:
        text = definition.strip()
        if not text:
            raise QueryExecutionError("DDL invalido: definicao de coluna vazia")

        if text[0] in {'"', "`"}:
            quote = text[0]
            name_chars: list[str] = []
            cursor = 1
            while cursor < len(text):
                char = text[cursor]
                if char == quote:
                    if cursor + 1 < len(text) and text[cursor + 1] == quote:
                        name_chars.append(quote)
                        cursor += 2
                        continue
                    return "".join(name_chars), text[cursor + 1 :].strip()
                name_chars.append(char)
                cursor += 1
            raise QueryExecutionError("DDL invalido: identificador com aspas nao fechado")

        name, separator, tail = text.partition(" ")
        if not separator:
            raise QueryExecutionError(
                f"DDL invalido: tipo nao encontrado para a definicao '{definition}'"
            )
        return name.strip(), tail.strip()

    def _parse_table_properties(self, content: str) -> dict[str, str | None]:
        properties: dict[str, str | None] = {}
        for item in self._split_top_level_items(content):
            match = re.fullmatch(
                r"\s*'((?:''|[^'])*)'\s*=\s*'((?:''|[^'])*)'\s*",
                item,
                flags=re.DOTALL,
            )
            if match is None:
                continue
            properties[match.group(1).replace("''", "'")] = match.group(2).replace(
                "''",
                "'",
            )
        return properties

    def _quote_sql_identifier(self, identifier: str) -> str:
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", identifier):
            return identifier
        return f'"{identifier.replace("\"", "\"\"")}"'

    def _build_column(self, column: dict[str, Any]) -> AthenaColumnMetadata:
        return AthenaColumnMetadata(
            name=column.get("Name", ""),
            type=column.get("Type", "unknown"),
            comment=column.get("Comment"),
        )

    def _build_generated_table_skill(self, metadata: AthenaTableMetadata) -> TableSkill:
        column_lines = [
            f"- {column.name}: {column.type}" + (f" ({column.comment})" if column.comment else "")
            for column in metadata.columns
        ]
        partition_lines = [
            f"- {column.name}: {column.type}" + (f" ({column.comment})" if column.comment else "")
            for column in metadata.partition_keys
        ]
        parameter_lines = [
            f"- {key}: {value if value is not None else '(null)'}"
            for key, value in sorted(metadata.parameters.items())
        ]
        sections = [
            f"# {metadata.database_name}.{metadata.table_name}",
            "",
            "Skill gerada automaticamente a partir do metadata do AWS Athena.",
            "",
            "## Colunas",
            *(column_lines or ["- Nenhuma coluna retornada pelo Athena."]),
        ]
        if partition_lines:
            sections.extend(["", "## Particoes", *partition_lines])
        if parameter_lines:
            sections.extend(["", "## Parametros", *parameter_lines])
        summary = (
            f"Tabela Athena com {len(metadata.columns)} colunas"
            + (f" e {len(metadata.partition_keys)} particoes" if metadata.partition_keys else "")
            + "."
        )
        tags = [value for value in [metadata.table_type, metadata.parameters.get("classification")] if value]
        return TableSkill(
            database_name=metadata.database_name,
            table_name=metadata.table_name,
            description="Skill gerada automaticamente a partir do Athena.",
            content_markdown="\n".join(sections),
            summary=summary,
            tags=tags,
        )