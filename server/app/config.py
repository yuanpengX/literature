from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./literature.db"
    arxiv_query: str = "cat:q-bio.* OR cat:cs.LG"
    arxiv_max_results: int = 30
    # 用户打开 arXiv 频道时，按其订阅关键词调用 export.arxiv.org/api/query（需遵守 polite 限流）
    arxiv_keyword_max_results: int = 40  # ARXIV_KEYWORD_MAX_RESULTS
    arxiv_user_refresh_seconds: float = 600.0  # 同一用户两次关键词拉取最小间隔（秒）；ARXIV_USER_REFRESH_SECONDS
    arxiv_keyword_max_terms: int = 12  # 拼 OR 查询时最多采用几条关键词；ARXIV_KEYWORD_MAX_TERMS
    rss_feeds: str = ""  # comma-separated URLs, optional
    # OpenAlex: https://docs.openalex.org — 需可访问 api.openalex.org
    openalex_enabled: bool = False
    # 官方免费 key：https://openalex.org/settings/api — 建议填写以获得每日免费额度与稳定限流
    openalex_api_key: str = ""
    openalex_mailto: str = "mailto:admin@cppteam.cn"  # OpenAlex 礼貌池；请改为可收信邮箱
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
    # Feed：与每日精选同源订阅预筛；无启用订阅且为 true 时返回空列表
    feed_strict_subscription_filter: bool = False  # FEED_STRICT_SUBSCRIPTION_FILTER
    feed_merge_max_total: int = 900  # FEED_MERGE_MAX_TOTAL
    feed_merge_per_channel: int = 350  # FEED_MERGE_PER_CHANNEL
    feed_fresh_days: float = 7.0  # FEED_FRESH_DAYS
    feed_trending_hot_norm_min: float = 0.55  # FEED_TRENDING_HOT_NORM_MIN
    # 每日精选（用户需主动同步 LLM 密钥到服务端；建议仅自建可信实例开启）
    daily_picks_hour: int = 6
    daily_picks_minute: int = 30
    daily_picks_timezone: str = "Asia/Shanghai"
    daily_picks_max_candidates: int = 48
    daily_picks_abstract_chars: int = 600
    # 微信小程序登录（jscode2session）与 JWT；仅服务端持有 app secret
    wechat_miniprogram_app_id: str = ""
    wechat_miniprogram_app_secret: str = ""
    jwt_secret: str = ""
    jwt_expires_days: int = 30


settings = Settings()
