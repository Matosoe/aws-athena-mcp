from __future__ import annotations

import subprocess
from pathlib import Path

from athena_knowledge_mcp.services.aws_cli_service import AwsCliService


class _Completed:
    def __init__(self, returncode: int, stdout: str, stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


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


def test_sso_login_success(monkeypatch) -> None:
    service = AwsCliService(aws_executable="aws")

    def _fake_popen(*args, **kwargs):
        command = args[0]
        assert command == ["aws", "sso", "login", "--profile", "default"]
        assert kwargs["stdin"] is subprocess.DEVNULL
        assert kwargs["stdout"] is subprocess.DEVNULL
        assert kwargs["stderr"] is subprocess.DEVNULL
        assert kwargs["cwd"]
        return object()

    monkeypatch.setattr(subprocess, "Popen", _fake_popen)

    result = service.sso_login("default", timeout_seconds=30)

    assert result["success"] is True
    assert result["status"] == "pending_user_confirmation"
    assert result["browser_login_started"] is True
    assert result["requires_user_confirmation"] is True


def test_sts_get_caller_identity_parses_json(monkeypatch) -> None:
    service = AwsCliService(aws_executable="aws")

    def _fake_run(*args, **kwargs):
        command = args[0]
        _ = kwargs
        assert command == [
            "aws",
            "sts",
            "get-caller-identity",
            "--output",
            "json",
            "--profile",
            "default",
        ]
        return _Completed(0, '{"Account":"123456789012"}', "")

    monkeypatch.setattr(subprocess, "run", _fake_run)

    result = service.sts_get_caller_identity(profile="default")

    assert result["success"] is True
    assert result["identity"] == {"Account": "123456789012"}


def test_run_command_handles_missing_aws(monkeypatch) -> None:
    service = AwsCliService(aws_executable="aws")

    def _fake_popen(*_args, **_kwargs):
        raise FileNotFoundError()

    monkeypatch.setattr(subprocess, "Popen", _fake_popen)

    result = service.sso_login("default")

    assert result["success"] is False
    assert result["stderr"] == "AWS CLI not found in PATH"


def test_sso_login_uses_detached_session_outside_windows(monkeypatch) -> None:
    service = AwsCliService(aws_executable="aws")

    def _fake_popen(*args, **kwargs):
        command = args[0]
        assert command == ["aws", "sso", "login", "--profile", "default"]
        assert kwargs["start_new_session"] is True
        return object()

    monkeypatch.setattr(subprocess, "Popen", _fake_popen)
    monkeypatch.setattr(
        "athena_knowledge_mcp.services.aws_cli_service.os.name",
        "posix",
    )

    result = service.sso_login("default")

    assert result["success"] is True
    assert result["command"] == "aws sso login --profile default"


def test_sso_login_rejects_empty_profile() -> None:
    service = AwsCliService()

    try:
        service.sso_login("   ")
        assert False, "expected ValueError"
    except ValueError as exc:
        assert str(exc) == "profile must not be empty"
