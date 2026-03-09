class AthenaKnowledgeError(Exception):
    """Base para erros de dominio do servidor."""


class ConfigurationRequiredError(AthenaKnowledgeError):
    """Erro retornado quando o servidor ainda nao foi configurado."""

    def __init__(self, missing_fields: list[str]) -> None:
        self.missing_fields = missing_fields
        super().__init__("Configuracao inicial obrigatoria.")


class InvalidConfigurationError(AthenaKnowledgeError):
    """Erro de validacao de configuracao."""


class CatalogEntryNotFoundError(AthenaKnowledgeError):
    """Erro para skills e catalogo inexistentes."""


class QueryExecutionError(AthenaKnowledgeError):
    """Erro de execucao ou falha no Athena."""
