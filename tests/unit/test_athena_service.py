from datetime import UTC, datetime
from pathlib import Path

from athena_knowledge_mcp.core.models import (
    AthenaQueryRequest,
    AwsAuthenticationType,
    CatalogEntry,
    ServerConfiguration,
)
from athena_knowledge_mcp.repositories.query_history_repository import QueryHistoryRepository
from athena_knowledge_mcp.repositories.s3_catalog_repository import S3CatalogRepository
from athena_knowledge_mcp.repositories.s3_skill_repository import S3SkillRepository
from athena_knowledge_mcp.services.athena_service import AthenaService
from athena_knowledge_mcp.services.s3_catalog_service import S3CatalogService
from athena_knowledge_mcp.services.table_skill_service import TableSkillService


class _FakeAthenaClient:
    def __init__(self) -> None:
        self.start_query_calls: list[dict[str, object]] = []
        self.get_query_execution_calls: list[dict[str, object]] = []
        self.get_query_results_calls: list[dict[str, object]] = []
        self._rows_by_query_id: dict[str, list[str]] = {}

    def start_query_execution(self, **kwargs: object) -> dict[str, object]:
        self.start_query_calls.append(kwargs)
        query_execution_id = f"query-{len(self.start_query_calls)}"
        query = str(kwargs["QueryString"])
        self._rows_by_query_id[query_execution_id] = self._resolve_query_rows(query)
        return {"QueryExecutionId": query_execution_id}

    def get_query_execution(self, **kwargs: object) -> dict[str, object]:
        self.get_query_execution_calls.append(kwargs)
        return {
            "QueryExecution": {
                "Status": {"State": "SUCCEEDED"},
                "ResultConfiguration": {
                    "OutputLocation": "s3://results-bucket/athena/results/query-1.csv"
                },
                "Statistics": {"EngineExecutionTimeInMillis": 12},
            }
        }

    def get_query_results(self, **kwargs: object) -> dict[str, object]:
        self.get_query_results_calls.append(kwargs)
        query_execution_id = str(kwargs["QueryExecutionId"])
        rows = self._rows_by_query_id[query_execution_id]
        return {
            "ResultSet": {
                "Rows": [{"Data": [{"VarCharValue": "value"}]}]
                + [{"Data": [{"VarCharValue": row}]} for row in rows]
            }
        }

    def _resolve_query_rows(self, query: str) -> list[str]:
        normalized_query = " ".join(query.strip().split()).lower()
        if normalized_query == "show databases":
            return ["analytics", "finance", "warehouse"]
        if normalized_query == "show tables in analytics":
            return ["orders", "pageviews"]
        if normalized_query == "show tables in finance":
            return []
        if normalized_query == "show create table orders":
            return ["""CREATE EXTERNAL TABLE `orders`(
  `order_id` bigint,
  `status` string COMMENT 'status atual',
  `items` array<struct<sku:string,qty:int>>
)
PARTITIONED BY (
  `dt` string
)
STORED AS PARQUET
LOCATION 's3://bucket/orders/'
TBLPROPERTIES (
  'classification'='parquet'
)"""]
        if normalized_query == "show create table pageviews":
                        return ["""CREATE EXTERNAL TABLE `pageviews`(
  `session_id` string,
  `path` string
)
STORED AS PARQUET"""]
        raise AssertionError(f"Query inesperada no fake Athena client: {query}")


def build_configuration(tmp_path: Path) -> ServerConfiguration:
    return ServerConfiguration(
        authentication_type=AwsAuthenticationType.DEFAULT_CREDENTIALS,
        aws_region="us-east-1",
        athena_workgroup="primary",
        default_database="default",
        query_results_s3_bucket="results-bucket",
        query_results_s3_prefix="athena/results",
        catalog_bucket="catalog-bucket",
        catalog_prefix="catalog/root",
        local_large_results_folder=tmp_path / "downloads",
    )


