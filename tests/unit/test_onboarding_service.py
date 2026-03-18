from pathlib import Path

from athena_knowledge_mcp.core.models import (
    AwsAuthenticationType,
    AwsSecretMaterial,
    ServerConfiguration,
)
from athena_knowledge_mcp.core.secrets_store import SecretsStore
from athena_knowledge_mcp.core.settings_store import SettingsStore
from athena_knowledge_mcp.repositories.local_config_repository import LocalConfigRepository
from athena_knowledge_mcp.services.onboarding_service import OnboardingService


def test_initialize_configuration_persists_data(tmp_path: Path) -> None:
    repository = LocalConfigRepository(
        SettingsStore(tmp_path / "runtime_settings.json"),
        SecretsStore(tmp_path / "secrets.json"),
    )
    service = OnboardingService(repository)
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

    status = service.initialize_configuration(
        configuration,
        AwsSecretMaterial(),
        skip_aws_validation=True,
    )

    assert status.is_configured is True
    assert repository.load_configuration() is not None


def test_get_configuration_status_when_missing() -> None:
    repository = LocalConfigRepository(
        SettingsStore(Path("missing.json")),
        SecretsStore(Path("missing-secrets.json")),
    )
    service = OnboardingService(repository)

    status = service.get_configuration_status()

    assert status.is_configured is False
    assert "aws_region" in status.missing_fields