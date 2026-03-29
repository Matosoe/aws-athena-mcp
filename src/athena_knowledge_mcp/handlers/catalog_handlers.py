from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from athena_knowledge_mcp.server.middleware import require_configuration
from athena_knowledge_mcp.services.generic_skill_service import GenericSkillService
from athena_knowledge_mcp.services.onboarding_service import OnboardingService
from athena_knowledge_mcp.services.s3_catalog_service import S3CatalogService
from athena_knowledge_mcp.services.skill_catalog_service import SkillCatalogService


@dataclass(slots=True)
class CatalogHandlers:
    onboarding_service: OnboardingService
    catalog_service_factory: Callable[[], S3CatalogService]
    skill_catalog_service_factory: Callable[[], SkillCatalogService]
    generic_skill_service_factory: Callable[[], GenericSkillService]

    # ------------------------------------------------------------------ #
    # Table catalog                                                         #
    # ------------------------------------------------------------------ #

    def search_table_catalog(self, query: str, limit: int = 5) -> list[dict[str, object]]:
        require_configuration(self.onboarding_service)
        service = self.catalog_service_factory()
        return [entry.model_dump(mode="json") for entry in service.search(query, limit)]

    def list_catalog_databases(self) -> list[str]:
        require_configuration(self.onboarding_service)
        service = self.catalog_service_factory()
        return service.list_databases()

    def list_catalog_tables(self, database_name: str) -> list[dict[str, object]]:
        require_configuration(self.onboarding_service)
        service = self.catalog_service_factory()
        return [entry.model_dump(mode="json") for entry in service.list_tables(database_name)]

    def refresh_catalog_index(self) -> dict[str, int]:
        require_configuration(self.onboarding_service)
        service = self.catalog_service_factory()
        return service.refresh_index()

    # ------------------------------------------------------------------ #
    # Skill catalog                                                         #
    # ------------------------------------------------------------------ #

    def search_skill_catalog(self, query: str, limit: int = 5) -> list[dict[str, object]]:
        require_configuration(self.onboarding_service)
        service = self.skill_catalog_service_factory()
        return [entry.model_dump(mode="json") for entry in service.search(query, limit)]

    def list_catalog_skills(self) -> list[dict[str, object]]:
        require_configuration(self.onboarding_service)
        service = self.skill_catalog_service_factory()
        return [entry.model_dump(mode="json") for entry in service.list_skills()]

    def refresh_skill_index(self) -> dict[str, object]:
        """Scan all skill files in S3 and rebuild the skill index.

        Reads every Markdown file under the ``skills/`` namespace,
        auto-extracts title and summary, and overwrites the persisted
        skill index.  Returns ``{"indexed": N, "errors": [...]}``.
        """
        require_configuration(self.onboarding_service)
        service = self.generic_skill_service_factory()
        return service.rebuild_index_from_s3()
