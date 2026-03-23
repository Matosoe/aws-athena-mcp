from pathlib import Path

from athena_knowledge_mcp.core.models import ServerConfiguration
from athena_knowledge_mcp.core.settings_store import SettingsStore


def test_save_and_load_settings(tmp_path: Path) -> None:
    file_path = tmp_path / "runtime_settings.json"
    store = SettingsStore(file_path)
    configuration = ServerConfiguration(
        aws_profile="test-profile",
        athena_databases=["default", "analytics"],
    )

    store.save(configuration)

    loaded = store.load()

    assert loaded is not None
    assert loaded.aws_profile == "test-profile"
    assert loaded.athena_databases == ["default", "analytics"]