def build_catalog_service(tmp_path: Path) -> S3CatalogService:
    service = S3CatalogService(
        S3CatalogRepository(bucket="local", prefix="", local_root=tmp_path / "catalog")
    )
    service.upsert_entry(
        CatalogEntry(
            database_name="analytics",
            table_name="orders",
            summary="Pedidos normalizados",
            business_context="Camada analitica de vendas",
            common_use_cases=["acompanhar pedidos"],
            detail_file_s3_uri="s3://catalog/analytics/orders.md",
            tags=["sales", "orders"],
        )
    )
    service.upsert_entry(
        CatalogEntry(
            database_name="analytics",
            table_name="sessions",
            summary="Sessoes web catalogadas",
            business_context="Uso de navegacao",
            common_use_cases=["medir retencao"],
            detail_file_s3_uri="s3://catalog/analytics/sessions.md",
            tags=["web"],
        )
    )
    return service


def test_execute_query_returns_inline_preview_for_small_result(tmp_path: Path) -> None:
    service = AthenaService(QueryHistoryRepository(tmp_path / "query_history.jsonl"))

    record = service.execute_query(
        AthenaQueryRequest(query="select 1"),
        build_configuration(tmp_path),
    )

    assert record.status == "SUCCEEDED"
    assert record.preview is not None
    assert record.next_step is None


def test_execute_query_marks_large_result_for_materialization(tmp_path: Path) -> None:
    service = AthenaService(QueryHistoryRepository(tmp_path / "query_history.jsonl"))

    record = service.execute_query(
        AthenaQueryRequest(query="select * from large_result"),
        build_configuration(tmp_path),
    )

    assert record.preview is None
    assert record.next_step == "materialize_large_result_locally"


def test_load_preview_uses_column_info_for_show_queries(tmp_path: Path) -> None:
    class _PreviewAthenaClient:
        def get_query_results(self, **kwargs: object) -> dict[str, object]:
            assert kwargs["QueryExecutionId"] == "query-preview"
            return {
                "ResultSet": {
                    "ResultSetMetadata": {
                        "ColumnInfo": [{"Name": "tab_name"}],
                    },
                    "Rows": [
                        {"Data": [{"VarCharValue": "acmp"}]},
                    ],
                }
            }

    service = AthenaService(
        QueryHistoryRepository(tmp_path / "query_history.jsonl"),
        athena_client=_PreviewAthenaClient(),
    )

    preview = service._load_preview("query-preview", max_rows=10)

    assert preview.columns == ["tab_name"]
    assert preview.rows == [["acmp"]]
    assert preview.row_count == 1


def test_load_preview_infers_columns_from_show_tables_query(tmp_path: Path) -> None:
    class _PreviewAthenaClient:
        def get_query_results(self, **kwargs: object) -> dict[str, object]:
            assert kwargs["QueryExecutionId"] == "query-preview"
            return {
                "ResultSet": {
                    "Rows": [
                        {"Data": [{"VarCharValue": "acmp"}]},
                    ],
                }
            }

    service = AthenaService(
        QueryHistoryRepository(tmp_path / "query_history.jsonl"),
        athena_client=_PreviewAthenaClient(),
    )

    preview = service._load_preview(
        "query-preview",
        max_rows=10,
        query="SHOW TABLES IN default",
    )

    assert preview.columns == ["tab_name"]
    assert preview.rows == [["acmp"]]
    assert preview.row_count == 1


def test_list_databases_uses_show_databases_query(tmp_path: Path) -> None:
    athena_client = _FakeAthenaClient()
    service = AthenaService(
        QueryHistoryRepository(tmp_path / "query_history.jsonl"),
        athena_client=athena_client,
    )

    databases = service.list_databases(build_configuration(tmp_path))

    assert [database.name for database in databases] == ["analytics", "finance", "warehouse"]
    assert all(database.sources == ["athena"] for database in databases)
    assert athena_client.start_query_calls[0]["QueryString"] == "SHOW DATABASES"
    assert athena_client.start_query_calls[0]["WorkGroup"] == "primary"


def test_list_tables_uses_show_tables_query(tmp_path: Path) -> None:
    athena_client = _FakeAthenaClient()
    service = AthenaService(
        QueryHistoryRepository(tmp_path / "query_history.jsonl"),
        athena_client=athena_client,
    )

    tables = service.list_tables(
        build_configuration(tmp_path),
        database_name="analytics",
    )

    assert [table.table_name for table in tables] == ["orders", "pageviews"]
    assert all(table.sources == ["athena"] for table in tables)
    assert athena_client.start_query_calls[0]["QueryString"] == "SHOW TABLES IN analytics"
    assert athena_client.start_query_calls[0]["WorkGroup"] == "primary"


