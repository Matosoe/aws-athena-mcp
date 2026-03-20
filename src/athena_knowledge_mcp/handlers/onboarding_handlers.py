from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from athena_knowledge_mcp.core.models import (
    DEFAULT_S3_PREFIX,
    AwsAuthenticationType,
    AwsSecretMaterial,
    ServerConfiguration,
)
from athena_knowledge_mcp.services.onboarding_service import OnboardingService


@dataclass(slots=True)
class OnboardingHandlers:
    onboarding_service: OnboardingService

    def initialize_server_configuration(
        self,
        authentication_type: str,
        aws_region: str,
        athena_workgroup: str,
        query_results_s3_bucket: str,
        catalog_bucket: str,
        athena_databases: list[str] | None = None,
        default_database: str | None = None,
        query_results_s3_prefix: str = DEFAULT_S3_PREFIX,
        catalog_prefix: str = DEFAULT_S3_PREFIX,
        athena_catalog: str = "AwsDataCatalog",
        local_large_results_folder: str = "downloads",
        inline_result_max_bytes: int = 500000,
        inline_result_max_rows: int = 200,
        aws_profile: str | None = None,
        aws_access_key_id: str | None = None,
        aws_secret_access_key: str | None = None,
        aws_session_token: str | None = None,
        skip_aws_validation: bool = False,
    ) -> dict[str, object]:
        configuration = ServerConfiguration(
            authentication_type=AwsAuthenticationType(authentication_type),
            aws_region=aws_region,
            aws_profile=aws_profile,
            athena_workgroup=athena_workgroup,
            athena_catalog=athena_catalog,
            athena_databases=athena_databases or [],
            default_database=default_database,
            query_results_s3_bucket=query_results_s3_bucket,
            query_results_s3_prefix=query_results_s3_prefix,
            catalog_bucket=catalog_bucket,
            catalog_prefix=catalog_prefix,
            local_large_results_folder=Path(local_large_results_folder),
            inline_result_max_bytes=inline_result_max_bytes,
            inline_result_max_rows=inline_result_max_rows,
        )
        secrets = AwsSecretMaterial(
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            aws_session_token=aws_session_token,
        )
        status = self.onboarding_service.initialize_configuration(
            configuration,
            secrets,
            skip_aws_validation,
        )
        return status.model_dump(mode="json")

    def get_server_configuration_status(self) -> dict[str, object]:
        return self.onboarding_service.get_configuration_status().model_dump(
            mode="json"
        )

    def list_accessible_s3_buckets(self) -> dict[str, object]:
        buckets = self.onboarding_service.list_accessible_s3_buckets()
        return {
            "buckets": buckets,
            "recommended_prefix": DEFAULT_S3_PREFIX,
            "requires_bucket_selection": True,
            "message": (
                "Mostre a lista de buckets e peca para o usuario escolher um. "
                "No onboarding, faca uma pergunta por vez."
            ),
            "next_step": (
                f"Depois confirme o prefixo padrao {DEFAULT_S3_PREFIX}. So "
                "solicite prefixo manual se o usuario quiser personalizar. "
                "Nao junte regiao, workgroup e databases na mesma pergunta e "
                "nao exija database padrao."
            ),
        }

    def update_server_configuration(
        self,
        skip_aws_validation: bool = False,
        **updates: object,
    ) -> dict[str, object]:
        secret_updates: dict[str, str | None] = {}
        for key in [
            "aws_access_key_id",
            "aws_secret_access_key",
            "aws_session_token",
        ]:
            if key in updates:
                value = updates.pop(key)
                if value is None or isinstance(value, str):
                    secret_updates[key] = value
        if "authentication_type" in updates and isinstance(
            updates["authentication_type"],
            str,
        ):
            updates["authentication_type"] = AwsAuthenticationType(
                updates["authentication_type"]
            )
        if "local_large_results_folder" in updates and isinstance(
            updates["local_large_results_folder"],
            str,
        ):
            updates["local_large_results_folder"] = Path(
                updates["local_large_results_folder"]
            )
        status = self.onboarding_service.update_configuration(
            updates,
            secret_updates,
            skip_aws_validation,
        )
        return status.model_dump(mode="json")
