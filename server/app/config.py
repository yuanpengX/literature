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
    paper_ttl_days: int = 60
    event_ttl_days: int = 30
    recommend_alpha_hot: float = 0.45
    recommend_beta_interest: float = 0.45
    recommend_gamma_recency: float = 0.10


settings = Settings()
