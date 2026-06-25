from typing import Any, Optional
from pydantic import BaseModel, field_validator


class PriorTurnContext(BaseModel):
    question: str
    answer: str = ""
    tool_calls: list[str] = []
    sources: list[dict[str, Any]] = []
    has_chart: bool = False
    analysis_context: Optional[dict[str, Any]] = None


class FollowUpAction(BaseModel):
    label: str
    message: str
    action: Optional[str] = None
    context: Optional[dict[str, Any]] = None


class ChatRequest(BaseModel):
    message: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    prior_context: Optional[PriorTurnContext] = None
    follow_up_action: Optional[FollowUpAction] = None

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
    comparison_period_label: Optional[str] = None
    limitations: list[str] = []


class ChatResponse(BaseModel):
    answer: str
    tool_calls: list[str]
    sources: list[SourceMeta]
    chart: Optional[Any] = None
    charts: list[Any] = []
    deep_dive: Optional[Any] = None
    follow_up_actions: list[dict[str, Any]] = []
    analysis_context: Optional[dict[str, Any]] = None
    limitations: list[str]
    supplier_id: str
    generated_at: str
