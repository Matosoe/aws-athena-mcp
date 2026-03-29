"""
Defaults de infraestrutura corporativa.

Este e o UNICO arquivo que o time de plataforma precisa editar ao
publicar uma nova versao do EXE para um novo ambiente (dev/staging/prod).
Todos os outros campos de infraestrutura sao derivados daqui em runtime,
a menos que o usuario tenha definido overrides em state/runtime_settings.json
(arquivo local nao rastreado pelo git).
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
COMPANY_DEFAULT_AUTHENTICATION_TYPE: AwsAuthenticationType = AwsAuthenticationType.PROFILE

# Valor sentinela: indica que os defaults ainda nao foram personalizados
_PLACEHOLDER_BUCKET = "minha-empresa-athena-results"


def has_placeholder_infrastructure() -> bool:
    """Retorna True se os defaults corporativos ainda sao os valores de exemplo.

    Quando True, o usuario deve fornecer overrides de infraestrutura via
    initialize_server_configuration para que o servidor funcione corretamente.
    """
    return (
        COMPANY_QUERY_RESULTS_S3_BUCKET == _PLACEHOLDER_BUCKET
        or COMPANY_CATALOG_S3_BUCKET == _PLACEHOLDER_BUCKET
    )


def build_resolved_config(
    server_config: ServerConfiguration | None,
) -> ResolvedConfig | None:
    """Combina os defaults corporativos com as preferencias do usuario.

    Campos definidos em server_config sobrescrevem os defaults corporativos.
    Retorna None se nao ha configuracao de usuario salva ainda.
    """
    if server_config is None:
        return None
    return ResolvedConfig(
        aws_region=server_config.aws_region or COMPANY_AWS_REGION,
        authentication_type=(
            server_config.authentication_type or COMPANY_DEFAULT_AUTHENTICATION_TYPE
        ),
        athena_workgroup=server_config.athena_workgroup or COMPANY_ATHENA_WORKGROUP,
        athena_catalog=server_config.athena_catalog or COMPANY_ATHENA_CATALOG,
        query_results_s3_bucket=(
            server_config.query_results_s3_bucket or COMPANY_QUERY_RESULTS_S3_BUCKET
        ),
        query_results_s3_prefix=(
            server_config.query_results_s3_prefix or COMPANY_QUERY_RESULTS_S3_PREFIX
        ),
        catalog_bucket=server_config.catalog_bucket or COMPANY_CATALOG_S3_BUCKET,
        catalog_prefix=server_config.catalog_prefix or COMPANY_CATALOG_S3_PREFIX,
        aws_profile=server_config.aws_profile,
        athena_databases=server_config.athena_databases,
        default_database=server_config.default_database,
        local_large_results_folder=server_config.local_large_results_folder,
        inline_result_max_bytes=server_config.inline_result_max_bytes,
        inline_result_max_rows=server_config.inline_result_max_rows,
    )
