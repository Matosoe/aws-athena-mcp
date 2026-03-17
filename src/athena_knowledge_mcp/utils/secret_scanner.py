from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


SENSITIVE_EXTENSIONS = {".key", ".p12", ".pem", ".pfx"}
ALLOWLIST_MARKER = "secret-scanner: allow"


@dataclass(frozen=True, slots=True)
class SecretFinding:
    file_path: str
    line_number: int | None
    rule_name: str
    snippet: str


LINE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("aws-access-key-id", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    (
        "aws-secret-access-key",
        re.compile(
            r"(?i)(?:aws_secret_access_key|AWS_SECRET_ACCESS_KEY)\s*[=:]\s*[\"']?[A-Za-z0-9/+=]{40}[\"']?"
        ),
    ),
    (
        "aws-session-token",
        re.compile(
            r"(?i)(?:aws_session_token|AWS_SESSION_TOKEN)\s*[=:]\s*[\"']?[A-Za-z0-9/+=]{20,}[\"']?"
        ),
    ),
    (
        "private-key-material",
        re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----"),
    ),
)


def scan_text(file_path: str, content: str) -> list[SecretFinding]:
    findings: list[SecretFinding] = []

    if Path(file_path).suffix.lower() in SENSITIVE_EXTENSIONS:
        findings.append(
            SecretFinding(
                file_path=file_path,
                line_number=None,
                rule_name="sensitive-file-extension",
                snippet="arquivo com extensao sensivel detectado no commit",
            )
        )

    for line_number, line in enumerate(content.splitlines(), start=1):
        if ALLOWLIST_MARKER in line:
            continue
        for rule_name, pattern in LINE_PATTERNS:
            if pattern.search(line):
                findings.append(
                    SecretFinding(
                        file_path=file_path,
                        line_number=line_number,
                        rule_name=rule_name,
                        snippet=line.strip(),
                    )
                )

    return findings


def get_staged_files(repo_root: Path) -> list[str]:
    result = subprocess.run(
        [
            "git",
            "-C",
            str(repo_root),
            "diff",
            "--cached",
            "--name-only",
            "--diff-filter=ACMR",
            "-z",
        ],
        capture_output=True,
        text=False,
        check=True,
    )
    entries = [entry for entry in result.stdout.decode("utf-8", errors="ignore").split("\0") if entry]
    return entries


def get_staged_file_content(repo_root: Path, file_path: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo_root), "show", f":{file_path}"],
        capture_output=True,
        text=False,
        check=True,
    )
    return result.stdout.decode("utf-8", errors="ignore")


def scan_staged_files(repo_root: Path) -> list[SecretFinding]:
    findings: list[SecretFinding] = []
    for file_path in get_staged_files(repo_root):
        content = get_staged_file_content(repo_root, file_path)
        findings.extend(scan_text(file_path=file_path, content=content))
    return findings


def format_findings(findings: list[SecretFinding]) -> str:
    lines = ["Commit bloqueado: possivel segredo detectado em arquivos staged."]
    for finding in findings:
        location = finding.file_path
        if finding.line_number is not None:
            location = f"{location}:{finding.line_number}"
        lines.append(f"- {location} [{finding.rule_name}] {finding.snippet}")
    lines.append("Revise o conteudo, remova o segredo e tente novamente.")
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Varre segredos comuns antes de commit.")
    parser.add_argument(
        "--staged",
        action="store_true",
        help="Varre o conteudo staged do repositorio atual.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.staged:
        print("Use --staged para varrer os arquivos staged do repositorio atual.", file=sys.stderr)
        return 2

    repo_root = Path.cwd()
    findings = scan_staged_files(repo_root)
    if findings:
        print(format_findings(findings), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())