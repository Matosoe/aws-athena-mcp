from athena_knowledge_mcp.core.models import TableSkill
from athena_knowledge_mcp.repositories.s3_catalog_repository import S3CatalogRepository
from athena_knowledge_mcp.repositories.s3_skill_catalog_repository import (
    S3SkillCatalogRepository,
)
from athena_knowledge_mcp.repositories.s3_skill_repository import S3SkillRepository
from athena_knowledge_mcp.services.request_routing_service import RequestRoutingService
from athena_knowledge_mcp.services.s3_catalog_service import S3CatalogService
from athena_knowledge_mcp.services.skill_catalog_service import SkillCatalogService
from athena_knowledge_mcp.services.table_skill_service import TableSkillService


def _build_services(tmp_path):
    table_catalog = S3CatalogService(
        S3CatalogRepository(bucket="local", prefix="", local_root=tmp_path / "catalog")
    )
    skill_catalog = SkillCatalogService(
        S3SkillCatalogRepository(
            bucket="local",
            prefix="",
            local_root=tmp_path / "skill_catalog",
        )
    )
    table_skill_service = TableSkillService(
        S3SkillRepository(bucket="local", prefix="", local_root=tmp_path / "skills"),
        table_catalog,
        skill_catalog,
    )
    return table_catalog, skill_catalog, table_skill_service


def test_route_prefers_table_catalog_with_explicit_db_table(tmp_path) -> None:
    table_catalog, skill_catalog, table_skill_service = _build_services(tmp_path)
    table_skill_service.create_or_update_table_skill(
        TableSkill(
            database_name="analytics",
            table_name="orders",
            description="Pedidos por status",
            content_markdown="# Orders",
            summary="Pedidos ecommerce",
            tags=["orders"],
        )
    )
    routing_service = RequestRoutingService(table_catalog, skill_catalog)

    routed = routing_service.route_request(
        user_request="gerar query para analytics.orders por status",
    )

    assert routed["route"] == "table_catalog"
    assert routed["should_scan_athena"] is False
    assert len(routed["table_matches"]) == 1


def test_route_prefers_skill_catalog_without_db_table_context(tmp_path) -> None:
    table_catalog, skill_catalog, table_skill_service = _build_services(tmp_path)
    table_skill_service.create_or_update_table_skill(
        TableSkill(
            database_name="analytics",
            table_name="orders",
            description="Skill de pedidos por status",
            content_markdown="# Orders",
            summary="Como montar KPI de pedidos",
            tags=["kpi", "pedidos"],
        )
    )
    routing_service = RequestRoutingService(table_catalog, skill_catalog)

    routed = routing_service.route_request(
        user_request="quero medir kpi de pedidos por status",
    )

    assert routed["route"] == "skill_catalog"
    assert routed["should_scan_athena"] is False
    assert len(routed["skill_matches"]) == 1


def test_route_allows_athena_scan_when_indexes_have_no_match(tmp_path) -> None:
    table_catalog, skill_catalog, _ = _build_services(tmp_path)
    routing_service = RequestRoutingService(table_catalog, skill_catalog)

    routed = routing_service.route_request(
        user_request="preciso de algo totalmente novo sem skill",
    )

    assert routed["route"] == "skill_catalog"
    assert routed["should_scan_athena"] is True
