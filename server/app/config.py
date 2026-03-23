from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./literature.db"
    arxiv_query: str = "cat:q-bio.* OR cat:cs.LG"
    arxiv_max_results: int = 30
    rss_feeds: str = ""  # comma-separated URLs, optional
    # OpenAlex: https://docs.openalex.org — 需可访问 api.openalex.org
    openalex_enabled: bool = False
    openalex_mailto: str = "mailto:dev@example.com"  # 礼貌池，请改为真实联系邮箱
    openalex_per_page: int = 25
    openalex_lookback_days: int = 120
    openalex_venue_source_id: str = ""  # 可选，如某会议/期刊的 OpenAlex Source ID（S…）
    openalex_filter_extra: str = ""  # 追加到 filter 的片段，例如 institution 等
    openalex_enrich_arxiv_citations: bool = True
    openalex_enrich_per_run: int = 20
    openalex_enrich_pool: int = 120
    # 订阅会议 + 「会议」频道：按 OpenAlex 来源类型 conference 拉一批近期论文
    openalex_fetch_conference_works: bool = True
    # 用户订阅里指定的 OpenAlex Source 每源抓取条数
    openalex_subscription_per_source: int = 35
    # 全库抓取定时任务间隔（小时），与每日精选任务独立
    ingest_interval_hours: float = 1.0
    paper_ttl_days: int = 60
    event_ttl_days: int = 30
    recommend_alpha_hot: float = 0.45
    recommend_beta_interest: float = 0.45
    recommend_gamma_recency: float = 0.10
    # 每日精选（用户需主动同步 LLM 密钥到服务端；建议仅自建可信实例开启）
    daily_picks_hour: int = 6
    daily_picks_minute: int = 30
    daily_picks_timezone: str = "Asia/Shanghai"
    daily_picks_max_candidates: int = 48
    daily_picks_abstract_chars: int = 600


settings = Settings()
