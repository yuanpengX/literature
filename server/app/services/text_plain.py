"""HTML / 富文本摘要转为纯文本，供 API 与一句话兜底使用。"""

from __future__ import annotations

import html
import re

_TAG_RE = re.compile(r"<[^>]*>", re.DOTALL)

# e.g. "Journal of Foo, Volume 12, Issue 3" / "The Journal of Bar, Vol. 1, No. 2"
_METADATA_JOURNAL_LINE_RE = re.compile(
    r"^(the\s+)?journal\s+of\s+.+\s*,\s*vol(ume)?\s*\d+",
    re.I,
)
_METADATA_JOURNAL_ISSUE_RE = re.compile(
    r"journal\s+of\s+.+\s*,\s*volume\s+\d+\s*,\s*issue\s+\d+",
    re.I,
)
_SENT_END_RE = re.compile(r"[。！？.!?]")


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


def _is_metadata_only_abstract(text: str) -> bool:
    """RSS 等场景：摘要仅为期刊卷期元信息、无正文摘要时返回 True。"""
    plain = strip_html_to_plain(text)
    if not plain:
        return True
    if _METADATA_JOURNAL_ISSUE_RE.search(plain):
        return True
    if _METADATA_JOURNAL_LINE_RE.match(plain.strip()):
        return True
    if len(plain) < 30 and not _SENT_END_RE.search(plain):
        return True
    return False


_WS_RE = re.compile(r"\s+")


def normalized_plain_blob(s: str | None) -> str:
    """比较用：去 HTML、压空白、小写。"""
    t = strip_html_to_plain(s)
    return _WS_RE.sub(" ", t).strip().casefold()


def feed_blurb_redundant_with_abstract(blurb: str | None, abstract: str | None) -> bool:
    """一句话与正文实质相同（或一方为另一方前缀且余量很短）时，避免列表里双显。"""
    b = normalized_plain_blob(blurb)
    a = normalized_plain_blob(abstract)
    if not b or not a:
        return False
    if b == a:
        return True
    head = a[:120]
    if len(b) >= 8 and head.startswith(b):
        return True
    if len(b) >= 20 and a.startswith(b) and (len(a) - len(b)) <= 24:
        return True
    if len(a) >= 20 and b.startswith(a) and (len(b) - len(a)) <= 24:
        return True
    return False
