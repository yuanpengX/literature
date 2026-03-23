"""新用户默认订阅字段（与 subscriptions 首次 GET、微信登录建号一致）。"""

from __future__ import annotations

import json

from app.catalog.presets import (
    default_subscription_conferences,
    default_subscription_journals,
    default_subscription_keywords,
    keywords_csv_from_subscription_json,
)


def default_subscription_fields() -> dict[str, str]:
    kw_j = json.dumps(default_subscription_keywords(), ensure_ascii=False)
    j_j = json.dumps(default_subscription_journals(), ensure_ascii=False)
    c_j = json.dumps(default_subscription_conferences(), ensure_ascii=False)
    csv = keywords_csv_from_subscription_json(kw_j)
    return {
        "keywords": csv,
        "subscription_keywords_json": kw_j,
        "subscription_journals_json": j_j,
        "subscription_conferences_json": c_j,
}


def default_subscription_tuple() -> tuple[str, str, str, str]:
    """(subscription_keywords_json, subscription_journals_json, subscription_conferences_json, keywords_csv)"""
    d = default_subscription_fields()
    return (
        d["subscription_keywords_json"],
        d["subscription_journals_json"],
        d["subscription_conferences_json"],
        d["keywords"],
    )
