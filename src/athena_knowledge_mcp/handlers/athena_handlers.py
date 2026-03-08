from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from athena_knowledge_mcp.core.models import AthenaQueryRequest
from athena_knowledge_mcp.server.middleware import require_configuration
from athena_knowledge_mcp.services.athena_service import AthenaService
from athena_knowledge_mcp.services.onboarding_service import OnboardingService
from athena_knowledge_mcp.services.result_materialization_service import (
    ResultMaterializationService,
)


@dataclass(slots=True)
class AthenaHandlers:
    onboarding_service: OnboardingService
    athena_service_factory: Callable[[], AthenaService]
    materialization_service_factory: Callable[[AthenaService], ResultMaterializationService]

    def execute_athena_query(
        self,
        query: str,
        database: str | None = None,
        catalog: str | None = None,
        workgroup: str | None = None,
        wait_for_completion: bool = True,
        max_wait_seconds: int = 300,
    ) -> dict[str, object]:
        require_configuration(self.onboarding_service)
        configuration = self.onboarding_service.config_repository.load_configuration()
        assert configuration is not None
        request = AthenaQueryRequest(
            query=query,
            database=database,
            catalog=catalog,
            workgroup=workgroup,
            wait_for_completion=wait_for_completion,
            max_wait_seconds=max_wait_seconds,
        )
        service = self.athena_service_factory()
        return service.execute_query(request, configuration).model_dump(mode="json")

    def get_query_execution_status(self, query_execution_id: str) -> dict[str, object]:
        require_configuration(self.onboarding_service)
        service = self.athena_service_factory()
        return service.get_query_status(query_execution_id).model_dump(mode="json")

    def fetch_query_result_preview(self, query_execution_id: str) -> dict[str, object]:
        require_configuration(self.onboarding_service)
        service = self.athena_service_factory()
        return service.fetch_result_preview(query_execution_id).model_dump(mode="json")

    def materialize_large_result_locally(self, query_execution_id: str) -> dict[str, object]:
        require_configuration(self.onboarding_service)
        configuration = self.onboarding_service.config_repository.load_configuration()
        assert configuration is not None
        athena_service = self.athena_service_factory()
        record = athena_service.get_query_status(query_execution_id)
        materialization_service = self.materialization_service_factory(athena_service)
        return materialization_service.materialize(
            record,
            configuration.local_large_results_folder,
        ).model_dump(mode="json")

    def list_local_result_files(self) -> list[str]:
        require_configuration(self.onboarding_service)
        configuration = self.onboarding_service.config_repository.load_configuration()
        assert configuration is not None
        materialization_service = self.materialization_service_factory(
            self.athena_service_factory()
        )
        return materialization_service.list_materialized_files(
            configuration.local_large_results_folder
        )