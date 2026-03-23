class AthenaKnowledgeError(Exception):
    """Base para erros de dominio do servidor."""


class ConfigurationRequiredError(AthenaKnowledgeError):
    """Erro retornado quando o servidor ainda nao foi configurado."""

    def __init__(
        self,
        missing_fields: list[str],
        guidance: str | None = None,
    ) -> None:
        self.missing_fields = missing_fields

        message_parts = ["Configuracao inicial obrigatoria."]
        if missing_fields:
            message_parts.append(f"Campos ausentes: {', '.join(missing_fields)}.")
        if guidance:
            message_parts.append(guidance)

        super().__init__(" ".join(message_parts))


class InvalidConfigurationError(AthenaKnowledgeError):
    """Erro de validacao de configuracao."""


class CatalogEntryNotFoundError(AthenaKnowledgeError):
    """Erro para skills e catalogo inexistentes."""


class QueryExecutionError(AthenaKnowledgeError):
    """Erro de execucao ou falha no Athena."""
