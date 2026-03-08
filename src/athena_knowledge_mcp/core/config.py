from __future__ import annotations

from dataclasses import dataclass

from athena_knowledge_mcp.core.models import RuntimePaths, ServerConfiguration
from athena_knowledge_mcp.core.secrets_store import SecretsStore
from athena_knowledge_mcp.core.settings_store import SettingsStore


@dataclass(slots=True)
class AppConfig:
    runtime_paths: RuntimePaths
    settings_store: SettingsStore
    secrets_store: SecretsStore

    @classmethod
    def default(cls) -> AppConfig:
        runtime_paths = RuntimePaths()
        return cls(
            runtime_paths=runtime_paths,
            settings_store=SettingsStore(runtime_paths.settings_file),
            secrets_store=SecretsStore(runtime_paths.secrets_file),
        )

    def load_configuration(self) -> ServerConfiguration | None:
        return self.settings_store.load()
