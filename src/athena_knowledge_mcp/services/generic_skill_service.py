from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime

from athena_knowledge_mcp.core.models import GenericSkill, SkillCatalogEntry
from athena_knowledge_mcp.repositories.s3_skill_repository import S3SkillRepository
from athena_knowledge_mcp.services.skill_catalog_service import SkillCatalogService


# --------------------------------------------------------------------------- #
# Markdown helpers                                                             #
# --------------------------------------------------------------------------- #

def _extract_first_heading(content: str) -> str | None:
    """Return the text of the first Markdown H1 line, or None."""
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped.lstrip("# ").strip()
    return None


def _extract_summary(content: str, max_chars: int = 300) -> str:
    """Return the first non-heading paragraph, truncated to *max_chars*."""
    current: list[str] = []
    paragraphs: list[str] = []

    for line in content.splitlines():
        if line.strip().startswith("#"):
            if current:
                paragraphs.append(" ".join(current).strip())
                current = []
            continue
        if line.strip():
            current.append(line.strip())
        elif current:
            paragraphs.append(" ".join(current).strip())
            current = []

    if current:
        paragraphs.append(" ".join(current).strip())

    text = " ".join(paragraphs[:2]) if paragraphs else content
    return text[:max_chars].strip()


# --------------------------------------------------------------------------- #
# Key parsing helpers                                                          #
# --------------------------------------------------------------------------- #

def _parse_skill_from_key(key: str, prefix: str) -> dict[str, str | None] | None:
    """Parse an S3 key (or normalised virtual key) into skill metadata fields.

    Returns a dict with keys ``skill_id``, ``database_name``, ``table_name``
    or *None* when the key does not map to a recognised skill layout.
    """
    relative = key
    if prefix:
        clean_prefix = prefix.strip("/")
        if relative.startswith(clean_prefix + "/"):
            relative = relative[len(clean_prefix) + 1:]

    if not relative.endswith(".md"):
        return None

    # skills/tables/{db}/{table}.md
    m = re.match(r"^skills/tables/([^/]+)/([^/]+)\.md$", relative)
    if m:
        db, tbl = m.group(1), m.group(2)
        return {"skill_id": f"{db}.{tbl}", "database_name": db, "table_name": tbl}

    # skills/general/{skill_id}.md
    m = re.match(r"^skills/general/([^/]+)\.md$", relative)
    if m:
        return {"skill_id": m.group(1), "database_name": None, "table_name": None}

    # Any other skills/{...}.md — derive skill_id from path
    m = re.match(r"^skills/(.+)\.md$", relative)
    if m:
        skill_id = m.group(1).replace("/", "__")
        return {"skill_id": skill_id, "database_name": None, "table_name": None}

    return None


# --------------------------------------------------------------------------- #
# Service                                                                      #
# --------------------------------------------------------------------------- #

@dataclass(slots=True)
class GenericSkillService:
    """Manage non-table-bound skills and the independent skill index."""

    skill_repository: S3SkillRepository
    skill_catalog_service: SkillCatalogService

    # ------------------------------------------------------------------ #
    # CRUD                                                                 #
    # ------------------------------------------------------------------ #

    def get_skill(self, skill_id: str) -> dict[str, str]:
        """Return the raw markdown content for any skill by *skill_id*."""
        content = self.skill_repository.read_skill_by_id(skill_id)
        return {"skill_id": skill_id, "content_markdown": content}

    def create_or_update_skill(self, skill: GenericSkill) -> SkillCatalogEntry:
        """Persist a generic skill file and upsert its catalog entry."""
        if skill.database_name and skill.table_name:
            # Store under the table-scoped path when db/table is provided.
            detail_uri = self.skill_repository.save_skill(
                skill.database_name, skill.table_name, skill.content_markdown
            )
        else:
            detail_uri = self.skill_repository.save_generic_skill(
                skill.skill_id, skill.content_markdown
            )

        entry = SkillCatalogEntry(
            skill_id=skill.skill_id,
            title=skill.title,
            summary=skill.summary,
            description=skill.description,
            database_name=skill.database_name,
            table_name=skill.table_name,
            detail_file_s3_uri=detail_uri,
            tags=skill.tags,
            last_updated_at=skill.updated_at,
        )
        return self.skill_catalog_service.upsert_entry(entry)

    # ------------------------------------------------------------------ #
    # Index rebuild                                                         #
    # ------------------------------------------------------------------ #

    def rebuild_index_from_s3(self) -> dict[str, object]:
        """Scan all skill files in S3 and rebuild the skill index.

        Walks the ``skills/`` namespace, reads every ``.md`` file,
        extracts title and summary from its Markdown content, and
        overwrites the ``skill_catalog/skill_index.jsonl`` index.

        Returns a summary dict with ``indexed`` count and any ``errors``.
        """
        keys = self.skill_repository.list_all_skill_keys()
        prefix = self.skill_repository.prefix
        bucket = self.skill_repository.bucket
        entries: list[SkillCatalogEntry] = []
        errors: list[str] = []

        for key in keys:
            parsed = _parse_skill_from_key(key, prefix)
            if parsed is None:
                continue
            try:
                content = self.skill_repository.read_by_key(key)
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{key}: {exc}")
                continue

            title = _extract_first_heading(content) or parsed["skill_id"]
            summary = _extract_summary(content)
            if self.skill_repository.is_local:
                detail_uri = key
            else:
                detail_uri = f"s3://{bucket}/{key}"

            entries.append(
                SkillCatalogEntry(
                    skill_id=parsed["skill_id"],
                    title=title,
                    summary=summary,
                    description=summary,
                    database_name=parsed.get("database_name"),
                    table_name=parsed.get("table_name"),
                    detail_file_s3_uri=detail_uri,
                    tags=[],
                    last_updated_at=datetime.now(UTC),
                )
            )

        entries.sort(key=lambda e: e.skill_id)
        self.skill_catalog_service.repository.save_entries(entries)
        return {"indexed": len(entries), "errors": errors}
