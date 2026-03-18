class AthenaKnowledgeError(Exception):
    """Base para erros de dominio do servidor."""


class ConfigurationRequiredError(AthenaKnowledgeError):
    """Erro retornado quando o servidor ainda nao foi configurado."""

    def __init__(
        self,
        missing_fields: list[str],
        guidance: str | None = None,
        available_s3_buckets: list[str] | None = None,
        recommended_s3_prefix: str | None = None,
    ) -> None:
        self.missing_fields = missing_fields
        self.available_s3_buckets = available_s3_buckets or []
        self.recommended_s3_prefix = recommended_s3_prefix

        message_parts = ["Configuracao inicial obrigatoria."]
        if missing_fields:
            message_parts.append(
                f"Campos ausentes: {', '.join(missing_fields)}."
            )
        if self.available_s3_buckets:
            message_parts.append(
                "Escolha um bucket nesta lista: "
                f"{', '.join(self.available_s3_buckets)}."
            )
        if recommended_s3_prefix:
            message_parts.append(
                f"Use o prefixo padrao {recommended_s3_prefix}"
            )
        if guidance:
            message_parts.append(guidance)
        elif self.available_s3_buckets and recommended_s3_prefix:
            message_parts.append(
                "Nao peca para o usuario digitar o bucket. Peca para ele "
                "escolher um da lista e so solicite prefixo manual se ele "
                "quiser um prefixo personalizado."
            )

        super().__init__(" ".join(message_parts))


class InvalidConfigurationError(AthenaKnowledgeError):
    """Erro de validacao de configuracao."""


class CatalogEntryNotFoundError(AthenaKnowledgeError):
    """Erro para skills e catalogo inexistentes."""


class QueryExecutionError(AthenaKnowledgeError):
    """Erro de execucao ou falha no Athena."""
