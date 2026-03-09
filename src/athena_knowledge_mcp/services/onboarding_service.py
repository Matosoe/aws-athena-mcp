from __future__ import annotations

from dataclasses import dataclass

from athena_knowledge_mcp.core.exceptions import InvalidConfigurationError
from athena_knowledge_mcp.core.models import (
    AwsSecretMaterial,
    ConfigurationStatus,
    ServerConfiguration,
)
from athena_knowledge_mcp.repositories.local_config_repository import LocalConfigRepository
from athena_knowledge_mcp.services.aws_session_service import AwsSessionService
from athena_knowledge_mcp.utils.validators import validate_configuration

REQUIRED_FIELDS = [
    "authentication_type",
    "aws_region",
    "athena_workgroup",
    "default_database",
    "query_results_s3_bucket",
    "query_results_s3_prefix",
    "catalog_bucket",
    "catalog_prefix",
]


@dataclass(slots=True)
class OnboardingService:
    config_repository: LocalConfigRepository
    aws_session_service: AwsSessionService | None = None

    def get_configuration_status(self) -> ConfigurationStatus:
        configuration = self.config_repository.load_configuration()
        if configuration is None:
            return ConfigurationStatus(is_configured=False, missing_fields=REQUIRED_FIELDS)
        missing_fields = self._missing_fields(configuration)
        return ConfigurationStatus(
            is_configured=not missing_fields,
            missing_fields=missing_fields,
            last_updated_at=configuration.last_updated_at,
        )

    def initialize_configuration(
        self,
        configuration: ServerConfiguration,
        secrets: AwsSecretMaterial,
        skip_aws_validation: bool = False,
    ) -> ConfigurationStatus:
        validate_configuration(configuration, secrets)
        self._validate_remote_access(configuration, secrets, skip_aws_validation)
        self.config_repository.save_configuration(configuration)
        self.config_repository.save_secrets(secrets)
        return self.get_configuration_status()

    def update_configuration(
        self,
        updates: dict[str, object],
        secret_updates: dict[str, str | None],
        skip_aws_validation: bool = False,
    ) -> ConfigurationStatus:
        current_configuration = self.config_repository.load_configuration()
        if current_configuration is None:
            raise InvalidConfigurationError("Nao existe configuracao inicial para atualizar")

        current_secrets = self.config_repository.load_secrets()
        merged_configuration = current_configuration.model_copy(update=updates)
        merged_secrets = current_secrets.model_copy(update=secret_updates)
        return self.initialize_configuration(
            merged_configuration,
            merged_secrets,
            skip_aws_validation,
        )

    def _missing_fields(self, configuration: ServerConfiguration) -> list[str]:
        missing_fields: list[str] = []
        for field_name in REQUIRED_FIELDS:
            if not getattr(configuration, field_name):
                missing_fields.append(field_name)
        return missing_fields

    def _validate_remote_access(
        self,
        configuration: ServerConfiguration,
        secrets: AwsSecretMaterial,
        skip_aws_validation: bool,
    ) -> None:
        if skip_aws_validation or self.aws_session_service is None:
            return

        session = self.aws_session_service.build_session(configuration, secrets)
        try:
            session.client("sts", region_name=configuration.aws_region).get_caller_identity()
        except Exception as exc:
            raise InvalidConfigurationError(f"Falha ao validar credenciais AWS: {exc}") from exc