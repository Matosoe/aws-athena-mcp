from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from athena_knowledge_mcp.core.config import AppConfig
from athena_knowledge_mcp.handlers.athena_handlers import AthenaHandlers
from athena_knowledge_mcp.handlers.aws_cli_handlers import AwsCliHandlers
from athena_knowledge_mcp.handlers.catalog_handlers import CatalogHandlers
from athena_knowledge_mcp.handlers.file_handlers import FileHandlers
from athena_knowledge_mcp.handlers.onboarding_handlers import OnboardingHandlers
from athena_knowledge_mcp.repositories.local_config_repository import LocalConfigRepository
from athena_knowledge_mcp.repositories.query_history_repository import QueryHistoryRepository
from athena_knowledge_mcp.repositories.s3_catalog_repository import S3CatalogRepository
from athena_knowledge_mcp.repositories.s3_skill_repository import S3SkillRepository
from athena_knowledge_mcp.server.lifecycle import build_container
from athena_knowledge_mcp.services.athena_service import AthenaService
from athena_knowledge_mcp.services.aws_cli_service import AwsCliService
from athena_knowledge_mcp.services.aws_session_service import AwsSessionService
from athena_knowledge_mcp.services.onboarding_service import OnboardingService
from athena_knowledge_mcp.services.result_materialization_service import (
    ResultMaterializationService,
)
from athena_knowledge_mcp.services.s3_catalog_service import S3CatalogService
from athena_knowledge_mcp.services.table_skill_service import TableSkillService


def _build_local_config_repository(config: AppConfig) -> LocalConfigRepository:
    return LocalConfigRepository(config.settings_store, config.secrets_store)


