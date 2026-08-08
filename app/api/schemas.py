"""Pydantic schemaهای ورودی/خروجی API — عمداً از schema های LLM (app/schemas/content.py) جدا هستند."""
from datetime import datetime

from pydantic import BaseModel, Field


class SourceOut(BaseModel):
    id: str  # short_id (۸ کاراکتر اول UUID)
    name: str
    url: str
    source_type: str
    rating: int
    is_active: bool
    is_blacklisted: bool


class SourceCreate(BaseModel):
    url: str
    name: str | None = None
    rating: int = Field(default=3, ge=1, le=5)


class SourceUpdate(BaseModel):
    is_active: bool | None = None
    is_blacklisted: bool | None = None
    rating: int | None = Field(default=None, ge=1, le=5)


class EvaluationOut(BaseModel):
    score_overall: int
    content_type: str | None
    hashtag: str | None
    worth_posting: bool
    rewritten_post: str | None
    llm_provider: str


class ItemOut(BaseModel):
    id: str
    title: str
    url: str
    status: str
    source_name: str
    published_at: datetime | None
    latest_evaluation: EvaluationOut | None
