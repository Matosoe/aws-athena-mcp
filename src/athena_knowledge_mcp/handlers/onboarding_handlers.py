from __future__ import annotations

from dataclasses import dataclass

from athena_knowledge_mcp.core.models import (
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
        skip_aws_validation: bool = False,
    ) -> dict[str, object]:
        configuration = ServerConfiguration(aws_profile=aws_profile)
        secrets = AwsSecretMaterial()
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
            "note": (
                "Esta ferramenta e apenas para diagnostico. "
                "O bucket e prefixo de infraestrutura sao fixos "
                "e definidos no company_defaults.py."
            ),
        }

    def update_server_configuration(
        self,
        aws_profile: str | None = None,
        default_database: str | None = None,
        athena_databases: list[str] | None = None,
        inline_result_max_bytes: int | None = None,
        inline_result_max_rows: int | None = None,
        skip_aws_validation: bool = False,
    ) -> dict[str, object]:
        updates: dict[str, object] = {}
        if aws_profile is not None:
            updates["aws_profile"] = aws_profile
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