def build_app() -> FastMCP:
    container = build_container()
    config = container.config
    config_repository = _build_local_config_repository(config)
    aws_session_service = AwsSessionService()
    onboarding_service = OnboardingService(config_repository, aws_session_service)
    history_repository = QueryHistoryRepository(
        config.runtime_paths.state_dir / "query_history.jsonl"
    )

    def create_catalog_service() -> S3CatalogService:
        configuration = config_repository.load_configuration()
        secrets = config_repository.load_secrets()
        local_root: Any | None = config.runtime_paths.state_dir / "catalog"
        s3_client: Any | None = None
        if configuration is not None:
            try:
                s3_client = aws_session_service.build_client("s3", configuration, secrets)
                local_root = None
            except Exception:
                local_root = config.runtime_paths.state_dir / "catalog"
        repository = S3CatalogRepository(
            bucket=configuration.catalog_bucket if configuration else "local-catalog",
            prefix=configuration.catalog_prefix if configuration else "",
            s3_client=s3_client,
            local_root=local_root,
        )
        return S3CatalogService(repository)

    def create_table_skill_service() -> TableSkillService:
        configuration = config_repository.load_configuration()
        secrets = config_repository.load_secrets()
        local_root: Any | None = config.runtime_paths.state_dir / "skills"
        s3_client: Any | None = None
        if configuration is not None:
            try:
                s3_client = aws_session_service.build_client("s3", configuration, secrets)
                local_root = None
            except Exception:
                local_root = config.runtime_paths.state_dir / "skills"
        repository = S3SkillRepository(
            bucket=configuration.catalog_bucket if configuration else "local-catalog",
            prefix=configuration.catalog_prefix if configuration else "",
            s3_client=s3_client,
            local_root=local_root,
        )
        return TableSkillService(repository, create_catalog_service())

    def create_athena_service() -> AthenaService:
        configuration = config_repository.load_configuration()
        secrets = config_repository.load_secrets()
        athena_client: Any | None = None
        s3_client: Any | None = None
        if configuration is not None:
            try:
                athena_client = aws_session_service.build_client("athena", configuration, secrets)
                s3_client = aws_session_service.build_client("s3", configuration, secrets)
            except Exception:
                athena_client = None
                s3_client = None
        return AthenaService(history_repository, athena_client=athena_client, s3_client=s3_client)

    def create_materialization_service(
        athena_service: AthenaService,
    ) -> ResultMaterializationService:
        configuration = config_repository.load_configuration()
        secrets = config_repository.load_secrets()
        s3_client: Any | None = None
        if configuration is not None:
            try:
                s3_client = aws_session_service.build_client("s3", configuration, secrets)
            except Exception:
                s3_client = None
        return ResultMaterializationService(athena_service, s3_client=s3_client)

    onboarding_handlers = OnboardingHandlers(onboarding_service)
    catalog_handlers = CatalogHandlers(onboarding_service, create_catalog_service)
    file_handlers = FileHandlers(onboarding_service, create_table_skill_service)
    aws_cli_handlers = AwsCliHandlers(AwsCliService())
    athena_handlers = AthenaHandlers(
        onboarding_service,
        create_athena_service,
        create_materialization_service,
        create_table_skill_service,
    )

    mcp = FastMCP("AWS Athena Knowledge MCP", json_response=True)

    @mcp.tool(
        name="initialize_server_configuration",
        description=("Persist the initial AWS and Athena configuration used by the " "server."),
    )
    def initialize_server_configuration(
        authentication_type: str,
        aws_region: str,
        athena_workgroup: str,
        default_database: str,
        query_results_s3_bucket: str,
        query_results_s3_prefix: str,
        catalog_bucket: str,
        catalog_prefix: str,
        athena_catalog: str = "AwsDataCatalog",
        local_large_results_folder: str = "downloads",
        inline_result_max_bytes: int = 500000,
        inline_result_max_rows: int = 200,
        aws_profile: str | None = None,
        aws_access_key_id: str | None = None,
        aws_secret_access_key: str | None = None,
        aws_session_token: str | None = None,
        skip_aws_validation: bool = False,
    ) -> dict[str, object]:
        """Persist the initial AWS and Athena configuration.

        The stored settings are used by the MCP server on later calls.
        """
        return onboarding_handlers.initialize_server_configuration(
            authentication_type=authentication_type,
            aws_region=aws_region,
            athena_workgroup=athena_workgroup,
            default_database=default_database,
            query_results_s3_bucket=query_results_s3_bucket,
            query_results_s3_prefix=query_results_s3_prefix,
            catalog_bucket=catalog_bucket,
            catalog_prefix=catalog_prefix,
            athena_catalog=athena_catalog,
            local_large_results_folder=local_large_results_folder,
            inline_result_max_bytes=inline_result_max_bytes,
            inline_result_max_rows=inline_result_max_rows,
            aws_profile=aws_profile,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            aws_session_token=aws_session_token,
            skip_aws_validation=skip_aws_validation,
        )

    @mcp.tool(
        name="get_server_configuration_status",
        description=(
            "Return whether the server is configured and summarize the " "active settings."
        ),
    )
    def get_server_configuration_status() -> dict[str, object]:
        """Return whether the server is configured.

        Includes a summary of the active local settings.
        """
        return onboarding_handlers.get_server_configuration_status()

    @mcp.tool(
        name="update_server_configuration",
        description=("Update one or more persisted server configuration fields."),
    )
    def update_server_configuration(
        authentication_type: str | None = None,
        aws_region: str | None = None,
        athena_workgroup: str | None = None,
        default_database: str | None = None,
        query_results_s3_bucket: str | None = None,
        query_results_s3_prefix: str | None = None,
        catalog_bucket: str | None = None,
        catalog_prefix: str | None = None,
        athena_catalog: str | None = None,
        local_large_results_folder: str | None = None,
        inline_result_max_bytes: int | None = None,
        inline_result_max_rows: int | None = None,
        aws_profile: str | None = None,
        aws_access_key_id: str | None = None,
        aws_secret_access_key: str | None = None,
        aws_session_token: str | None = None,
        skip_aws_validation: bool = False,
    ) -> dict[str, object]:
        """Update persisted server configuration fields.

        This avoids recreating the full setup from scratch.
        """
        updates = {
            key: value
            for key, value in {
                "authentication_type": authentication_type,
                "aws_region": aws_region,
                "athena_workgroup": athena_workgroup,
                "default_database": default_database,
                "query_results_s3_bucket": query_results_s3_bucket,
                "query_results_s3_prefix": query_results_s3_prefix,
                "catalog_bucket": catalog_bucket,
                "catalog_prefix": catalog_prefix,
                "athena_catalog": athena_catalog,
                "local_large_results_folder": local_large_results_folder,
                "inline_result_max_bytes": inline_result_max_bytes,
                "inline_result_max_rows": inline_result_max_rows,
                "aws_profile": aws_profile,
                "aws_access_key_id": aws_access_key_id,
                "aws_secret_access_key": aws_secret_access_key,
                "aws_session_token": aws_session_token,
            }.items()
            if value is not None
        }
        return onboarding_handlers.update_server_configuration(
            skip_aws_validation=skip_aws_validation,
            **updates,
        )

    @mcp.tool(
        name="search_table_catalog",
        description=("Search the indexed table catalog by text and return matching " "entries."),
    )
    def search_table_catalog(
        query: str,
        limit: int = 5,
    ) -> list[dict[str, object]]:
        """Search the indexed table catalog by text.

        Returns the most relevant table entries.
        """
        return catalog_handlers.search_table_catalog(query, limit)

    @mcp.tool(
        name="get_table_skill",
        description=("Load the detailed skill document stored for a specific table."),
    )
    def get_table_skill(database_name: str, table_name: str) -> dict[str, str]:
        """Load the detailed skill document for a cataloged table."""
        return file_handlers.get_table_skill(database_name, table_name)

    @mcp.tool(
        name="create_or_update_table_skill",
        description=("Create or update the detailed skill content and metadata for " "a table."),
    )
    def create_or_update_table_skill(
        database_name: str,
        table_name: str,
        description: str,
        content_markdown: str,
        summary: str,
        business_context: str = "",
        common_use_cases: list[str] | None = None,
        tags: list[str] | None = None,
    ) -> dict[str, object]:
        """Create or replace a table skill.

        Stores the detailed content and summary metadata for the table.
        """
        return file_handlers.create_or_update_table_skill(
            database_name=database_name,
            table_name=table_name,
            description=description,
            content_markdown=content_markdown,
            summary=summary,
            business_context=business_context,
            common_use_cases=common_use_cases,
            tags=tags,
        )

    @mcp.tool(
        name="refresh_catalog_index",
        description=("Reload the local catalog index from persisted catalog storage."),
    )
    def refresh_catalog_index() -> dict[str, int]:
        """Reload the local catalog index from persisted storage."""
        return catalog_handlers.refresh_catalog_index()

    @mcp.tool(
        name="list_catalog_databases",
        description=("List database names currently available in the indexed catalog."),
    )
    def list_catalog_databases() -> list[str]:
        """List database names currently available in the indexed catalog."""
        return catalog_handlers.list_catalog_databases()

    @mcp.tool(
        name="list_catalog_tables",
        description="List indexed catalog tables for a specific database.",
    )
    def list_catalog_tables(database_name: str) -> list[dict[str, object]]:
        """List indexed catalog tables for a specific database."""
        return catalog_handlers.list_catalog_tables(database_name)

    @mcp.tool(
        name="list_aws_cli_profiles",
        description=("List AWS profile names found in local AWS CLI config and credentials files."),
    )
    def list_aws_cli_profiles() -> list[str]:
        """List local AWS CLI profile names."""
        return aws_cli_handlers.list_aws_cli_profiles()

    @mcp.tool(
        name="aws_sso_login",
        description=(
            "Run `aws sso login` for a specific profile to refresh local SSO session tokens."
        ),
    )
    def aws_sso_login(
        profile: str,
        timeout_seconds: int = 180,
    ) -> dict[str, object]:
        """Run AWS CLI SSO login for one profile."""
        return aws_cli_handlers.aws_sso_login(
            profile=profile,
            timeout_seconds=timeout_seconds,
        )

    @mcp.tool(
        name="aws_sts_get_caller_identity",
        description=(
            "Run `aws sts get-caller-identity` using AWS CLI for the provided profile "
            "or current default credentials."
        ),
    )
    def aws_sts_get_caller_identity(
        profile: str | None = None,
        timeout_seconds: int = 60,
    ) -> dict[str, object]:
        """Read caller identity via AWS CLI."""
        return aws_cli_handlers.aws_sts_get_caller_identity(
            profile=profile,
            timeout_seconds=timeout_seconds,
        )

    @mcp.tool(
        name="execute_athena_query",
        description=("Execute SQL in Athena and optionally wait for completion."),
    )
    def execute_athena_query(
        query: str,
        database: str | None = None,
        catalog: str | None = None,
        workgroup: str | None = None,
        wait_for_completion: bool = True,
        max_wait_seconds: int = 300,
    ) -> dict[str, object]:
        """Execute SQL in Athena.

        Optionally waits for completion before returning status and metadata.
        """
        return athena_handlers.execute_athena_query(
            query=query,
            database=database,
            catalog=catalog,
            workgroup=workgroup,
            wait_for_completion=wait_for_completion,
            max_wait_seconds=max_wait_seconds,
        )

    @mcp.tool(
        name="list_athena_databases",
        description=(
            "List databases directly from Athena using SHOW DATABASES. If the user already "
            "knows the database, prefer asking them to type it instead of relying on this call."
        ),
    )
    def list_athena_databases(
        catalog: str | None = None,
    ) -> list[dict[str, object]]:
        """List databases directly from Athena using SHOW DATABASES."""
        return athena_handlers.list_athena_databases(
            catalog=catalog,
        )

    @mcp.tool(
        name="list_athena_tables",
        description="List tables directly from Athena for a database using SHOW TABLES.",
    )
    def list_athena_tables(
        database_name: str,
        catalog: str | None = None,
        name_prefix: str | None = None,
    ) -> list[dict[str, object]]:
        """List tables directly from Athena for a database using SHOW TABLES.

        Optionally filters the list by name prefix.
        """
        return athena_handlers.list_athena_tables(
            database_name=database_name,
            catalog=catalog,
            name_prefix=name_prefix,
        )

    @mcp.tool(
        name="get_athena_table_metadata",
        description=(
            "Fetch table metadata by running SHOW CREATE TABLE in the user-provided "
            "database instead of using GetTableMetadata."
        ),
    )
    def get_athena_table_metadata(
        database_name: str,
        table_name: str,
        catalog: str | None = None,
    ) -> dict[str, object]:
        """Derive columns, partitions and properties from SHOW CREATE TABLE."""
        return athena_handlers.get_athena_table_metadata(
            database_name=database_name,
            table_name=table_name,
            catalog=catalog,
        )

    @mcp.tool(
        name="sync_athena_database_to_catalog",
        description=("Import Athena tables into the indexed catalog and generate " "basic skills."),
    )
    def sync_athena_database_to_catalog(
        database_name: str,
        catalog: str | None = None,
        name_prefix: str | None = None,
        max_tables: int | None = None,
        overwrite_existing: bool = False,
    ) -> dict[str, object]:
        """Import Athena tables into the indexed catalog.

        Also generates basic skills for the imported tables.
        """
        return athena_handlers.sync_athena_database_to_catalog(
            database_name=database_name,
            catalog=catalog,
            name_prefix=name_prefix,
            max_tables=max_tables,
            overwrite_existing=overwrite_existing,
        )

    @mcp.tool(
        name="get_query_execution_status",
        description=("Return the latest status and metadata for a submitted Athena " "query."),
    )
    def get_query_execution_status(
        query_execution_id: str,
    ) -> dict[str, object]:
        """Return the latest status for a submitted Athena query.

        Includes execution metadata when available.
        """
        return athena_handlers.get_query_execution_status(query_execution_id)

    @mcp.tool(
        name="fetch_query_result_preview",
        description=("Fetch an inline preview of the result set for a completed " "Athena query."),
    )
    def fetch_query_result_preview(
        query_execution_id: str,
    ) -> dict[str, object]:
        """Fetch an inline preview for a completed Athena query."""
        return athena_handlers.fetch_query_result_preview(query_execution_id)

    @mcp.tool(
        name="materialize_large_result_locally",
        description=("Download a large Athena query result file to local storage."),
    )
    def materialize_large_result_locally(
        query_execution_id: str,
    ) -> dict[str, object]:
        """Download a large Athena result file locally.

        The file is stored in the configured local results folder.
        """
        return athena_handlers.materialize_large_result_locally(query_execution_id)

    @mcp.tool(
        name="list_local_result_files",
        description="List Athena result files that were materialized locally.",
    )
    def list_local_result_files() -> list[str]:
        """List Athena result files materialized to local storage."""
        return athena_handlers.list_local_result_files()

    return mcp


def main() -> None:
    build_app().run(transport="stdio")
