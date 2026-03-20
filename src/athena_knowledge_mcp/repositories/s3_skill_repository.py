from __future__ import annotations

from pathlib import Path
from typing import Any

from athena_knowledge_mcp.core.aws_errors import raise_if_aws_access_denied


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

    def read_skill(self, database_name: str, table_name: str) -> str:
        if self._local_root is not None:
            file_path = self._local_root / database_name / f"{table_name}.md"
            return file_path.read_text(encoding="utf-8")

        if self._s3_client is None:
            raise RuntimeError("S3 client nao configurado")
        try:
            response = self._s3_client.get_object(
                Bucket=self._bucket,
                Key=self._skill_key(database_name, table_name),
            )
        except Exception as exc:
            raise_if_aws_access_denied(exc, "S3")
            raise
        return response["Body"].read().decode("utf-8")

    def save_skill(self, database_name: str, table_name: str, content_markdown: str) -> str:
        if self._local_root is not None:
            folder = self._local_root / database_name
            folder.mkdir(parents=True, exist_ok=True)
            file_path = folder / f"{table_name}.md"
            file_path.write_text(content_markdown, encoding="utf-8")
            return file_path.as_posix()

        key = self._skill_key(database_name, table_name)
        if self._s3_client is None:
            raise RuntimeError("S3 client nao configurado")
        try:
            self._s3_client.put_object(
                Bucket=self._bucket,
                Key=key,
                Body=content_markdown.encode("utf-8"),
            )
        except Exception as exc:
            raise_if_aws_access_denied(exc, "S3")
            raise
        return f"s3://{self._bucket}/{key}"

    def _skill_key(self, database_name: str, table_name: str) -> str:
        base = f"skills/tables/{database_name}/{table_name}.md"
        if not self._prefix:
            return base
        return f"{self._prefix}/{base}"