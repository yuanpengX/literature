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


class UserLlmCredentials(BaseModel):
    """同步到服务端的 OpenAI 兼容配置（用于每日精选定时任务）。"""

    base_url: str = Field(..., description="根地址，如 https://api.deepseek.com/v1")
    api_key: str = Field(..., min_length=1)
    model: str = Field(..., min_length=1, description="chat completions 模型 id")


class DailyPicksResponse(BaseModel):
    date: str
    items: list[PaperOut]
    note: str | None = None
    error: str | None = None
    server_llm_configured: bool = False


class SubscriptionKeywordItem(BaseModel):
    text: str
    enabled: bool = True


class SubscriptionJournalItem(BaseModel):
    id: str
    enabled: bool = True
    name: str | None = Field(default=None, description="自定义期刊展示名")
    rss: str | None = Field(default=None, description="自定义 RSS；若填写则优先于预设")


class SubscriptionConferenceItem(BaseModel):
    id: str
    enabled: bool = True
    name: str | None = Field(default=None, description="自定义会议展示名")
    openalex_source_id: str | None = Field(
        default=None,
        description="OpenAlex Source ID，如 S1234567890 或 https://openalex.org/S…",
    )


class JournalPresetOut(BaseModel):
    id: str
    name: str
    abbr: str
    issn: str
    rss: str | None = None


class ConferencePresetOut(BaseModel):
    id: str
    name: str
    abbr: str
    note: str | None = None
    openalex_source_id: str | None = None


class SubscriptionCatalogResponse(BaseModel):
    journals: list[JournalPresetOut]
    conferences: list[ConferencePresetOut]
    default_keywords: list[SubscriptionKeywordItem]
    default_journals: list[SubscriptionJournalItem]
    default_conferences: list[SubscriptionConferenceItem]


class UserSubscriptionsResponse(BaseModel):
    keywords: list[SubscriptionKeywordItem]
    journals: list[SubscriptionJournalItem]
    conferences: list[SubscriptionConferenceItem]


class UserSubscriptionsPut(BaseModel):
    keywords: list[SubscriptionKeywordItem] = Field(default_factory=list)
    journals: list[SubscriptionJournalItem] = Field(default_factory=list)
    conferences: list[SubscriptionConferenceItem] = Field(default_factory=list)
