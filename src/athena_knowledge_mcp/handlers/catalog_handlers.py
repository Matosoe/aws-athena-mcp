from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from athena_knowledge_mcp.server.middleware import require_configuration
from athena_knowledge_mcp.services.onboarding_service import OnboardingService
from athena_knowledge_mcp.services.s3_catalog_service import S3CatalogService


@dataclass(slots=True)
class CatalogHandlers:
    onboarding_service: OnboardingService
    catalog_service_factory: Callable[[], S3CatalogService]

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