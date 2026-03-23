from pathlib import Path

import pytest

from athena_knowledge_mcp.core.models import (
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
        aws_profile="test-profile",
        athena_databases=["db_conceito_athena", "db_conceito_relacional"],
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
    assert status.next_step is not None


def test_require_configuration_raises_when_not_configured() -> None:
    repository = LocalConfigRepository(
        SettingsStore(Path("missing.json")),
        SecretsStore(Path("missing-secrets.json")),
    )
    service = OnboardingService(repository)

    with pytest.raises(ConfigurationRequiredError):
        require_configuration(service)
