from pathlib import Path

from athena_knowledge_mcp.core.models import AwsAuthenticationType, ServerConfiguration
from athena_knowledge_mcp.core.settings_store import SettingsStore


def test_save_and_load_settings(tmp_path: Path) -> None:
    file_path = tmp_path / "runtime_settings.json"
    store = SettingsStore(file_path)
    configuration = ServerConfiguration(
        authentication_type=AwsAuthenticationType.DEFAULT_CREDENTIALS,
        aws_region="us-east-1",
        athena_workgroup="primary",
        default_database="default",
        query_results_s3_bucket="results-bucket",
        query_results_s3_prefix="athena/results",
        catalog_bucket="catalog-bucket",
        catalog_prefix="catalog/root",
    )

    store.save(configuration)

    loaded = store.load()

    assert loaded is not None
    assert loaded.aws_region == "us-east-1"
    assert loaded.catalog_bucket == "catalog-bucket"