def test_list_tables_filters_prefix_after_show_tables_query(tmp_path: Path) -> None:
    athena_client = _FakeAthenaClient()
    service = AthenaService(
        QueryHistoryRepository(tmp_path / "query_history.jsonl"),
        athena_client=athena_client,
    )

    tables = service.list_tables(
        build_configuration(tmp_path),
        database_name="analytics",
        name_prefix="ord",
    )

    assert [table.table_name for table in tables] == ["orders"]


def test_get_table_metadata_reads_columns_from_show_create_table(tmp_path: Path) -> None:
    athena_client = _FakeAthenaClient()
    service = AthenaService(
        QueryHistoryRepository(tmp_path / "query_history.jsonl"),
        athena_client=athena_client,
    )

    metadata = service.get_table_metadata(
        build_configuration(tmp_path),
        database_name="analytics",
        table_name="orders",
    )

    assert metadata.sources == ["athena"]
    assert metadata.columns[0].name == "order_id"
    assert metadata.columns[1].comment == "status atual"
    assert metadata.columns[2].type == "array<struct<sku:string,qty:int>>"
    assert metadata.partition_keys[0].name == "dt"
    assert metadata.parameters["classification"] == "parquet"
    assert metadata.summary is None
    assert athena_client.start_query_calls[0]["QueryString"] == "SHOW CREATE TABLE orders"
    assert athena_client.start_query_calls[0]["QueryExecutionContext"] == {
        "Database": "analytics",
        "Catalog": "AwsDataCatalog",
    }
    assert athena_client.start_query_calls[0]["WorkGroup"] == "primary"


def test_sync_database_to_catalog_creates_generated_skills(tmp_path: Path) -> None:
    athena_client = _FakeAthenaClient()
    catalog_service = S3CatalogService(
        S3CatalogRepository(bucket="local", prefix="", local_root=tmp_path / "catalog")
    )
    table_skill_service = TableSkillService(
        S3SkillRepository(bucket="local", prefix="", local_root=tmp_path / "skills"),
        catalog_service,
    )
    service = AthenaService(
        QueryHistoryRepository(tmp_path / "query_history.jsonl"),
        athena_client=athena_client,
    )

    result = service.sync_database_to_catalog(
        build_configuration(tmp_path),
        database_name="analytics",
        table_skill_service=table_skill_service,
    )

    assert result["synced_count"] == 2
    assert result["skipped_count"] == 0
    assert table_skill_service.catalog_service.get_entry("analytics", "orders") is not None
    assert (tmp_path / "skills" / "analytics" / "orders.md").exists()


def test_sync_database_to_catalog_handles_tables_without_tblproperties(tmp_path: Path) -> None:
    class _NullableParameterAthenaClient(_FakeAthenaClient):
        def _resolve_query_rows(self, query: str) -> list[str]:
            normalized_query = " ".join(query.strip().split()).lower()
            if normalized_query == "show databases":
                return ["analytics"]
            if normalized_query == "show tables in analytics":
                return ["orders", "pageviews"]
            if normalized_query == "show create table orders":
                return ["""CREATE EXTERNAL TABLE `orders`(
  `id` bigint
)
STORED AS TEXTFILE"""]
            if normalized_query == "show create table pageviews":
                return ["""CREATE EXTERNAL TABLE `pageviews`(
  `id` bigint
)
STORED AS TEXTFILE"""]
            raise AssertionError(f"Query inesperada no fake Athena client: {query}")

    athena_client = _NullableParameterAthenaClient()
    catalog_service = S3CatalogService(
        S3CatalogRepository(bucket="local", prefix="", local_root=tmp_path / "catalog")
    )
    table_skill_service = TableSkillService(
        S3SkillRepository(bucket="local", prefix="", local_root=tmp_path / "skills"),
        catalog_service,
    )
    service = AthenaService(
        QueryHistoryRepository(tmp_path / "query_history.jsonl"),
        athena_client=athena_client,
    )

    result = service.sync_database_to_catalog(
        build_configuration(tmp_path),
        database_name="analytics",
        table_skill_service=table_skill_service,
    )

    skill_content = (tmp_path / "skills" / "analytics" / "orders.md").read_text(encoding="utf-8")
    assert result["synced_count"] == 2
    assert "## Colunas" in skill_content
    assert "- id: bigint" in skill_content