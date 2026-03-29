from __future__ import annotations

from dataclasses import dataclass

from athena_knowledge_mcp.core.models import (
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
        aws_profile: str | None = None,
        authentication_type: str | None = None,
        aws_region: str | None = None,
        athena_workgroup: str | None = None,
        athena_catalog: str | None = None,
        query_results_s3_bucket: str | None = None,
        query_results_s3_prefix: str | None = None,
        catalog_bucket: str | None = None,
        catalog_prefix: str | None = None,
        skip_aws_validation: bool = False,
    ) -> dict[str, object]:
        infra_overrides: dict[str, object] = {}
        if authentication_type is not None:
            infra_overrides["authentication_type"] = AwsAuthenticationType(authentication_type)
        if aws_region is not None:
            infra_overrides["aws_region"] = aws_region
        if athena_workgroup is not None:
            infra_overrides["athena_workgroup"] = athena_workgroup
        if athena_catalog is not None:
            infra_overrides["athena_catalog"] = athena_catalog
        if query_results_s3_bucket is not None:
            infra_overrides["query_results_s3_bucket"] = query_results_s3_bucket
        if query_results_s3_prefix is not None:
            infra_overrides["query_results_s3_prefix"] = query_results_s3_prefix
        if catalog_bucket is not None:
            infra_overrides["catalog_bucket"] = catalog_bucket
        if catalog_prefix is not None:
            infra_overrides["catalog_prefix"] = catalog_prefix
        configuration = ServerConfiguration(aws_profile=aws_profile, **infra_overrides)
        secrets = AwsSecretMaterial()
        status = self.onboarding_service.initialize_configuration(
            configuration,
            secrets,
            skip_aws_validation,
        )
        return status.model_dump(mode="json")

    def get_server_configuration_status(self) -> dict[str, object]:
        return self.onboarding_service.get_configuration_status().model_dump(mode="json")

    def list_accessible_s3_buckets(self) -> dict[str, object]:
        buckets = self.onboarding_service.list_accessible_s3_buckets()
        return {
            "buckets": buckets,
            "note": (
                "Use esta lista para identificar o bucket correto e "
                "depois chame initialize_server_configuration ou "
                "update_server_configuration com query_results_s3_bucket "
                "e catalog_bucket."
            ),
        }

    def update_server_configuration(
        self,
        aws_profile: str | None = None,
        authentication_type: str | None = None,
        aws_region: str | None = None,
        athena_workgroup: str | None = None,
        athena_catalog: str | None = None,
        query_results_s3_bucket: str | None = None,
        query_results_s3_prefix: str | None = None,
        catalog_bucket: str | None = None,
        catalog_prefix: str | None = None,
        default_database: str | None = None,
        athena_databases: list[str] | None = None,
        inline_result_max_bytes: int | None = None,
        inline_result_max_rows: int | None = None,
        skip_aws_validation: bool = False,
    ) -> dict[str, object]:
        updates: dict[str, object] = {}
        if aws_profile is not None:
            updates["aws_profile"] = aws_profile
        if authentication_type is not None:
            updates["authentication_type"] = AwsAuthenticationType(authentication_type)
        if aws_region is not None:
            updates["aws_region"] = aws_region
        if athena_workgroup is not None:
            updates["athena_workgroup"] = athena_workgroup
        if athena_catalog is not None:
            updates["athena_catalog"] = athena_catalog
        if query_results_s3_bucket is not None:
            updates["query_results_s3_bucket"] = query_results_s3_bucket
        if query_results_s3_prefix is not None:
            updates["query_results_s3_prefix"] = query_results_s3_prefix
        if catalog_bucket is not None:
            updates["catalog_bucket"] = catalog_bucket
        if catalog_prefix is not None:
            updates["catalog_prefix"] = catalog_prefix
        if default_database is not None:
            updates["default_database"] = default_database
        if athena_databases is not None:
            updates["athena_databases"] = athena_databases
        if inline_result_max_bytes is not None:
            updates["inline_result_max_bytes"] = inline_result_max_bytes
        if inline_result_max_rows is not None:
            updates["inline_result_max_rows"] = inline_result_max_rows
        status = self.onboarding_service.update_configuration(
            updates,
            {},
            skip_aws_validation,
        )
        return status.model_dump(mode="json")
