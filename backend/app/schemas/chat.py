from typing import Any, Optional
from pydantic import BaseModel, field_validator


class PriorTurnContext(BaseModel):
    question: str
    answer: str = ""
    tool_calls: list[str] = []
    sources: list[dict[str, Any]] = []


class ChatRequest(BaseModel):
    message: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    prior_context: Optional[PriorTurnContext] = None

    @field_validator("message")
    @classmethod
    def message_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("message must not be empty")
        if len(v) > 2000:
            raise ValueError("message must be 2000 characters or fewer")
        return v


class SourceMeta(BaseModel):
    tool: str
    source: str
    supplier_id: str
    generated_at: str
    row_count: Optional[int] = None
    date_range: Optional[Any] = None
    limitations: list[str] = []


class ChatResponse(BaseModel):
    answer: str
    tool_calls: list[str]
    sources: list[SourceMeta]
    chart: Optional[Any] = None
    limitations: list[str]
    supplier_id: str
    generated_at: str
