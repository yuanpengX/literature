"""HTML / 富文本摘要转为纯文本，供 API 与一句话兜底使用。"""

from __future__ import annotations

import html
import re

_TAG_RE = re.compile(r"<[^>]*>", re.DOTALL)


def strip_html_to_plain(s: str | None) -> str:
    if not s:
        return ""
    t = str(s).strip()
    if not t:
        return ""
    t = _TAG_RE.sub(" ", t)
    t = html.unescape(t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def heuristic_feed_blurb_from_abstract(abstract_plain: str, *, max_len: int = 88) -> str:
    """无 LLM 缓存时，用摘要首句/截断作为 Feed 一句话展示。"""
    plain = strip_html_to_plain(abstract_plain)
    if not plain:
        return ""
    for sep in ("。", "！", "？", ".", "!", "?"):
        i = plain.find(sep)
        if 8 <= i <= max_len + 40:
            return plain[: i + 1].strip()
    if len(plain) <= max_len:
        return plain
    return plain[: max_len - 1].strip() + "…"
