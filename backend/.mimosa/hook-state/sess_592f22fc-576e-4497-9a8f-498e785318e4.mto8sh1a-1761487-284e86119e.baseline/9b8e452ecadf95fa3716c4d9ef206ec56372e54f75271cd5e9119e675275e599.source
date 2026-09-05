"""Chat request/response schemas."""

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Natural language query from the user."""

    query: str = Field(
        ..., min_length=1, max_length=5000, description="The user's natural language question"
    )
    conversation_id: str | None = Field(
        None, description="Optional conversation ID for multi-turn context"
    )
    confirm_large_query: bool = Field(
        False,
        description="Explicit confirmation to run a query whose EXPLAIN row "
        "estimate exceeds the large-query threshold (>1M rows)",
    )


class ChatResponse(BaseModel):
    """Response from the NL → SQL → Chart → Narrative pipeline."""

    conversation_id: str
    session_id: str | None = Field(
        None,
        description="Pipeline session id — the feedback API's key (also in the SSE start event)",
    )
    query: str
    sql: str | None = None
    sql_explanation: str | None = None
    chart_spec: dict | None = None
    narrative: str | None = None
    chart_image_base64: str | None = None
    warnings: list[str] = []
    requires_confirmation: bool = Field(
        False, description="True when the query needs explicit confirmation (>1M estimated rows)"
    )
    row_estimate: int | None = Field(
        None, description="EXPLAIN-estimated row count, when available"
    )
