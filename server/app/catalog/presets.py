"""
期刊 / 会议预设目录：供订阅配置页展示，并由抓取任务根据用户启用的期刊合并 RSS。
RSS 链接为常见模板，若出版社改版需在预设中更新。
"""

from __future__ import annotations

from dataclasses import dataclass
import json


@dataclass(frozen=True)
class JournalPreset:
    id: str
    name: str
    abbr: str
    issn: str
    rss: str | None


@dataclass(frozen=True)
class ConferencePreset:
    id: str
    name: str
    abbr: str
    note: str | None = None


# 与药物发现 / 分子设计 / AI for science 相关；含用户点名的 JCM、JCIM 等
JOURNAL_PRESETS: dict[str, JournalPreset] = {
    "jcm": JournalPreset(
        id="jcm",
        name="Journal of Clinical Medicine",
        abbr="J Clin Med",
        issn="2077-0383",
        rss="https://www.mdpi.com/rss/journal/jcm",
    ),
    "jcim": JournalPreset(
        id="jcim",
        name="Journal of Chemical Information and Modeling",
        abbr="J Chem Inf Model",
        issn="1549-9596",
        # ACS 刊名代码 jcisd8（非 jcim）
        rss="https://pubs.acs.org/action/showFeed?type=etoc&feed=rss&jc=jcisd8",
    ),
    "jmedchem": JournalPreset(
        id="jmedchem",
        name="Journal of Medicinal Chemistry",
        abbr="J Med Chem",
        issn="0022-2623",
        rss="https://pubs.acs.org/action/showFeed?type=etoc&feed=rss&jc=jmcmar",
    ),
    "jctc": JournalPreset(
        id="jctc",
        name="Journal of Chemical Theory and Computation",
        abbr="J Chem Theory Comput",
        issn="1549-9618",
        rss="https://pubs.acs.org/action/showFeed?type=etoc&feed=rss&jc=jctcce",
    ),
    "natmachintell": JournalPreset(
        id="natmachintell",
        name="Nature Machine Intelligence",
        abbr="Nat Mach Intell",
        issn="2522-5839",
        rss="https://feeds.nature.com/natmachintell/rss/current",
    ),
    "pharmaceutics": JournalPreset(
        id="pharmaceutics",
        name="Pharmaceutics",
        abbr="Pharmaceutics",
        issn="1999-4923",
        rss="https://www.mdpi.com/rss/journal/pharmaceutics",
    ),
    "bioinformatics": JournalPreset(
        id="bioinformatics",
        name="Bioinformatics",
        abbr="Bioinformatics",
        issn="1367-4811",
        rss="https://academic.oup.com/rss/site_5337/3234.xml",
    ),
    "jcheminf": JournalPreset(
        id="jcheminf",
        name="Journal of Cheminformatics",
        abbr="J Cheminform",
        issn="1758-2946",
        rss="https://jcheminf.biomedcentral.com/articles/most-recent/rss.xml",
    ),
}

CONFERENCE_PRESETS: dict[str, ConferencePreset] = {
    "neurips": ConferencePreset(
        id="neurips",
        name="NeurIPS",
        abbr="NeurIPS",
        note="AI 顶会；会议论文多经 arXiv 收录，可结合 arXiv 频道与关键词",
    ),
    "icml": ConferencePreset(id="icml", name="International Conference on Machine Learning", abbr="ICML", note=None),
    "iclr": ConferencePreset(
        id="iclr",
        name="International Conference on Learning Representations",
        abbr="ICLR",
        note=None,
    ),
    "ismb": ConferencePreset(
        id="ismb",
        name="Intelligent Systems for Molecular Biology",
        abbr="ISMB",
        note="计算生物学 / 生物信息学重要会议",
    ),
    "recomb": ConferencePreset(
        id="recomb",
        name="Research in Computational Molecular Biology",
        abbr="RECOMB",
        note=None,
    ),
}


def default_subscription_keywords() -> list[dict]:
    return [
        {"text": "drug discovery", "enabled": True},
        {"text": "molecular design", "enabled": True},
        {"text": "deep learning", "enabled": True},
        {"text": "generative model", "enabled": True},
        {"text": "protein design", "enabled": True},
        {"text": "virtual screening", "enabled": True},
        {"text": "binding affinity", "enabled": True},
        {"text": "cheminformatics", "enabled": True},
        {"text": "AI drug", "enabled": True},
        {"text": "diffusion model", "enabled": True},
    ]


def default_subscription_journals() -> list[dict]:
    return [
        {"id": "jcm", "enabled": True},
        {"id": "jcim", "enabled": True},
        {"id": "jmedchem", "enabled": True},
        {"id": "natmachintell", "enabled": True},
        {"id": "pharmaceutics", "enabled": True},
        {"id": "bioinformatics", "enabled": True},
        {"id": "jcheminf", "enabled": True},
        {"id": "jctc", "enabled": True},
    ]


def default_subscription_conferences() -> list[dict]:
    return [
        {"id": "neurips", "enabled": True},
        {"id": "icml", "enabled": True},
        {"id": "iclr", "enabled": True},
        {"id": "ismb", "enabled": True},
        {"id": "recomb", "enabled": True},
    ]


def keywords_csv_from_subscription_json(json_str: str) -> str:
    try:
        arr = json.loads(json_str or "[]")
    except json.JSONDecodeError:
        return ""
    if not isinstance(arr, list):
        return ""
    parts: list[str] = []
    for x in arr:
        if not isinstance(x, dict):
            continue
        if not x.get("enabled", True):
            continue
        t = (x.get("text") or "").strip()
        if t:
            parts.append(t)
    return ",".join(parts)
