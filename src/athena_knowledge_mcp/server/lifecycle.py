from __future__ import annotations

from dataclasses import dataclass

from athena_knowledge_mcp.core.config import AppConfig


@dataclass(slots=True)
class AppContainer:
    config: AppConfig


def build_container() -> AppContainer:
    return AppContainer(config=AppConfig.default())
