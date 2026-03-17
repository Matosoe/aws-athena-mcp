from __future__ import annotations

from athena_knowledge_mcp.core.models import QueryExecutionRecord


def format_large_result_message(record: QueryExecutionRecord) -> str:
    size = record.result_size_bytes or 0
    location = record.output_location or "desconhecido"
    return (
        "Resultado grande detectado. "
        f"Arquivo com {size} bytes em {location}. "
        "Use materialize_large_result_locally para baixar o arquivo."
    )
