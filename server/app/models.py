from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Paper(Base):
    __tablename__ = "papers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    external_id: Mapped[str] = mapped_column(String(256), unique=True, index=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    abstract: Mapped[str] = mapped_column(Text, default="")
    authors_text: Mapped[str] = mapped_column(Text, default="")  # 展示用，如 "A, B et al."
    pdf_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    html_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    source: Mapped[str] = mapped_column(String(64), index=True)  # arxiv, rss:host
    # OpenAlex Work 的 primary_location.source.id 规范为短码 S…，用于按用户订阅的会议 Source 精确匹配
    openalex_source_key: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    primary_category: Mapped[str | None] = mapped_column(String(128), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    citation_count: Mapped[int] = mapped_column(Integer, default=0)
    citation_synced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    stats: Mapped["PaperStat | None"] = relationship(back_populates="paper", uselist=False)


class PaperStat(Base):
    __tablename__ = "paper_stats"

    paper_id: Mapped[int] = mapped_column(ForeignKey("papers.id", ondelete="CASCADE"), primary_key=True)
    hot_score: Mapped[float] = mapped_column(Float, default=0.0, index=True)
    impression_count: Mapped[int] = mapped_column(Integer, default=0)
    click_count: Mapped[int] = mapped_column(Integer, default=0)
    save_count: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    paper: Mapped["Paper"] = relationship(back_populates="stats")


class UserProfile(Base):
    __tablename__ = "user_profiles"

    user_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    keywords: Mapped[str] = mapped_column(Text, default="")  # comma-separated subscription prefs
    subscription_keywords_json: Mapped[str] = mapped_column(Text, default="[]")
    subscription_journals_json: Mapped[str] = mapped_column(Text, default="[]")
    subscription_conferences_json: Mapped[str] = mapped_column(Text, default="[]")
    interest_blob: Mapped[str] = mapped_column(Text, default="{}")  # JSON: word -> weight
    # 每日精选：用户自愿同步的 OpenAI 兼容端点（与客户端 BYOK 一致，须 HTTPS 自建可信）
    llm_base_url: Mapped[str] = mapped_column(Text, default="")
    llm_api_key: Mapped[str] = mapped_column(Text, default="")
    llm_model: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class PaperUserBlurb(Base):
    """用户对某篇论文 Feed 一句话总结（用户 LLM 生成，按用户隔离）。"""

    __tablename__ = "paper_user_blurbs"

    user_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    paper_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("papers.id", ondelete="CASCADE"), primary_key=True
    )
    blurb: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class DailyPick(Base):
    """按用户、按自然日缓存 LLM 选出的论文列表。"""

    __tablename__ = "daily_picks"
    __table_args__ = (UniqueConstraint("user_id", "pick_date", name="uq_daily_picks_user_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    pick_date: Mapped[str] = mapped_column(String(10), index=True)  # YYYY-MM-DD（与 daily_picks_timezone 一致）
    paper_ids_json: Mapped[str] = mapped_column(Text, default="[]")
    curator_note: Mapped[str] = mapped_column(Text, default="")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


class FcmToken(Base):
    __tablename__ = "fcm_tokens"

    user_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    token: Mapped[str] = mapped_column(String(512), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class AnalyticsEvent(Base):
    __tablename__ = "analytics_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    paper_id: Mapped[int | None] = mapped_column(
        ForeignKey("papers.id", ondelete="SET NULL"), nullable=True, index=True
    )
    surface: Mapped[str | None] = mapped_column(String(32), nullable=True)
    position: Mapped[int | None] = mapped_column(Integer, nullable=True)
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
