from __future__ import annotations

from dataclasses import dataclass

from botocore.exceptions import (  # type: ignore[import-untyped]
    BotoCoreError,
    ClientError,
    NoCredentialsError,
    ProfileNotFound,
)

from athena_knowledge_mcp.core.company_defaults import (
    build_resolved_config,
    has_placeholder_infrastructure,
)
from athena_knowledge_mcp.core.exceptions import InvalidConfigurationError
from athena_knowledge_mcp.core.models import (
    AwsSecretMaterial,
    ConfigurationStatus,
    ResolvedConfig,
    ServerConfiguration,
)
from athena_knowledge_mcp.repositories.local_config_repository import (
    LocalConfigRepository,
)
from athena_knowledge_mcp.services.aws_session_service import AwsSessionService
from athena_knowledge_mcp.utils.validators import validate_configuration


def _has_infra_overrides(configuration: ServerConfiguration) -> bool:
    """Retorna True se o usuario definiu ao menos um override de infraestrutura."""
    return any([
        configuration.authentication_type,
        configuration.aws_region,
        configuration.athena_workgroup,
        configuration.athena_catalog,
        configuration.query_results_s3_bucket,
        configuration.query_results_s3_prefix,
        configuration.catalog_bucket,
        configuration.catalog_prefix,
    ])


@dataclass(slots=True)
class OnboardingService:
    config_repository: LocalConfigRepository
    aws_session_service: AwsSessionService | None = None

    def get_configuration_status(self) -> ConfigurationStatus:
        configuration = self.config_repository.load_configuration()
        if configuration is None:
            return ConfigurationStatus(
                is_configured=False,
                next_step=(
                    "Nenhuma configuracao encontrada. Pergunte ao usuario: "
                    "(1) tipo de autenticacao AWS desejado (profile, "
                    "default_credentials, access_key); "
                    "(2) nome do perfil AWS se aplicavel (ex: 'default', "
                    "'minha-empresa-prod'); "
                    "(3) regiao AWS (ex: 'us-east-1'); "
                    "(4) nome do bucket S3 para resultados do Athena; "
                    "(5) nome do bucket S3 para catalogo (pode ser o mesmo). "
                    "Em seguida, chame initialize_server_configuration com "
                    "os valores informados."
                ),
            )
        next_step: str | None = None
        if has_placeholder_infrastructure() and not _has_infra_overrides(configuration):
            next_step = (
                "Atencao: os defaults de infraestrutura corporativa ainda "
                "sao valores de exemplo. Pergunte ao usuario o bucket S3 "
                "para resultados do Athena e o bucket para o catalogo "
                "(podem ser o mesmo), alem da regiao AWS se diferente de "
                "us-east-1. Em seguida, chame update_server_configuration "
                "com esses valores."
            )
        return ConfigurationStatus(
            is_configured=True,
            last_updated_at=configuration.last_updated_at,
            next_step=next_step,
        )

    def get_resolved_configuration(self) -> ResolvedConfig | None:
        return build_resolved_config(self.config_repository.load_configuration())

    def initialize_configuration(
        self,
        configuration: ServerConfiguration,
        secrets: AwsSecretMaterial,
        skip_aws_validation: bool = False,
    ) -> ConfigurationStatus:
        normalized_configuration = ServerConfiguration.model_validate(
            configuration.model_dump(mode="python")
        )
        resolved = build_resolved_config(normalized_configuration)
        assert resolved is not None
        validate_configuration(resolved, secrets)
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
            raise InvalidConfigurationError("Nao existe configuracao inicial para atualizar")

        current_secrets = self.config_repository.load_secrets()
        merged_configuration = current_configuration.model_copy(update=updates)
        merged_secrets = current_secrets.model_copy(update=secret_updates)
        return self.initialize_configuration(
            merged_configuration,
            merged_secrets,
            skip_aws_validation,
        )

    def list_accessible_s3_buckets(self) -> list[str]:
        """Ferramenta de diagnostico: lista buckets acessiveis."""
        if self.aws_session_service is None:
            return []

        resolved = self.get_resolved_configuration()
        secrets = self.config_repository.load_secrets()
        try:
            return self.aws_session_service.list_s3_buckets(
                resolved,
                secrets,
            )
        except (
            BotoCoreError,
            ClientError,
            NoCredentialsError,
            ProfileNotFound,
        ):
            return []

    def _validate_remote_access(
        self,
        configuration: ServerConfiguration,
        secrets: AwsSecretMaterial,
        skip_aws_validation: bool,
    ) -> None:
        if skip_aws_validation or self.aws_session_service is None:
            return

        resolved = build_resolved_config(configuration)
        assert resolved is not None
        session = self.aws_session_service.build_session(resolved, secrets)
        try:
            session.client(
                "sts",
                region_name=resolved.aws_region,
            ).get_caller_identity()
        except Exception as exc:
            raise InvalidConfigurationError(f"Falha ao validar credenciais AWS: {exc}") from exc
