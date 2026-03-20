from pathlib import Path

import pytest

from athena_knowledge_mcp.core.models import (
    DEFAULT_S3_PREFIX,
    AwsAuthenticationType,
    AwsSecretMaterial,
    ServerConfiguration,
)
from athena_knowledge_mcp.core.exceptions import ConfigurationRequiredError
from athena_knowledge_mcp.core.secrets_store import SecretsStore
from athena_knowledge_mcp.core.settings_store import SettingsStore
from athena_knowledge_mcp.repositories.local_config_repository import (
    LocalConfigRepository,
)
from athena_knowledge_mcp.server.middleware import require_configuration
from athena_knowledge_mcp.services.onboarding_service import OnboardingService


class _FakeAwsSessionService:
    def __init__(self, buckets: list[str] | None = None) -> None:
        self._buckets = buckets or []

    def list_s3_buckets(self, *_args, **_kwargs) -> list[str]:
        return self._buckets


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
        athena_databases=["db_conceito_athena", "db_conceito_relacional"],
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
    service = OnboardingService(
        repository,
        _FakeAwsSessionService(["analytics-bucket", "results-bucket"]),
    )

    status = service.get_configuration_status()

    assert status.is_configured is False
    assert "aws_region" in status.missing_fields
    assert status.storage_selection_required is True
    assert status.available_s3_buckets == [
        "analytics-bucket",
        "results-bucket",
    ]
    assert status.recommended_s3_prefix == DEFAULT_S3_PREFIX
    assert status.next_step is not None
    assert "bucket da lista" in status.next_step
    assert DEFAULT_S3_PREFIX in status.next_step
    assert "Pergunte uma informacao por vez" in status.next_step
    assert "nao exija database padrao" in status.next_step


def test_require_configuration_returns_direct_storage_guidance() -> None:
    repository = LocalConfigRepository(
        SettingsStore(Path("missing.json")),
        SecretsStore(Path("missing-secrets.json")),
    )
    service = OnboardingService(
        repository,
        _FakeAwsSessionService(["analytics-bucket", "results-bucket"]),
    )

    with pytest.raises(ConfigurationRequiredError) as exc_info:
        require_configuration(service)
    message = str(exc_info.value)

    assert "Escolha um bucket nesta lista" in message
    assert "analytics-bucket, results-bucket" in message
    assert f"Use o prefixo padrao {DEFAULT_S3_PREFIX}" in message
    assert "Nao peca para o usuario digitar o bucket" not in message
    assert "bucket da lista" in message


def test_update_configuration_normalizes_blank_storage_prefixes(
    tmp_path: Path,
) -> None:
    repository = LocalConfigRepository(
        SettingsStore(tmp_path / "runtime_settings.json"),
        SecretsStore(tmp_path / "secrets.json"),
    )
    service = OnboardingService(repository)
    configuration = ServerConfiguration(
        authentication_type=AwsAuthenticationType.DEFAULT_CREDENTIALS,
        aws_region="us-east-1",
        athena_workgroup="primary",
        query_results_s3_bucket="results-bucket",
        query_results_s3_prefix="athena/results",
        catalog_bucket="catalog-bucket",
        catalog_prefix="catalog/root",
    )

    service.initialize_configuration(
        configuration,
        AwsSecretMaterial(),
        skip_aws_validation=True,
    )

    status = service.update_configuration(
        {
            "query_results_s3_prefix": "",
            "catalog_prefix": "   ",
        },
        {},
        skip_aws_validation=True,
    )

    saved_configuration = repository.load_configuration()

    assert status.is_configured is True
    assert saved_configuration is not None
    assert saved_configuration.query_results_s3_prefix == DEFAULT_S3_PREFIX
    assert saved_configuration.catalog_prefix == DEFAULT_S3_PREFIX
