from __future__ import annotations

import re
from dataclasses import dataclass

from athena_knowledge_mcp.services.s3_catalog_service import S3CatalogService
from athena_knowledge_mcp.services.skill_catalog_service import SkillCatalogService


@dataclass(slots=True)
class RequestRoutingService:
    table_catalog_service: S3CatalogService
    skill_catalog_service: SkillCatalogService

    _DB_TABLE_PATTERN = re.compile(r"\b[a-zA-Z0-9_]+\.[a-zA-Z0-9_]+\b")

    def route_request(
        self,
        user_request: str,
        database_name: str | None = None,
        table_name: str | None = None,
        limit: int = 5,
    ) -> dict[str, object]:
        normalized_request = user_request.strip()
        if not normalized_request:
            return {
                "route": "skill_catalog",
                "reason": "Pedido vazio. Comece pela busca de skills para orientar contexto.",
                "table_matches": [],
                "skill_matches": [],
                "should_scan_athena": False,
                "next_recommended_tools": ["search_skill_catalog"],
            }

        if self._has_explicit_table_context(normalized_request, database_name, table_name):
            explicit_database = database_name
            explicit_table = table_name
            if not explicit_database or not explicit_table:
                inferred_database, inferred_table = self._extract_db_table(normalized_request)
                explicit_database = explicit_database or inferred_database
                explicit_table = explicit_table or inferred_table

            table_matches: list[dict[str, object]] = []
            if explicit_database and explicit_table:
                direct_entry = self.table_catalog_service.get_entry(
                    explicit_database,
                    explicit_table,
                )
                if direct_entry is not None:
                    table_matches.append(direct_entry.model_dump(mode="json"))

            table_query = " ".join(
                token
                for token in [normalized_request, database_name or "", table_name or ""]
                if token
            )
            if not table_matches:
                table_matches = [
                    entry.model_dump(mode="json")
                    for entry in self.table_catalog_service.search(table_query, limit)
                ]
            should_scan_athena = len(table_matches) == 0
            return {
                "route": "table_catalog",
                "reason": "Pedido com contexto de database/tabela. Priorizar indice de tabelas.",
                "table_matches": table_matches,
                "skill_matches": [],
                "should_scan_athena": should_scan_athena,
                "next_recommended_tools": (
                    ["get_table_skill", "execute_athena_query"]
                    if table_matches
                    else ["search_skill_catalog", "list_athena_tables"]
                ),
            }

        skill_matches = [
            entry.model_dump(mode="json")
            for entry in self.skill_catalog_service.search(normalized_request, limit)
        ]
        table_matches: list[dict[str, object]] = []
        if not skill_matches:
            table_matches = [
                entry.model_dump(mode="json")
                for entry in self.table_catalog_service.search(normalized_request, limit)
            ]

        should_scan_athena = len(skill_matches) == 0 and len(table_matches) == 0
        return {
            "route": "skill_catalog",
            "reason": "Pedido sem contexto tecnico explicito. Priorizar indice de skills.",
            "table_matches": table_matches,
            "skill_matches": skill_matches,
            "should_scan_athena": should_scan_athena,
            "next_recommended_tools": self._next_tools(skill_matches, table_matches),
        }

    def _has_explicit_table_context(
        self,
        user_request: str,
        database_name: str | None,
        table_name: str | None,
    ) -> bool:
        if database_name and database_name.strip():
            return True
        if table_name and table_name.strip():
            return True
        if self._DB_TABLE_PATTERN.search(user_request):
            return True

        lowered = user_request.lower()
        context_keywords = ["database", "db", "tabela", "table"]
        return any(keyword in lowered for keyword in context_keywords)

    def _extract_db_table(self, user_request: str) -> tuple[str | None, str | None]:
        match = self._DB_TABLE_PATTERN.search(user_request)
        if not match:
            return None, None
        database_name, table_name = match.group(0).split(".", maxsplit=1)
        return database_name, table_name

    @staticmethod
    def _next_tools(
        skill_matches: list[dict[str, object]],
        table_matches: list[dict[str, object]],
    ) -> list[str]:
        if skill_matches:
            return ["get_table_skill", "execute_athena_query"]
        if table_matches:
            return ["get_table_skill", "execute_athena_query"]
        return ["search_table_catalog", "list_athena_databases"]
