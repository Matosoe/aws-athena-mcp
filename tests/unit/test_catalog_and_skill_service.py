from athena_knowledge_mcp.core.models import TableSkill
from athena_knowledge_mcp.repositories.s3_catalog_repository import S3CatalogRepository
from athena_knowledge_mcp.repositories.s3_skill_catalog_repository import (
    S3SkillCatalogRepository,
)
from athena_knowledge_mcp.repositories.s3_skill_repository import S3SkillRepository
from athena_knowledge_mcp.services.s3_catalog_service import S3CatalogService
from athena_knowledge_mcp.services.skill_catalog_service import SkillCatalogService
from athena_knowledge_mcp.services.table_skill_service import TableSkillService


class _MissingCatalogClient:
    def get_object(self, **_: object) -> object:
        error = Exception("missing")
        error.response = {"Error": {"Code": "NoSuchKey"}}
        raise error


def test_catalog_search_and_skill_upsert(tmp_path) -> None:
    catalog_service = S3CatalogService(
        S3CatalogRepository(bucket="local", prefix="", local_root=tmp_path / "catalog")
    )
    skill_catalog_service = SkillCatalogService(
        S3SkillCatalogRepository(
            bucket="local",
            prefix="",
            local_root=tmp_path / "skill_catalog",
        )
    )
    table_skill_service = TableSkillService(
        S3SkillRepository(bucket="local", prefix="", local_root=tmp_path / "skills"),
        catalog_service,
        skill_catalog_service,
    )

    entry = table_skill_service.create_or_update_table_skill(
        TableSkill(
            database_name="analytics",
            table_name="orders",
            description="Pedidos do ecommerce",
            content_markdown="# Orders\n\nTabela de pedidos.",
            summary="Pedidos e status do ecommerce",
            business_context="Suporte a operacao comercial",
            common_use_cases=["pedidos por status"],
            tags=["orders", "sales"],
        )
    )

    search_results = catalog_service.search("status ecommerce", limit=5)
    skill_search_results = skill_catalog_service.search("pedidos ecommerce", limit=5)
    skill = table_skill_service.get_table_skill("analytics", "orders")

    assert entry.table_name == "orders"
    assert len(search_results) == 1
    assert len(skill_search_results) == 1
    assert skill_search_results[0].skill_id == "analytics.orders"
    assert skill["content_markdown"].startswith("# Orders")


def test_catalog_load_entries_returns_empty_when_s3_index_is_missing() -> None:
    repository = S3CatalogRepository(
        bucket="catalog-bucket",
        prefix="catalog-prefix",
        s3_client=_MissingCatalogClient(),
    )

    assert repository.load_entries() == []


def test_catalog_list_tables_filters_by_database(tmp_path) -> None:
    catalog_service = S3CatalogService(
        S3CatalogRepository(bucket="local", prefix="", local_root=tmp_path / "catalog")
    )
    skill_catalog_service = SkillCatalogService(
        S3SkillCatalogRepository(
            bucket="local",
            prefix="",
            local_root=tmp_path / "skill_catalog",
        )
    )
    table_skill_service = TableSkillService(
        S3SkillRepository(bucket="local", prefix="", local_root=tmp_path / "skills"),
        catalog_service,
        skill_catalog_service,
    )
    table_skill_service.create_or_update_table_skill(
        TableSkill(
            database_name="analytics",
            table_name="orders",
            description="Pedidos",
            content_markdown="# Orders",
            summary="Pedidos",
        )
    )
    table_skill_service.create_or_update_table_skill(
        TableSkill(
            database_name="finance",
            table_name="invoices",
            description="Faturas",
            content_markdown="# Invoices",
            summary="Faturas",
        )
    )

    tables = catalog_service.list_tables("analytics")
    skills = skill_catalog_service.list_skills()

    assert [table.table_name for table in tables] == ["orders"]
    assert [skill.skill_id for skill in skills] == [
        "analytics.orders",
        "finance.invoices",
    ]