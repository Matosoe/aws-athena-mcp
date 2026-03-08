from __future__ import annotations

from dataclasses import dataclass

from athena_knowledge_mcp.core.models import AwsSecretMaterial, ServerConfiguration
from athena_knowledge_mcp.core.secrets_store import SecretsStore
from athena_knowledge_mcp.core.settings_store import SettingsStore


@dataclass(slots=True)
class LocalConfigRepository:
    settings_store: SettingsStore
    secrets_store: SecretsStore

    def load_configuration(self) -> ServerConfiguration | None:
        return self.settings_store.load()

    def save_configuration(self, configuration: ServerConfiguration) -> None:
        self.settings_store.save(configuration)

    def load_secrets(self) -> AwsSecretMaterial:
        return self.secrets_store.load()

    def save_secrets(self, secrets: AwsSecretMaterial) -> None:
        self.secrets_store.save(secrets)