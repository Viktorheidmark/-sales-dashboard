from typing import Any, Optional
from pydantic import BaseModel, field_validator


class SaveInsightRequest(BaseModel):
    question: str
    answer: str
    chart: Optional[dict] = None
    tool_calls: list[str] = []
    sources: list[dict] = []
    limitations: list[str] = []

    @field_validator("question")
    @classmethod
    def question_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("question must not be empty")
        if len(v) > 2000:
            raise ValueError("question must be 2000 characters or fewer")
        return v

    @field_validator("answer")
    @classmethod
    def answer_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("answer must not be empty")
        return v


class SaveInsightResponse(BaseModel):
    id: str
    created_at: str


class InsightSummary(BaseModel):
    id: str
    question: str
    answer_preview: str
    created_at: str
    has_chart: bool
    source_tools: list[str]


class InsightDetail(BaseModel):
    id: str
    question: str
    answer: str
    chart: Optional[Any] = None
    tool_calls: list[str]
    sources: list[dict]
    limitations: list[str]
    created_at: str
