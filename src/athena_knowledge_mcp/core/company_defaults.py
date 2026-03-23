"""
Defaults de infraestrutura corporativa.

Este e o UNICO arquivo que o time de plataforma precisa editar ao
publicar uma nova versao do EXE para um novo ambiente (dev/staging/prod).
Todos os outros campos de infraestrutura sao derivados daqui em runtime.
"""
from __future__ import annotations

from athena_knowledge_mcp.core.models import (
    AwsAuthenticationType,
    ResolvedConfig,
    ServerConfiguration,
)

# ---------------------------------------------------------------------------
# Constantes de infraestrutura — edite aqui ao adaptar para seu ambiente
# ---------------------------------------------------------------------------

COMPANY_AWS_REGION: str = "us-east-1"
COMPANY_ATHENA_WORKGROUP: str = "primary"
COMPANY_ATHENA_CATALOG: str = "AwsDataCatalog"
COMPANY_QUERY_RESULTS_S3_BUCKET: str = "minha-empresa-athena-results"
COMPANY_QUERY_RESULTS_S3_PREFIX: str = "mcp/athena/results/"
COMPANY_CATALOG_S3_BUCKET: str = "minha-empresa-athena-results"
COMPANY_CATALOG_S3_PREFIX: str = "mcp/athena/catalog/"
COMPANY_DEFAULT_AUTHENTICATION_TYPE: AwsAuthenticationType = (
    AwsAuthenticationType.PROFILE
)


def build_resolved_config(
    server_config: ServerConfiguration | None,
) -> ResolvedConfig | None:
    """Combina os defaults corporativos com as preferencias do usuario.

    Retorna None se nao ha configuracao de usuario salva ainda.
    """
    if server_config is None:
        return None
    return ResolvedConfig(
        aws_region=COMPANY_AWS_REGION,
        authentication_type=COMPANY_DEFAULT_AUTHENTICATION_TYPE,
        athena_workgroup=COMPANY_ATHENA_WORKGROUP,
        athena_catalog=COMPANY_ATHENA_CATALOG,
        query_results_s3_bucket=COMPANY_QUERY_RESULTS_S3_BUCKET,
        query_results_s3_prefix=COMPANY_QUERY_RESULTS_S3_PREFIX,
        catalog_bucket=COMPANY_CATALOG_S3_BUCKET,
        catalog_prefix=COMPANY_CATALOG_S3_PREFIX,
        aws_profile=server_config.aws_profile,
        athena_databases=server_config.athena_databases,
        default_database=server_config.default_database,
        local_large_results_folder=server_config.local_large_results_folder,
        inline_result_max_bytes=server_config.inline_result_max_bytes,
        inline_result_max_rows=server_config.inline_result_max_rows,
    )
