from __future__ import annotations

from dataclasses import dataclass

from botocore.exceptions import (  # type: ignore[import-untyped]
    BotoCoreError,
    ClientError,
    NoCredentialsError,
    ProfileNotFound,
)

from athena_knowledge_mcp.core.exceptions import InvalidConfigurationError
from athena_knowledge_mcp.core.models import (
    DEFAULT_S3_PREFIX,
    AwsSecretMaterial,
    ConfigurationStatus,
    ServerConfiguration,
)
from athena_knowledge_mcp.repositories.local_config_repository import (
    LocalConfigRepository,
)
from athena_knowledge_mcp.services.aws_session_service import AwsSessionService
from athena_knowledge_mcp.utils.validators import validate_configuration

REQUIRED_FIELDS = [
    "authentication_type",
    "aws_region",
    "athena_workgroup",
    "query_results_s3_bucket",
    "query_results_s3_prefix",
    "catalog_bucket",
    "catalog_prefix",
]

STORAGE_BUCKET_FIELDS = ["query_results_s3_bucket", "catalog_bucket"]
STORAGE_PREFIX_FIELDS = ["query_results_s3_prefix", "catalog_prefix"]


@dataclass(slots=True)
class OnboardingService:
    config_repository: LocalConfigRepository
    aws_session_service: AwsSessionService | None = None

    def get_configuration_status(self) -> ConfigurationStatus:
        configuration = self.config_repository.load_configuration()
        if configuration is None:
            return self._enrich_storage_guidance(
                ConfigurationStatus(
                    is_configured=False,
                    missing_fields=REQUIRED_FIELDS,
                )
            )
        missing_fields = self._missing_fields(configuration)
        return self._enrich_storage_guidance(
            ConfigurationStatus(
                is_configured=not missing_fields,
                missing_fields=missing_fields,
                last_updated_at=configuration.last_updated_at,
            )
        )

    def initialize_configuration(
        self,
        configuration: ServerConfiguration,
        secrets: AwsSecretMaterial,
        skip_aws_validation: bool = False,
    ) -> ConfigurationStatus:
        normalized_configuration = ServerConfiguration.model_validate(
            configuration.model_dump(mode="python")
        )
        validate_configuration(normalized_configuration, secrets)
        self._validate_remote_access(
            normalized_configuration,
            secrets,
            skip_aws_validation,
        )
        self.config_repository.save_configuration(normalized_configuration)
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
            raise InvalidConfigurationError(
                "Nao existe configuracao inicial para atualizar"
            )

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

    def list_accessible_s3_buckets(self) -> list[str]:
        if self.aws_session_service is None:
            return []

        configuration = self.config_repository.load_configuration()
        secrets = self.config_repository.load_secrets()
        try:
            return self.aws_session_service.list_s3_buckets(
                configuration,
                secrets,
            )
        except (
            BotoCoreError,
            ClientError,
            NoCredentialsError,
            ProfileNotFound,
        ):
            return []

    def _enrich_storage_guidance(
        self,
        status: ConfigurationStatus,
    ) -> ConfigurationStatus:
        missing_storage_fields = [
            field_name
            for field_name in status.missing_fields
            if field_name in {*STORAGE_BUCKET_FIELDS, *STORAGE_PREFIX_FIELDS}
        ]
        if not missing_storage_fields:
            return status

        status.storage_selection_required = True
        status.storage_missing_fields = missing_storage_fields
        status.recommended_s3_prefix = DEFAULT_S3_PREFIX

        if any(
            field_name in STORAGE_BUCKET_FIELDS
            for field_name in missing_storage_fields
        ):
            status.available_s3_buckets = self.list_accessible_s3_buckets()

        if status.available_s3_buckets:
            status.next_step = (
                "Pergunte uma informacao por vez. Primeiro, pergunte qual "
                "bucket da lista o usuario quer usar. Depois, confirme o "
                f"prefixo padrao {DEFAULT_S3_PREFIX} e so peca um prefixo "
                "digitado manualmente se ele quiser personalizar. "
                "Para Athena, "
                "nao junte regiao, workgroup e databases na mesma pergunta. "
                "Pergunte separadamente e nao exija database padrao; se "
                "quiser registrar contexto, peca uma lista opcional de "
                "databases em pergunta propria."
            )
        else:
            status.next_step = (
                "Defina as credenciais AWS necessarias para listar buckets. "
                f"Depois disso, ofereca o prefixo padrao {DEFAULT_S3_PREFIX} "
                "e so peca um prefixo manual se o usuario quiser "
                "personalizar. "
                "Pergunte uma informacao por vez e nao exija database padrao."
            )
        return status

    def _validate_remote_access(
        self,
        configuration: ServerConfiguration,
        secrets: AwsSecretMaterial,
        skip_aws_validation: bool,
    ) -> None:
        if skip_aws_validation or self.aws_session_service is None:
            return

        session = self.aws_session_service.build_session(
            configuration,
            secrets,
        )
        try:
            session.client(
                "sts",
                region_name=configuration.aws_region,
            ).get_caller_identity()
        except Exception as exc:
            raise InvalidConfigurationError(
                f"Falha ao validar credenciais AWS: {exc}"
            ) from exc
