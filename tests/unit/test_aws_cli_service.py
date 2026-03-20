from __future__ import annotations

import io
import subprocess
from pathlib import Path

from athena_knowledge_mcp.services.aws_cli_service import AwsCliService


class _Completed:
    def __init__(self, returncode: int, stdout: str, stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class _FakePopen:
    def __init__(self, command: list[str], output: str, returncode: int = 0) -> None:
        self.command = command
        self.stdout = io.StringIO(output)
        self.returncode = returncode
        self._killed = False

    def poll(self) -> int | None:
        current_position = self.stdout.tell()
        end_position = len(self.stdout.getvalue())
        if self._killed:
            return -9
        if current_position < end_position:
            return None
        return self.returncode

    def communicate(self) -> tuple[str, None]:
        return (self.stdout.read(), None)

    def kill(self) -> None:
        self._killed = True


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
    opened_urls: list[str] = []

    def _fake_popen(*args, **kwargs):
        command = args[0]
        assert command == ["aws", "sso", "login", "--no-browser", "--profile", "default"]
        assert kwargs["env"]["AWS_PAGER"] == ""
        return _FakePopen(
            command,
            (
                "Using a browser to open the SSO authorization page.\n"
                "If the browser does not open, use the following URL:\n"
                "https://device.sso.us-east-1.amazonaws.com/\n"
                "Then enter the code:\n"
                "ABCD-EFGH\n"
                "Successfully logged into Start URL: https://example.awsapps.com/start\n"
            ),
            returncode=0,
        )

    def _fake_open(url: str) -> bool:
        opened_urls.append(url)
        return True

    monkeypatch.setattr(subprocess, "Popen", _fake_popen)
    monkeypatch.setattr("webbrowser.open", _fake_open)

    result = service.sso_login("default", timeout_seconds=30)

    assert result["success"] is True
    assert result["exit_code"] == 0
    assert result["browser_opened"] is True
    assert result["verification_url"] == "https://device.sso.us-east-1.amazonaws.com/"
    assert result["user_code"] == "ABCD-EFGH"
    assert opened_urls == ["https://device.sso.us-east-1.amazonaws.com/"]


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


def test_sso_login_returns_browser_flag_when_open_fails(monkeypatch) -> None:
    service = AwsCliService(aws_executable="aws")

    def _fake_popen(*args, **_kwargs):
        command = args[0]
        return _FakePopen(
            command,
            "https://device.sso.us-east-1.amazonaws.com/\nWXYZ-1234\n",
            returncode=0,
        )

    monkeypatch.setattr(subprocess, "Popen", _fake_popen)
    monkeypatch.setattr("webbrowser.open", lambda _url: False)

    result = service.sso_login("default")

    assert result["success"] is True
    assert result["browser_opened"] is False
    assert result["verification_url"] == "https://device.sso.us-east-1.amazonaws.com/"


def test_sso_login_rejects_empty_profile() -> None:
    service = AwsCliService()

    try:
        service.sso_login("   ")
        assert False, "expected ValueError"
    except ValueError as exc:
        assert str(exc) == "profile must not be empty"
