from __future__ import annotations

from dataclasses import dataclass

from athena_knowledge_mcp.core.models import CatalogEntry
from athena_knowledge_mcp.repositories.s3_catalog_repository import S3CatalogRepository


@dataclass(slots=True)
class S3CatalogService:
    repository: S3CatalogRepository

    def search(self, query: str, limit: int = 5) -> list[CatalogEntry]:
        terms = [term.strip().lower() for term in query.split() if term.strip()]
        entries = self.repository.load_entries()
        if not terms:
            return entries[:limit]

        scored_entries: list[tuple[int, CatalogEntry]] = []
        for entry in entries:
            haystack = entry.searchable_text()
            score = sum(1 for term in terms if term in haystack)
            if score:
                scored_entries.append((score, entry))

        scored_entries.sort(key=lambda item: (-item[0], item[1].database_name, item[1].table_name))
        return [entry for _, entry in scored_entries[:limit]]

    def list_databases(self) -> list[str]:
        entries = self.repository.load_entries()
        return sorted({entry.database_name for entry in entries})

    def list_database_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for entry in self.repository.load_entries():
            counts[entry.database_name] = counts.get(entry.database_name, 0) + 1
        return dict(sorted(counts.items()))

    def list_tables(self, database_name: str) -> list[CatalogEntry]:
        entries = self.repository.load_entries()
        filtered_entries = [
            entry for entry in entries if entry.database_name.lower() == database_name.lower()
        ]
        filtered_entries.sort(key=lambda item: item.table_name)
        return filtered_entries

    def get_entry(self, database_name: str, table_name: str) -> CatalogEntry | None:
        normalized_database = database_name.lower()
        normalized_table = table_name.lower()
        for entry in self.repository.load_entries():
            if (
                entry.database_name.lower() == normalized_database
                and entry.table_name.lower() == normalized_table
            ):
                return entry
        return None

    def upsert_entry(self, entry: CatalogEntry) -> CatalogEntry:
        entries = self.repository.load_entries()
        updated_entries = [
            current
            for current in entries
            if not (
                current.database_name == entry.database_name
                and current.table_name == entry.table_name
            )
        ]
        updated_entries.append(entry)
        updated_entries.sort(key=lambda item: (item.database_name, item.table_name))
        self.repository.save_entries(updated_entries)
        return entry

    def refresh_index(self) -> dict[str, int]:
        count = len(self.repository.load_entries())
        return {"entries": count}