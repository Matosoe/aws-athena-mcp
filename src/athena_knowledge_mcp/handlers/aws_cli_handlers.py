from __future__ import annotations

from dataclasses import dataclass

from athena_knowledge_mcp.services.aws_cli_service import AwsCliService


@dataclass(slots=True)
class AwsCliHandlers:
    aws_cli_service: AwsCliService

    def list_aws_cli_profiles(self) -> list[str]:
        return self.aws_cli_service.list_profiles()
