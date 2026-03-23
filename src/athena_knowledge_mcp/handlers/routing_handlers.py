from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from athena_knowledge_mcp.server.middleware import require_configuration
from athena_knowledge_mcp.services.onboarding_service import OnboardingService
from athena_knowledge_mcp.services.request_routing_service import RequestRoutingService


@dataclass(slots=True)
class RoutingHandlers:
    onboarding_service: OnboardingService
    request_routing_service_factory: Callable[[], RequestRoutingService]

    def route_user_request_context(
        self,
        user_request: str,
        database_name: str | None = None,
        table_name: str | None = None,
        limit: int = 5,
    ) -> dict[str, object]:
        require_configuration(self.onboarding_service)
        service = self.request_routing_service_factory()
        return service.route_request(
            user_request=user_request,
            database_name=database_name,
            table_name=table_name,
            limit=limit,
        )
