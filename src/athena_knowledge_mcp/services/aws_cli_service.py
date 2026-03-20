from __future__ import annotations

import configparser
import json
import os
import re
import shutil
import subprocess
import time
import webbrowser
from dataclasses import dataclass
from pathlib import Path

_URL_PATTERN = re.compile(r"https://[^\s]+")
_DEVICE_CODE_PATTERN = re.compile(r"^[A-Z0-9]{4}(?:-[A-Z0-9]{4})+$")


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
        """Run `aws sso login` for one profile and open the authorization URL."""
        self._validate_profile(profile)
        return self._run_sso_login_command(
            profile=profile,
            timeout_seconds=timeout_seconds,
        )

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

    def _run_sso_login_command(
        self,
        profile: str,
        timeout_seconds: int,
    ) -> dict[str, object]:
        executable = self.aws_executable or shutil.which("aws") or "aws"
        command = [executable, "sso", "login", "--no-browser", "--profile", profile]
        env = os.environ.copy()
        env.setdefault("AWS_PAGER", "")

        try:
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=env,
            )
        except FileNotFoundError:
            return {
                "success": False,
                "exit_code": None,
                "stdout": "",
                "stderr": "AWS CLI not found in PATH",
                "command": " ".join(command),
                "browser_opened": False,
                "verification_url": None,
                "user_code": None,
                "profile": profile,
            }

        output_lines: list[str] = []
        verification_url: str | None = None
        user_code: str | None = None
        browser_opened = False
        deadline = time.monotonic() + timeout_seconds
        awaiting_code = False

        assert process.stdout is not None

        while True:
            if time.monotonic() > deadline:
                process.kill()
                remaining_output = process.communicate()[0]
                if remaining_output:
                    output_lines.append(remaining_output)
                return {
                    "success": False,
                    "exit_code": None,
                    "stdout": "".join(output_lines),
                    "stderr": f"Command timed out after {timeout_seconds} seconds",
                    "command": " ".join(command),
                    "browser_opened": browser_opened,
                    "verification_url": verification_url,
                    "user_code": user_code,
                    "profile": profile,
                }

            line = process.stdout.readline()
            if line:
                output_lines.append(line)
                stripped_line = line.strip()

                if verification_url is None:
                    url_match = _URL_PATTERN.search(stripped_line)
                    if url_match:
                        verification_url = url_match.group(0).rstrip(".,)")

                lower_line = stripped_line.lower()
                if awaiting_code and user_code is None and _DEVICE_CODE_PATTERN.fullmatch(stripped_line):
                    user_code = stripped_line
                    awaiting_code = False
                elif "enter the code" in lower_line:
                    awaiting_code = True

                if verification_url and not browser_opened:
                    browser_opened = webbrowser.open(verification_url)
            elif process.poll() is not None:
                break
            else:
                time.sleep(0.1)

        remaining_output = process.stdout.read()
        if remaining_output:
            output_lines.append(remaining_output)
            if verification_url is None:
                url_match = _URL_PATTERN.search(remaining_output)
                if url_match:
                    verification_url = url_match.group(0).rstrip(".,)")
            if user_code is None:
                for candidate_line in remaining_output.splitlines():
                    stripped_line = candidate_line.strip()
                    if _DEVICE_CODE_PATTERN.fullmatch(stripped_line):
                        user_code = stripped_line
                        break
            if verification_url and not browser_opened:
                browser_opened = webbrowser.open(verification_url)

        return {
            "success": process.returncode == 0,
            "exit_code": process.returncode,
            "stdout": "".join(output_lines),
            "stderr": "",
            "command": " ".join(command),
            "browser_opened": browser_opened,
            "verification_url": verification_url,
            "user_code": user_code,
            "profile": profile,
        }

    def _validate_profile(self, profile: str) -> None:
        if not profile.strip():
            raise ValueError("profile must not be empty")
