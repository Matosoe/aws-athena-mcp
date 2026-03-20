from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

from athena_knowledge_mcp.core.exceptions import InvalidConfigurationError
from athena_knowledge_mcp.core.models import (
    AwsAuthenticationType,
    AwsSecretMaterial,
    ServerConfiguration,
)
from athena_knowledge_mcp.utils.paths import resolve_runtime_path


def validate_configuration(configuration: ServerConfiguration, secrets: AwsSecretMaterial) -> None:
    if (
        configuration.authentication_type == AwsAuthenticationType.PROFILE
        and not configuration.aws_profile
    ):
        raise InvalidConfigurationError(
            "aws_profile e obrigatorio quando authentication_type=profile"
        )
    if configuration.authentication_type in {
        AwsAuthenticationType.ACCESS_KEY,
        AwsAuthenticationType.SESSION_TOKEN,
    }:
        if not secrets.aws_access_key_id or not secrets.aws_secret_access_key:
            raise InvalidConfigurationError(
                "Credenciais AWS incompletas para autenticacao por chave"
            )
    if (
        configuration.authentication_type == AwsAuthenticationType.SESSION_TOKEN
        and not secrets.aws_session_token
    ):
        raise InvalidConfigurationError(
            "aws_session_token e obrigatorio para authentication_type=session_token"
        )

    validate_s3_uri(
        f"s3://{configuration.query_results_s3_bucket}/{configuration.query_results_s3_prefix}"
    )
    validate_s3_uri(f"s3://{configuration.catalog_bucket}/{configuration.catalog_prefix}")
    validate_local_path(configuration.local_large_results_folder)


def validate_s3_uri(value: str) -> None:
    parsed = urlparse(value)
    if parsed.scheme != "s3" or not parsed.netloc:
        raise InvalidConfigurationError(f"URI S3 invalida: {value}")


def validate_local_path(value: str | Path) -> None:
    path = resolve_runtime_path(value)
    path.mkdir(parents=True, exist_ok=True)
    if not path.is_dir():
        raise InvalidConfigurationError(f"Caminho local invalido: {path}")


def validate_sql(query: str) -> None:
    if not query.strip():
        raise InvalidConfigurationError("A query SQL nao pode ser vazia")
