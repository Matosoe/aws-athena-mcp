from __future__ import annotations

import configparser
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class AwsCliService:
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
