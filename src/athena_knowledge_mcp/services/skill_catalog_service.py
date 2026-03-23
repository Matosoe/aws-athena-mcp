from __future__ import annotations

from dataclasses import dataclass

from athena_knowledge_mcp.core.models import SkillCatalogEntry
from athena_knowledge_mcp.repositories.s3_skill_catalog_repository import (
    S3SkillCatalogRepository,
)


@dataclass(slots=True)
class SkillCatalogService:
    repository: S3SkillCatalogRepository

    def search(self, query: str, limit: int = 5) -> list[SkillCatalogEntry]:
        terms = [term.strip().lower() for term in query.split() if term.strip()]
        entries = self.repository.load_entries()
        if not terms:
            return entries[:limit]

        scored_entries: list[tuple[int, SkillCatalogEntry]] = []
        for entry in entries:
            haystack = entry.searchable_text()
            score = sum(1 for term in terms if term in haystack)
            if score:
                scored_entries.append((score, entry))

        scored_entries.sort(key=lambda item: (-item[0], item[1].skill_id))
        return [entry for _, entry in scored_entries[:limit]]

    def list_skills(self) -> list[SkillCatalogEntry]:
        entries = self.repository.load_entries()
        return sorted(entries, key=lambda item: item.skill_id)

    def get_entry(self, skill_id: str) -> SkillCatalogEntry | None:
        normalized_skill_id = skill_id.strip().lower()
        for entry in self.repository.load_entries():
            if entry.skill_id.lower() == normalized_skill_id:
                return entry
        return None

    def upsert_entry(self, entry: SkillCatalogEntry) -> SkillCatalogEntry:
        entries = self.repository.load_entries()
        updated_entries = [
            current for current in entries if current.skill_id.lower() != entry.skill_id.lower()
        ]
        updated_entries.append(entry)
        updated_entries.sort(key=lambda item: item.skill_id)
        self.repository.save_entries(updated_entries)
        return entry

    def refresh_index(self) -> dict[str, int]:
        count = len(self.repository.load_entries())
        return {"entries": count}
