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
# ACS 等 TOC RSS：「刊名, Volume N, Issue M, Page a-b, …」整段无正文摘要
_METADATA_VOL_ISSUE_PAGE_RE = re.compile(
    r"\bvolume\s+\d+\s*,\s*issue\s+\d+\s*,\s*page\s+[\d\-–]+",
    re.I,
)
_METADATA_ARTICLE_NUMBER_RE = re.compile(
    r"\barticle\s+number\s*:",
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


def _is_metadata_only_plain(plain: str) -> bool:
    """已去 HTML 的纯文本：判断是否仅为期刊卷期/出版信息（非论文摘要）。"""
    if not plain or not plain.strip():
        return True
    plain = plain.strip()
    wc = len(plain.split())
    low = plain.casefold()
    if _METADATA_JOURNAL_ISSUE_RE.search(plain):
        return True
    if _METADATA_JOURNAL_LINE_RE.match(plain):
        return True
    # ACS eTOC：Journal of …, Volume 69, Issue 5, Page 5059-5062, March 12, 2026.
    if _METADATA_VOL_ISSUE_PAGE_RE.search(plain) and wc <= 48:
        return True
    # Springer Nature 子刊：Article number: … (年份)
    if _METADATA_ARTICLE_NUMBER_RE.search(plain) and wc <= 28:
        return True
    # 短行且同时出现 volume + issue（不限定 Journal of）
    if (
        "volume" in low
        and re.search(r"\bissue\s+\d+", plain, re.I)
        and wc <= 28
        and len(plain) <= 220
    ):
        return True
    # Nature 系：刊名 + Published online + doi，doi 后无正文
    if "published online" in low and len(plain) < 320 and re.search(r"doi\s*:\s*10\.\d+", plain, re.I):
        tail = plain.split("doi", 1)[-1]
        if not _SENT_END_RE.search(tail) or len(tail.strip()) < 22:
            return True
    if len(plain) < 30 and not _SENT_END_RE.search(plain):
        return True
    return False


def strip_rss_boilerplate_html(html: str | None) -> str:
    """
    - Nature / Springer：首段 <p> 常为刊名+Published online+doi，正文在第一个 </p> 之后。
    - ACS：首块常为 <div><cite>刊名, Volume… Issue… Page…</cite></div>，无摘要时应整段丢弃。
    """
    if not html:
        return ""
    s = str(html).strip()
    if not s:
        return ""

    # ACS：<div …><cite>…Volume…Issue…Page…</cite></div>
    cite_div = re.match(
        r'(?is)^\s*<div[^>]*>\s*<cite[^>]*>([\s\S]*?)</cite>\s*</div>\s*',
        s,
    )
    if cite_div:
        inner_plain = strip_html_to_plain(cite_div.group(1))
        if _is_metadata_only_plain(inner_plain):
            s = s[cite_div.end() :].lstrip()
    else:
        cite_only = re.match(r"(?is)^\s*<cite[^>]*>([\s\S]*?)</cite>\s*", s)
        if cite_only:
            inner_plain = strip_html_to_plain(cite_only.group(1))
            if _is_metadata_only_plain(inner_plain):
                s = s[cite_only.end() :].lstrip()

    if "</p>" not in s:
        return s
    head, tail = s.split("</p>", 1)
    head_plain = strip_html_to_plain(head + "</p>").lower()
    tail = tail.strip()
    if not tail:
        return s
    meta_hints = ("published online", "doi:10.", "doi:", "online publication")
    if any(h in head_plain for h in meta_hints):
        return tail
    return s


def _is_metadata_only_abstract(text: str) -> bool:
    """RSS 等场景：摘要仅为期刊卷期元信息、无正文摘要时返回 True。"""
    return _is_metadata_only_plain(strip_html_to_plain(text))


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
