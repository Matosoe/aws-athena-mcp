from athena_knowledge_mcp.utils.secret_scanner import format_findings, scan_text


def test_scan_text_detects_aws_access_key_id() -> None:
    fake_access_key_id = "AKIA" + ("A" * 16)
    findings = scan_text(
        "config.json",
        f'{{"aws_access_key_id": "{fake_access_key_id}"}} # secret-scanner: allow',
    )

    assert findings == []


def test_scan_text_detects_aws_access_key_id_without_allowlist_marker() -> None:
    fake_access_key_id = "AKIA" + ("A" * 16)
    findings = scan_text("config.json", f'{{"aws_access_key_id": "{fake_access_key_id}"}}')

    assert len(findings) == 1
    assert findings[0].rule_name == "aws-access-key-id"


def test_scan_text_detects_secret_access_key_assignment() -> None:
    fake_secret = "abcd" * 10
    findings = scan_text(
        "config.json",
        f'aws_secret_access_key = "{fake_secret}"',
    )

    assert len(findings) == 1
    assert findings[0].rule_name == "aws-secret-access-key"


def test_scan_text_detects_sensitive_extension_without_content_match() -> None:
    findings = scan_text("id_rsa.pem", "public information only")

    assert len(findings) == 1
    assert findings[0].rule_name == "sensitive-file-extension"


def test_format_findings_includes_location_and_rule() -> None:
    fake_secret = "abcd" * 10
    findings = scan_text(
        "credentials.env",
        f'AWS_SECRET_ACCESS_KEY="{fake_secret}"',
    )

    output = format_findings(findings)

    assert "credentials.env:1" in output
    assert "aws-secret-access-key" in output