from __future__ import annotations

from pathlib import Path

from athena_knowledge_mcp.core.exceptions import InvalidConfigurationError
from athena_knowledge_mcp.core.models import (
    AwsAuthenticationType,
    AwsSecretMaterial,
    ResolvedConfig,
)
from athena_knowledge_mcp.utils.paths import resolve_runtime_path


def validate_configuration(
    resolved: ResolvedConfig,
    secrets: AwsSecretMaterial,
) -> None:
    if (
        resolved.authentication_type == AwsAuthenticationType.PROFILE
        and not resolved.aws_profile
    ):
        raise InvalidConfigurationError(
            "aws_profile e obrigatorio quando authentication_type=profile"
        )
    if resolved.authentication_type in {
        AwsAuthenticationType.ACCESS_KEY,
        AwsAuthenticationType.SESSION_TOKEN,
    }:
        if not secrets.aws_access_key_id or not secrets.aws_secret_access_key:
            raise InvalidConfigurationError(
                "Credenciais AWS incompletas para autenticacao por chave"
            )
    if (
        resolved.authentication_type
        == AwsAuthenticationType.SESSION_TOKEN
        and not secrets.aws_session_token
    ):
        raise InvalidConfigurationError(
            "aws_session_token e obrigatorio para "
            "authentication_type=session_token"
        )
    validate_local_path(resolved.local_large_results_folder)


def validate_s3_uri(value: str) -> None:
    from urllib.parse import urlparse
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
