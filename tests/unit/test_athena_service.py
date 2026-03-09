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
        self.list_database_calls: list[dict[str, object]] = []
        self.list_table_calls: list[dict[str, object]] = []
        self.get_table_calls: list[dict[str, object]] = []

    def list_databases(self, **kwargs: object) -> dict[str, object]:
        self.list_database_calls.append(kwargs)
        if kwargs.get("NextToken") == "page-2":
            return {"DatabaseList": [{"Name": "warehouse"}]}
        return {
            "DatabaseList": [{"Name": "analytics"}, {"Name": "finance"}],
            "NextToken": "page-2",
        }

    def list_table_metadata(self, **kwargs: object) -> dict[str, object]:
        self.list_table_calls.append(kwargs)
        database_name = kwargs["DatabaseName"]
        if database_name == "analytics":
            return {
                "TableMetadataList": [
                    {"Name": "orders"},
                    {"Name": "pageviews"},
                ]
            }
        return {"TableMetadataList": []}

    def get_table_metadata(self, **kwargs: object) -> dict[str, object]:
        self.get_table_calls.append(kwargs)
        return {
            "TableMetadata": {
                "Name": "orders",
                "TableType": "EXTERNAL_TABLE",
                "CreateTime": datetime(2025, 1, 10, tzinfo=UTC),
                "LastAccessTime": datetime(2025, 1, 11, tzinfo=UTC),
                "Columns": [
                    {"Name": "order_id", "Type": "bigint"},
                    {"Name": "status", "Type": "string", "Comment": "status atual"},
                ],
                "PartitionKeys": [{"Name": "dt", "Type": "string"}],
                "Parameters": {"classification": "parquet"},
            }
        }


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


def test_list_databases_prefers_cache_and_merges_remote(tmp_path: Path) -> None:
    athena_client = _FakeAthenaClient()
    service = AthenaService(
        QueryHistoryRepository(tmp_path / "query_history.jsonl"),
        athena_client=athena_client,
    )

    databases = service.list_databases(build_configuration(tmp_path))

    assert [database.name for database in databases] == ["analytics", "finance", "warehouse"]
    assert all(database.sources == ["athena"] for database in databases)
    assert athena_client.list_database_calls[0]["WorkGroup"] == "primary"


def test_list_tables_prefers_cache_and_merges_remote(tmp_path: Path) -> None:
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
    assert athena_client.list_table_calls[0]["WorkGroup"] == "primary"


def test_get_table_metadata_enriches_remote_with_cache(tmp_path: Path) -> None:
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
    assert metadata.partition_keys[0].name == "dt"
    assert metadata.parameters["classification"] == "parquet"
    assert metadata.summary is None
    assert athena_client.get_table_calls[0]["WorkGroup"] == "primary"


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


def test_sync_database_to_catalog_accepts_nullable_table_parameters(tmp_path: Path) -> None:
    class _NullableParameterAthenaClient(_FakeAthenaClient):
        def get_table_metadata(self, **kwargs: object) -> dict[str, object]:
            self.get_table_calls.append(kwargs)
            return {
                "TableMetadata": {
                    "Name": kwargs["TableName"],
                    "TableType": "EXTERNAL_TABLE",
                    "Columns": [{"Name": "id", "Type": "bigint"}],
                    "Parameters": {
                        "classification": "csv",
                        "inputformat": None,
                        "outputformat": None,
                        "serde.serialization.lib": None,
                    },
                }
            }

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
    assert "- inputformat: (null)" in skill_content
    assert "- outputformat: (null)" in skill_content