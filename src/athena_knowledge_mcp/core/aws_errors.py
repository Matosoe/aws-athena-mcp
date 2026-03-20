from __future__ import annotations

from botocore.exceptions import (  # type: ignore[import-untyped]
    BotoCoreError,
    ClientError,
    NoCredentialsError,
    ProfileNotFound,
)

from athena_knowledge_mcp.core.exceptions import AwsAccessDeniedError

_ACCESS_DENIED_CODES = {
    "AccessDenied",
    "AccessDeniedException",
    "AccessDeniedError",
    "Unauthorized",
    "UnauthorizedException",
    "Forbidden",
    "ForbiddenException",
    "403",
}

_ACCESS_DENIED_TOKENS = (
    "access denied",
    "accessdenied",
    "not authorized",
    "unauthorized",
    "forbidden",
)


def raise_if_aws_access_denied(exc: Exception, service_name: str) -> None:
    if _is_aws_access_denied(exc) or _is_aws_login_required(exc):
        raise AwsAccessDeniedError(service_name) from exc


def _is_aws_access_denied(exc: Exception) -> bool:
    if isinstance(exc, ClientError):
        code = _extract_error_code(exc)
        if code in _ACCESS_DENIED_CODES:
            return True

    message = _extract_error_message(exc).lower()
    return any(token in message for token in _ACCESS_DENIED_TOKENS)


def _is_aws_login_required(exc: Exception) -> bool:
    return isinstance(
        exc,
        (
            BotoCoreError,
            NoCredentialsError,
            ProfileNotFound,
        ),
    )


def _extract_error_code(exc: ClientError) -> str | None:
    error = exc.response.get("Error")
    if not isinstance(error, dict):
        return None
    code = error.get("Code")
    return code if isinstance(code, str) else None


def _extract_error_message(exc: Exception) -> str:
    response = getattr(exc, "response", None)
    if isinstance(response, dict):
        error = response.get("Error")
        if isinstance(error, dict):
            message = error.get("Message")
            if isinstance(message, str) and message.strip():
                return message
    return str(exc)