from __future__ import annotations

import configparser
import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class AwsCliService:
    aws_executable: str | None = None

    def list_profiles(self) -> list[str]:
        """List profile names discovered in AWS CLI config files."""
        aws_dir = Path.home() / ".aws"
        credentials_file = aws_dir / "credentials"
        config_file = aws_dir / "config"

        profiles: set[str] = set()

        if credentials_file.exists():
            parser = configparser.ConfigParser()
            parser.read(credentials_file, encoding="utf-8")
            profiles.update(section.strip() for section in parser.sections() if section.strip())

        if config_file.exists():
            parser = configparser.ConfigParser()
            parser.read(config_file, encoding="utf-8")
            for section in parser.sections():
                normalized = section.strip()
                if normalized.startswith("profile "):
                    normalized = normalized.removeprefix("profile ").strip()
                if normalized:
                    profiles.add(normalized)

        return sorted(profiles)

    def sso_login(
        self,
        profile: str,
        timeout_seconds: int = 180,
    ) -> dict[str, object]:
        """Start `aws sso login` for one profile without blocking."""
        self._validate_profile(profile)
        del timeout_seconds

        executable = self.aws_executable or shutil.which("aws") or "aws"
        command = [executable, "sso", "login", "--profile", profile]

        popen_kwargs: dict[str, object] = {
            "stdin": subprocess.DEVNULL,
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
            "cwd": str(Path.home()),
        }

        if os.name == "nt":
            creationflags = 0
            creationflags |= getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            creationflags |= getattr(subprocess, "DETACHED_PROCESS", 0)
            popen_kwargs["creationflags"] = creationflags
        else:
            popen_kwargs["start_new_session"] = True

        try:
            subprocess.Popen(command, **popen_kwargs)
        except FileNotFoundError:
            return {
                "success": False,
                "exit_code": None,
                "stdout": "",
                "stderr": "AWS CLI not found in PATH",
                "command": " ".join(command),
            }

        return {
            "success": True,
            "exit_code": None,
            "stdout": "",
            "stderr": "",
            "command": " ".join(command),
            "status": "pending_user_confirmation",
            "browser_login_started": True,
            "requires_user_confirmation": True,
            "message": (
                "AWS SSO login was started for the selected profile. "
                "A browser window should open so the user can approve login."
            ),
            "next_step": (
                "Ask the user to confirm after approving the login in the "
                "browser. Only continue with authenticated AWS tools after "
                "that confirmation."
            ),
        }

    def sts_get_caller_identity(
        self,
        profile: str | None = None,
        timeout_seconds: int = 60,
    ) -> dict[str, object]:
        """Run `aws sts get-caller-identity` and parse JSON output."""
        args = ["sts", "get-caller-identity", "--output", "json"]
        if profile:
            self._validate_profile(profile)
            args.extend(["--profile", profile])

        result = self._run_command(args, timeout_seconds=timeout_seconds)
        if result["success"] and isinstance(result.get("stdout"), str):
            stdout = result["stdout"]
            try:
                result["identity"] = json.loads(stdout) if stdout else {}
            except json.JSONDecodeError:
                result["identity"] = None
        return result

    def _run_command(
        self,
        args: list[str],
        timeout_seconds: int,
    ) -> dict[str, object]:
        executable = self.aws_executable or shutil.which("aws") or "aws"
        command = [executable, *args]
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
            )
        except FileNotFoundError:
            return {
                "success": False,
                "exit_code": None,
                "stdout": "",
                "stderr": "AWS CLI not found in PATH",
                "command": " ".join(command),
            }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "exit_code": None,
                "stdout": "",
                "stderr": f"Command timed out after {timeout_seconds} seconds",
                "command": " ".join(command),
            }

        return {
            "success": completed.returncode == 0,
            "exit_code": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
            "command": " ".join(command),
        }

    def _validate_profile(self, profile: str) -> None:
        if not profile.strip():
            raise ValueError("profile must not be empty")
