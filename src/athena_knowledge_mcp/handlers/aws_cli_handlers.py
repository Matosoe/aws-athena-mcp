from __future__ import annotations

from dataclasses import dataclass

from athena_knowledge_mcp.services.aws_cli_service import AwsCliService


@dataclass(slots=True)
class AwsCliHandlers:
    aws_cli_service: AwsCliService

    def list_aws_cli_profiles(self) -> list[str]:
        return self.aws_cli_service.list_profiles()

    def aws_sso_login(
        self,
        profile: str,
        timeout_seconds: int = 180,
    ) -> dict[str, object]:
        return self.aws_cli_service.sso_login(
            profile=profile,
            timeout_seconds=timeout_seconds,
        )

    def aws_sts_get_caller_identity(
        self,
        profile: str | None = None,
        timeout_seconds: int = 60,
    ) -> dict[str, object]:
        return self.aws_cli_service.sts_get_caller_identity(
            profile=profile,
            timeout_seconds=timeout_seconds,
        )
