from __future__ import annotations

from pathlib import Path

from athena_knowledge_mcp.services.aws_cli_service import AwsCliService


def test_list_profiles_reads_credentials_and_config(
    tmp_path: Path,
    monkeypatch,
) -> None:
    aws_dir = tmp_path / ".aws"
    aws_dir.mkdir(parents=True)
    (aws_dir / "credentials").write_text(
        "[default]\naws_access_key_id=x\n\n[dev]\naws_access_key_id=y\n",
        encoding="utf-8",
    )
    (aws_dir / "config").write_text(
        ("[default]\nregion=us-east-1\n\n" "[profile analytics]\nregion=us-east-1\n"),
        encoding="utf-8",
    )

    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    service = AwsCliService()

    assert service.list_profiles() == ["analytics", "default", "dev"]
