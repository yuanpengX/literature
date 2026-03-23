from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class PaperOut(BaseModel):
    id: int
    external_id: str
    title: str
    abstract: str
    pdf_url: str | None
    html_url: str | None
    source: str
    primary_category: str | None
    published_at: datetime | None
    citation_count: int = 0
    hot_score: float = 0.0
    rank_reason: Literal["trending", "for_you", "recent"] | None = None

    class Config:
        from_attributes = True


class FeedResponse(BaseModel):
    items: list[PaperOut]
    next_cursor: str | None


class PreferencesUpdate(BaseModel):
    keywords: str = Field(default="", description="Comma-separated subscription keywords")


class AnalyticsEventIn(BaseModel):
    event_type: str
    paper_id: int | None = None
    surface: str | None = None
    position: int | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class AnalyticsBatchIn(BaseModel):
    events: list[AnalyticsEventIn]


class SearchResponse(BaseModel):
    items: list[PaperOut]


class FcmTokenIn(BaseModel):
    token: str
