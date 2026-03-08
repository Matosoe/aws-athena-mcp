from pathlib import Path

import pytest

from athena_knowledge_mcp.core.exceptions import InvalidConfigurationError
from athena_knowledge_mcp.utils.validators import validate_local_path, validate_s3_uri, validate_sql


def test_validate_s3_uri_accepts_valid_uri() -> None:
    validate_s3_uri("s3://bucket/path/file.json")


def test_validate_s3_uri_rejects_invalid_uri() -> None:
    with pytest.raises(InvalidConfigurationError):
        validate_s3_uri("https://bucket/path")


def test_validate_local_path_creates_directory(tmp_path: Path) -> None:
    path = tmp_path / "downloads"

    validate_local_path(path)

    assert path.exists()


def test_validate_sql_rejects_empty_query() -> None:
    with pytest.raises(InvalidConfigurationError):
        validate_sql("   ")
