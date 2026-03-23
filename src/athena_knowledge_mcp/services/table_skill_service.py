from __future__ import annotations

from dataclasses import dataclass

from athena_knowledge_mcp.core.exceptions import CatalogEntryNotFoundError
from athena_knowledge_mcp.core.models import CatalogEntry, SkillCatalogEntry, TableSkill
from athena_knowledge_mcp.repositories.s3_skill_repository import S3SkillRepository
from athena_knowledge_mcp.services.s3_catalog_service import S3CatalogService
from athena_knowledge_mcp.services.skill_catalog_service import SkillCatalogService


@dataclass(slots=True)
class TableSkillService:
    skill_repository: S3SkillRepository
    catalog_service: S3CatalogService
    skill_catalog_service: SkillCatalogService

    def get_table_skill(self, database_name: str, table_name: str) -> dict[str, str]:
        try:
            content = self.skill_repository.read_skill(database_name, table_name)
        except FileNotFoundError as exc:
            raise CatalogEntryNotFoundError(
                f"Skill nao encontrada para {database_name}.{table_name}"
            ) from exc
        return {
            "database_name": database_name,
            "table_name": table_name,
            "content_markdown": content,
        }

    def create_or_update_table_skill(self, skill: TableSkill) -> CatalogEntry:
        detail_uri = self.skill_repository.save_skill(
            skill.database_name,
            skill.table_name,
            skill.content_markdown,
        )
        entry = CatalogEntry(
            database_name=skill.database_name,
            table_name=skill.table_name,
            summary=skill.summary,
            business_context=skill.business_context,
            common_use_cases=skill.common_use_cases,
            detail_file_s3_uri=detail_uri,
            tags=skill.tags,
            last_updated_at=skill.updated_at,
        )
        self.skill_catalog_service.upsert_entry(
            SkillCatalogEntry(
                skill_id=f"{skill.database_name}.{skill.table_name}",
                title=skill.description,
                summary=skill.summary,
                description=skill.description,
                database_name=skill.database_name,
                table_name=skill.table_name,
                detail_file_s3_uri=detail_uri,
                tags=skill.tags,
                last_updated_at=skill.updated_at,
            )
        )
        return self.catalog_service.upsert_entry(entry)