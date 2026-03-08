from pathlib import Path

from athena_knowledge_mcp.core.models import (
    AthenaQueryRequest,
    AwsAuthenticationType,
    ServerConfiguration,
)
from athena_knowledge_mcp.repositories.query_history_repository import QueryHistoryRepository
from athena_knowledge_mcp.services.athena_service import AthenaService


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