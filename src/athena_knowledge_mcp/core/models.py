from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, model_validator


DEFAULT_S3_PREFIX = "mcp/athena/"


def normalize_s3_prefix(value: str) -> str:
    normalized = value.strip().strip("/")
    if not normalized:
        return DEFAULT_S3_PREFIX
    return f"{normalized}/"


class AwsAuthenticationType(StrEnum):
    DEFAULT_CREDENTIALS = "default_credentials"
    PROFILE = "profile"
    ACCESS_KEY = "access_key"
    SESSION_TOKEN = "session_token"


class RuntimePaths(BaseModel):
    state_dir: Path = Field(default=Path("state"))
    downloads_dir: Path = Field(default=Path("downloads"))
    settings_file: Path = Field(default=Path("state/runtime_settings.json"))
    secrets_file: Path = Field(default=Path("state/secrets.json"))


class ServerConfiguration(BaseModel):
    """Preferencias do usuario persistidas localmente.

    Apenas os campos que variam por usuario e por sessao sao armazenados
    aqui. Os campos de infraestrutura (bucket, workgroup, regiao etc.) sao
    definidos em company_defaults.py.
    """

    aws_profile: str | None = None
    athena_databases: list[str] = Field(default_factory=list)
    default_database: str | None = None
    local_large_results_folder: Path = Field(default=Path("downloads"))
    inline_result_max_bytes: int = Field(default=500_000, ge=1)
    inline_result_max_rows: int = Field(default=200, ge=1)
    last_updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @model_validator(mode="after")
    def normalize_fields(self) -> ServerConfiguration:
        self.local_large_results_folder = Path(self.local_large_results_folder)
        self.athena_databases = [
            database.strip() for database in self.athena_databases if database and database.strip()
        ]
        if self.default_database is not None:
            self.default_database = self.default_database.strip() or None
        return self


@dataclass(slots=True)
class ResolvedConfig:
    """Configuracao completa em runtime.

    Une os defaults corporativos (company_defaults.py) com as preferencias
    do usuario (ServerConfiguration). Usado pelos servicos que precisam de
    todos os campos de infraestrutura.
    """

    # Campos fixos — vem de company_defaults.py
    aws_region: str
    authentication_type: AwsAuthenticationType
    athena_workgroup: str
    athena_catalog: str
    query_results_s3_bucket: str
    query_results_s3_prefix: str
    catalog_bucket: str
    catalog_prefix: str

    # Campos variaveis — vem de ServerConfiguration
    aws_profile: str | None
    athena_databases: list[str]
    default_database: str | None
    local_large_results_folder: Path
    inline_result_max_bytes: int
    inline_result_max_rows: int


class AwsSecretMaterial(BaseModel):
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    aws_session_token: str | None = None


class ConfigurationStatus(BaseModel):
    is_configured: bool
    missing_fields: list[str] = Field(default_factory=list)
    last_updated_at: datetime | None = None
    catalog_last_sync_at: datetime | None = None
    next_step: str | None = None


class AthenaQueryRequest(BaseModel):
    query: str
    database: str | None = None
    catalog: str | None = None
    workgroup: str | None = None
    wait_for_completion: bool = True
    max_wait_seconds: int = Field(default=300, ge=1, le=3600)


class QueryResultPreview(BaseModel):
    columns: list[str]
    rows: list[list[str | None]]
    row_count: int


class QueryExecutionRecord(BaseModel):
    query_execution_id: str
    status: str
    submitted_query: str
    database: str | None = None
    catalog: str
    workgroup: str
    output_location: str | None = None
    result_size_bytes: int | None = None
    completion_reason: str | None = None
    execution_time_ms: int | None = None
    preview: QueryResultPreview | None = None
    next_step: str | None = None


class AthenaDatabaseSummary(BaseModel):
    name: str
    sources: list[str] = Field(default_factory=list)
    cached_table_count: int = 0


class AthenaTableSummary(BaseModel):
    database_name: str
    table_name: str
    sources: list[str] = Field(default_factory=list)
    summary: str | None = None
    detail_file_s3_uri: str | None = None
    tags: list[str] = Field(default_factory=list)


class AthenaColumnMetadata(BaseModel):
    name: str
    type: str
    comment: str | None = None


class AthenaTableMetadata(BaseModel):
    database_name: str
    table_name: str
    catalog: str
    sources: list[str] = Field(default_factory=list)
    table_type: str | None = None
    owner: str | None = None
    create_time: datetime | None = None
    last_access_time: datetime | None = None
    columns: list[AthenaColumnMetadata] = Field(default_factory=list)
    partition_keys: list[AthenaColumnMetadata] = Field(default_factory=list)
    parameters: dict[str, str | None] = Field(default_factory=dict)
    summary: str | None = None
    business_context: str = ""
    common_use_cases: list[str] = Field(default_factory=list)
    detail_file_s3_uri: str | None = None
    tags: list[str] = Field(default_factory=list)


class CatalogEntry(BaseModel):
    database_name: str
    table_name: str
    summary: str
    business_context: str = ""
    common_use_cases: list[str] = Field(default_factory=list)
    detail_file_s3_uri: str
    tags: list[str] = Field(default_factory=list)
    last_updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def searchable_text(self) -> str:
        parts = [
            self.database_name,
            self.table_name,
            self.summary,
            self.business_context,
            " ".join(self.common_use_cases),
            " ".join(self.tags),
        ]
        return " ".join(part.lower() for part in parts if part)


class SkillCatalogEntry(BaseModel):
    skill_id: str
    title: str
    summary: str
    description: str = ""
    database_name: str | None = None
    table_name: str | None = None
    detail_file_s3_uri: str
    tags: list[str] = Field(default_factory=list)
    last_updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @model_validator(mode="after")
    def normalize_fields(self) -> SkillCatalogEntry:
        self.skill_id = self.skill_id.strip()
        self.title = self.title.strip()
        self.summary = self.summary.strip()
        self.description = self.description.strip()
        if self.database_name is not None:
            self.database_name = self.database_name.strip() or None
        if self.table_name is not None:
            self.table_name = self.table_name.strip() or None
        return self

    def searchable_text(self) -> str:
        parts = [
            self.skill_id,
            self.title,
            self.summary,
            self.description,
            self.database_name or "",
            self.table_name or "",
            " ".join(self.tags),
        ]
        return " ".join(part.lower() for part in parts if part)


class TableSkill(BaseModel):
    database_name: str
    table_name: str
    description: str
    content_markdown: str
    summary: str
    business_context: str = ""
    common_use_cases: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class MaterializedResult(BaseModel):
    query_execution_id: str
    local_path: Path
    source_s3_uri: str
    size_bytes: int


class OperationResult(BaseModel):
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
