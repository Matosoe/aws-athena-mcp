from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from athena_knowledge_mcp.core.models import TableSkill
from athena_knowledge_mcp.server.middleware import require_configuration
from athena_knowledge_mcp.services.onboarding_service import OnboardingService
from athena_knowledge_mcp.services.table_skill_service import TableSkillService


@dataclass(slots=True)
class FileHandlers:
    onboarding_service: OnboardingService
    table_skill_service_factory: Callable[[], TableSkillService]

    def get_table_skill(self, database_name: str, table_name: str) -> dict[str, str]:
        require_configuration(self.onboarding_service)
        service = self.table_skill_service_factory()
        return service.get_table_skill(database_name, table_name)

    def create_or_update_table_skill(
        self,
        database_name: str,
        table_name: str,
        description: str,
        content_markdown: str,
        summary: str,
        business_context: str = "",
        common_use_cases: list[str] | None = None,
        tags: list[str] | None = None,
    ) -> dict[str, object]:
        require_configuration(self.onboarding_service)
        service = self.table_skill_service_factory()
        skill = TableSkill(
            database_name=database_name,
            table_name=table_name,
            description=description,
            content_markdown=content_markdown,
            summary=summary,
            business_context=business_context,
            common_use_cases=common_use_cases or [],
            tags=tags or [],
        )
        return service.create_or_update_table_skill(skill).model_dump(mode="json")
