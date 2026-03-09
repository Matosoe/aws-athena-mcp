from __future__ import annotations

from dataclasses import dataclass

from athena_knowledge_mcp.core.models import RuntimePaths, ServerConfiguration
from athena_knowledge_mcp.core.secrets_store import SecretsStore
from athena_knowledge_mcp.core.settings_store import SettingsStore
from athena_knowledge_mcp.utils.paths import resolve_runtime_home


@dataclass(slots=True)
class AppConfig:
    runtime_paths: RuntimePaths
    settings_store: SettingsStore
    secrets_store: SecretsStore

    @classmethod
    def default(cls) -> AppConfig:
        runtime_home = resolve_runtime_home()
        runtime_paths = RuntimePaths(
            state_dir=runtime_home / "state",
            downloads_dir=runtime_home / "downloads",
            settings_file=runtime_home / "state" / "runtime_settings.json",
            secrets_file=runtime_home / "state" / "secrets.json",
        )
        return cls(
            runtime_paths=runtime_paths,
            settings_store=SettingsStore(runtime_paths.settings_file),
            secrets_store=SecretsStore(runtime_paths.secrets_file),
        )

    def load_configuration(self) -> ServerConfiguration | None:
        return self.settings_store.load()
