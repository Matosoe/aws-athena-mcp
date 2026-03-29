from __future__ import annotations

import re
from pathlib import Path
from typing import Any


def _sanitize_skill_id(skill_id: str) -> str:
    """Sanitize skill_id to prevent path-traversal attacks.

    Keeps alphanumeric chars, dots, hyphens and underscores.
    """
    sanitized = re.sub(r"[^a-zA-Z0-9._\-]", "_", skill_id)
    while ".." in sanitized:
        sanitized = sanitized.replace("..", "_")
    return sanitized.strip("./") or "unnamed_skill"


class S3SkillRepository:
    def __init__(
        self,
        bucket: str,
        prefix: str,
        s3_client: Any | None = None,
        local_root: Path | None = None,
    ) -> None:
        self._bucket = bucket
        self._prefix = prefix.strip("/")
        self._s3_client = s3_client
        self._local_root = local_root

    @property
    def bucket(self) -> str:
        return self._bucket

    @property
    def prefix(self) -> str:
        return self._prefix

    @property
    def is_local(self) -> bool:
        return self._local_root is not None

    # ------------------------------------------------------------------ #
    # Table-scoped skills (legacy entry-point)                             #
    # ------------------------------------------------------------------ #

    def read_skill(self, database_name: str, table_name: str) -> str:
        if self._local_root is not None:
            file_path = self._local_root / database_name / f"{table_name}.md"
            return file_path.read_text(encoding="utf-8")

        if self._s3_client is None:
            raise RuntimeError("S3 client nao configurado")
        response = self._s3_client.get_object(
            Bucket=self._bucket,
            Key=self._skill_key(database_name, table_name),
        )
        return response["Body"].read().decode("utf-8")

    def save_skill(
        self, database_name: str, table_name: str, content_markdown: str
    ) -> str:
        if self._local_root is not None:
            folder = self._local_root / database_name
            folder.mkdir(parents=True, exist_ok=True)
            file_path = folder / f"{table_name}.md"
            file_path.write_text(content_markdown, encoding="utf-8")
            return file_path.as_posix()

        key = self._skill_key(database_name, table_name)
        if self._s3_client is None:
            raise RuntimeError("S3 client nao configurado")
        self._s3_client.put_object(
            Bucket=self._bucket,
            Key=key,
            Body=content_markdown.encode("utf-8"),
        )
        return f"s3://{self._bucket}/{key}"

    # ------------------------------------------------------------------ #
    # Generic (non-table-bound) skills                                     #
    # ------------------------------------------------------------------ #

    def read_skill_by_id(self, skill_id: str) -> str:
        """Read any skill file by skill_id.

        For table skills (skill_id == "db.table") falls back to the
        table-scoped path; otherwise uses the generic path.
        """
        parts = skill_id.split(".", 1)
        if len(parts) == 2:
            try:
                return self.read_skill(parts[0], parts[1])
            except Exception:  # noqa: BLE001
                pass  # fall through to generic-skill path
        safe_id = _sanitize_skill_id(skill_id)
        if self._local_root is not None:
            path = self._local_root / "general" / f"{safe_id}.md"
            return path.read_text(encoding="utf-8")
        if self._s3_client is None:
            raise RuntimeError("S3 client nao configurado")
        response = self._s3_client.get_object(
            Bucket=self._bucket,
            Key=self._generic_skill_key(safe_id),
        )
        return response["Body"].read().decode("utf-8")

    def save_generic_skill(self, skill_id: str, content_markdown: str) -> str:
        """Save a generic skill and return its storage URI."""
        safe_id = _sanitize_skill_id(skill_id)
        if self._local_root is not None:
            folder = self._local_root / "general"
            folder.mkdir(parents=True, exist_ok=True)
            path = folder / f"{safe_id}.md"
            path.write_text(content_markdown, encoding="utf-8")
            return path.as_posix()
        key = self._generic_skill_key(safe_id)
        if self._s3_client is None:
            raise RuntimeError("S3 client nao configurado")
        self._s3_client.put_object(
            Bucket=self._bucket,
            Key=key,
            Body=content_markdown.encode("utf-8"),
        )
        return f"s3://{self._bucket}/{key}"

    # ------------------------------------------------------------------ #
    # Index rebuild support                                                #
    # ------------------------------------------------------------------ #

    def list_all_skill_keys(self) -> list[str]:
        """Return all skill file keys under the skills/ namespace.

        In S3 mode returns full object keys; in local mode returns
        normalised virtual keys in the same S3-style layout.
        """
        if self._local_root is not None:
            return self._list_local_skill_keys()
        if self._s3_client is None:
            raise RuntimeError("S3 client nao configurado")
        skills_prefix = (
            f"{self._prefix}/skills/" if self._prefix else "skills/"
        )
        paginator = self._s3_client.get_paginator("list_objects_v2")
        keys: list[str] = []
        for page in paginator.paginate(
            Bucket=self._bucket, Prefix=skills_prefix
        ):
            for obj in page.get("Contents", []):
                if obj["Key"].endswith(".md"):
                    keys.append(obj["Key"])
        return keys

    def read_by_key(self, key: str) -> str:
        """Read a skill file by its raw storage key."""
        if self._local_root is not None:
            # Map the normalised virtual key back to the local FS path.
            relative = key
            if self._prefix:
                clean = self._prefix.strip("/")
                if relative.startswith(clean + "/"):
                    relative = relative[len(clean) + 1:]
            if relative.startswith("skills/tables/"):
                relative = relative[len("skills/tables/"):]
            elif relative.startswith("skills/"):
                relative = relative[len("skills/"):]
            return (self._local_root / relative).read_text(encoding="utf-8")
        if self._s3_client is None:
            raise RuntimeError("S3 client nao configurado")
        response = self._s3_client.get_object(Bucket=self._bucket, Key=key)
        return response["Body"].read().decode("utf-8")

    # ------------------------------------------------------------------ #
    # Private helpers                                                      #
    # ------------------------------------------------------------------ #

    def _list_local_skill_keys(self) -> list[str]:
        """Enumerate local skill files and return normalised S3-style keys."""
        assert self._local_root is not None
        base_prefix = f"{self._prefix}/" if self._prefix else ""
        keys: list[str] = []
        for path in sorted(self._local_root.rglob("*.md")):
            rel = path.relative_to(self._local_root).as_posix()
            if rel.startswith("general/"):
                virtual = f"skills/{rel}"
            else:
                # Legacy table layout: {db}/{table}.md
                parts = rel.split("/")
                if len(parts) == 2:
                    virtual = f"skills/tables/{rel}"
                else:
                    virtual = f"skills/{rel}"
            keys.append(f"{base_prefix}{virtual}")
        return keys

    def _skill_key(self, database_name: str, table_name: str) -> str:
        base = f"skills/tables/{database_name}/{table_name}.md"
        if not self._prefix:
            return base
        return f"{self._prefix}/{base}"

    def _generic_skill_key(self, safe_skill_id: str) -> str:
        base = f"skills/general/{safe_skill_id}.md"
        if not self._prefix:
            return base
        return f"{self._prefix}/{base}"
