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
from athena_knowledge_mcp.services.table_skill_service import TableSkillService
from athena_knowledge_mcp.utils.paths import resolve_runtime_path


@dataclass(slots=True)
class AthenaHandlers:
    onboarding_service: OnboardingService
    athena_service_factory: Callable[[], AthenaService]
    materialization_service_factory: Callable[[AthenaService], ResultMaterializationService]
    table_skill_service_factory: Callable[[], TableSkillService]

    def list_athena_databases(
        self,
        catalog: str | None = None,
    ) -> list[dict[str, object]]:
        require_configuration(self.onboarding_service)
        resolved = self.onboarding_service.get_resolved_configuration()
        assert resolved is not None
        service = self.athena_service_factory()
        return [
            database.model_dump(mode="json")
            for database in service.list_databases(
                resolved,
                catalog=catalog,
            )
        ]

    def list_athena_tables(
        self,
        database_name: str,
        catalog: str | None = None,
        name_prefix: str | None = None,
    ) -> list[dict[str, object]]:
        require_configuration(self.onboarding_service)
        resolved = self.onboarding_service.get_resolved_configuration()
        assert resolved is not None
        service = self.athena_service_factory()
        return [
            table.model_dump(mode="json")
            for table in service.list_tables(
                resolved,
                database_name=database_name,
                catalog=catalog,
                name_prefix=name_prefix,
            )
        ]

    def get_athena_table_metadata(
        self,
        database_name: str,
        table_name: str,
        catalog: str | None = None,
    ) -> dict[str, object]:
        require_configuration(self.onboarding_service)
        resolved = self.onboarding_service.get_resolved_configuration()
        assert resolved is not None
        service = self.athena_service_factory()
        return service.get_table_metadata(
            resolved,
            database_name=database_name,
            table_name=table_name,
            catalog=catalog,
        ).model_dump(mode="json")

    def sync_athena_database_to_catalog(
        self,
        database_name: str,
        catalog: str | None = None,
        name_prefix: str | None = None,
        max_tables: int | None = None,
        overwrite_existing: bool = False,
    ) -> dict[str, object]:
        require_configuration(self.onboarding_service)
        resolved = self.onboarding_service.get_resolved_configuration()
        assert resolved is not None
        service = self.athena_service_factory()
        table_skill_service = self.table_skill_service_factory()
        return service.sync_database_to_catalog(
            resolved,
            database_name=database_name,
            table_skill_service=table_skill_service,
            catalog=catalog,
            name_prefix=name_prefix,
            max_tables=max_tables,
            overwrite_existing=overwrite_existing,
        )

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
        resolved = self.onboarding_service.get_resolved_configuration()
        assert resolved is not None
        request = AthenaQueryRequest(
            query=query,
            database=database,
            catalog=catalog,
            workgroup=workgroup,
            wait_for_completion=wait_for_completion,
            max_wait_seconds=max_wait_seconds,
        )
        service = self.athena_service_factory()
        return service.execute_query(request, resolved).model_dump(mode="json")

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
        resolved = self.onboarding_service.get_resolved_configuration()
        assert resolved is not None
        athena_service = self.athena_service_factory()
        record = athena_service.get_query_status(query_execution_id)
        materialization_service = self.materialization_service_factory(athena_service)
        return materialization_service.materialize(
            record,
            resolve_runtime_path(resolved.local_large_results_folder),
        ).model_dump(mode="json")

    def list_local_result_files(self) -> list[str]:
        require_configuration(self.onboarding_service)
        resolved = self.onboarding_service.get_resolved_configuration()
        assert resolved is not None
        materialization_service = self.materialization_service_factory(
            self.athena_service_factory()
        )
        return materialization_service.list_materialized_files(
            resolve_runtime_path(resolved.local_large_results_folder)
        )
