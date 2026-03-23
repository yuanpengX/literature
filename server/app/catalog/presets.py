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
    # OpenAlex Source 短码（S…）；在 openalex.org 搜索会议 proceedings 可得
    openalex_source_id: str | None = None


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

# 订阅预筛：OpenAlex venue 展示名常与预设简称不一致（如 NeurIPS → Advances in Neural…），补充可匹配子串
CONFERENCE_EXTRA_NEEDLES_BY_PRESET_ID: dict[str, tuple[str, ...]] = {
    "neurips": (
        "neural information processing",
        "advances in neural",
    ),
    "icml": (
        "international conference on machine learning",
        "machine learning research",
        "proc. mach. learn",
    ),
    "iclr": ("international conference on learning representations",),
    "ismb": ("intelligent systems for molecular biology",),
    "recomb": ("research in computational molecular biology",),
    "cvpr": ("computer vision and pattern recognition", " ieee/cvf"),
    "eccv": ("european conference on computer vision",),
    "acl": (
        "association for computational linguistics",
        "meeting of the association for computational linguistics",
    ),
    "emnlp": ("empirical methods in natural language processing",),
    "naacl": ("north american chapter of the acl", "north american chapter of the association"),
    "aaai": ("aaai conference on artificial intelligence",),
    "ijcai": ("international joint conference on artificial intelligence",),
    "kdd": ("knowledge discovery and data mining", "sigkdd"),
    "www": ("the web conference", "international world wide web", "www conference"),
    "sigir": ("research and development in information retrieval", "sigir"),
    "aistats": ("artificial intelligence and statistics", "aistats"),
    "colt": ("learning theory", "colt"),
    "uai": ("uncertainty in artificial intelligence",),
    "mlsys": ("machine learning and systems", "mlsys"),
    "iccv": ("international conference on computer vision", "ieee/cvf"),
    "eacl": ("european chapter of the acl",),
    "coling": ("computational linguistics", "international conference on computational linguistics"),
    "corl": ("conference on robot learning", "robot learning"),
    "robotics_rss": ("robotics: science and systems", "robotics science and systems"),
    "icra": ("international conference on robotics and automation",),
    "iros": ("intelligent robots and systems",),
    "cikm": ("information and knowledge management", "cikm"),
    "wsdm": ("web search and data mining", "wsdm"),
    "facct": ("fairness, accountability and transparency", "facct"),
    "aies": ("ai, ethics, and society", "artificial intelligence, ethics"),
    "mm": ("acm multimedia", "international conference on multimedia"),
}


CONFERENCE_PRESETS: dict[str, ConferencePreset] = {
    "neurips": ConferencePreset(
        id="neurips",
        name="NeurIPS",
        abbr="NeurIPS",
        note="AI 顶会；可在 openalex.org 搜 NeurIPS proceedings 将 Source ID 填入手动订阅",
        openalex_source_id=None,
    ),
    "icml": ConferencePreset(
        id="icml",
        name="International Conference on Machine Learning",
        abbr="ICML",
        note=None,
        openalex_source_id=None,
    ),
    "iclr": ConferencePreset(
        id="iclr",
        name="International Conference on Learning Representations",
        abbr="ICLR",
        note=None,
        openalex_source_id=None,
    ),
    "ismb": ConferencePreset(
        id="ismb",
        name="Intelligent Systems for Molecular Biology",
        abbr="ISMB",
        note="计算生物学 / 生物信息学重要会议",
        openalex_source_id=None,
    ),
    "recomb": ConferencePreset(
        id="recomb",
        name="Research in Computational Molecular Biology",
        abbr="RECOMB",
        note=None,
        openalex_source_id=None,
    ),
    "cvpr": ConferencePreset(
        id="cvpr",
        name="Computer Vision and Pattern Recognition",
        abbr="CVPR",
        note="计算机视觉顶会；可在 OpenAlex 搜 CVPR proceedings 填 Source ID",
        openalex_source_id=None,
    ),
    "eccv": ConferencePreset(
        id="eccv",
        name="European Conference on Computer Vision",
        abbr="ECCV",
        note=None,
        openalex_source_id=None,
    ),
    "acl": ConferencePreset(
        id="acl",
        name="Annual Meeting of the Association for Computational Linguistics",
        abbr="ACL",
        note="NLP 顶会",
        openalex_source_id=None,
    ),
    "emnlp": ConferencePreset(
        id="emnlp",
        name="Conference on Empirical Methods in Natural Language Processing",
        abbr="EMNLP",
        note=None,
        openalex_source_id=None,
    ),
    "naacl": ConferencePreset(
        id="naacl",
        name="North American Chapter of the ACL",
        abbr="NAACL",
        note=None,
        openalex_source_id=None,
    ),
    "aaai": ConferencePreset(
        id="aaai",
        name="AAAI Conference on Artificial Intelligence",
        abbr="AAAI",
        note=None,
        openalex_source_id=None,
    ),
    "ijcai": ConferencePreset(
        id="ijcai",
        name="International Joint Conference on Artificial Intelligence",
        abbr="IJCAI",
        note=None,
        openalex_source_id=None,
    ),
    "kdd": ConferencePreset(
        id="kdd",
        name="ACM SIGKDD Conference on Knowledge Discovery and Data Mining",
        abbr="KDD",
        note=None,
        openalex_source_id=None,
    ),
    "www": ConferencePreset(
        id="www",
        name="The Web Conference",
        abbr="WWW",
        note="原 WWW / TheWebConf",
        openalex_source_id=None,
    ),
    "sigir": ConferencePreset(
        id="sigir",
        name="ACM SIGIR Conference on Research and Development in Information Retrieval",
        abbr="SIGIR",
        note=None,
        openalex_source_id=None,
    ),
    # —— 以下补充常见 AI / ML / 机器人 / 数据挖掘 会议目录（与 OpenAlex 全局会议批次 + 订阅预筛别名配合）——
    "aistats": ConferencePreset(
        id="aistats",
        name="International Conference on Artificial Intelligence and Statistics",
        abbr="AISTATS",
        note="机器学习与统计",
        openalex_source_id=None,
    ),
    "colt": ConferencePreset(
        id="colt",
        name="Annual Conference on Learning Theory",
        abbr="COLT",
        note="学习理论",
        openalex_source_id=None,
    ),
    "uai": ConferencePreset(
        id="uai",
        name="Conference on Uncertainty in Artificial Intelligence",
        abbr="UAI",
        note="不确定性推理与概率图模型",
        openalex_source_id=None,
    ),
    "mlsys": ConferencePreset(
        id="mlsys",
        name="Conference on Machine Learning and Systems",
        abbr="MLSys",
        note="机器学习系统与工程",
        openalex_source_id=None,
    ),
    "iccv": ConferencePreset(
        id="iccv",
        name="IEEE/CVF International Conference on Computer Vision",
        abbr="ICCV",
        note="计算机视觉顶会（与 CVPR、ECCV 并列）",
        openalex_source_id=None,
    ),
    "eacl": ConferencePreset(
        id="eacl",
        name="Conference of the European Chapter of the ACL",
        abbr="EACL",
        note="欧洲计算语言学分会",
        openalex_source_id=None,
    ),
    "coling": ConferencePreset(
        id="coling",
        name="International Conference on Computational Linguistics",
        abbr="COLING",
        note="计算语言学",
        openalex_source_id=None,
    ),
    "corl": ConferencePreset(
        id="corl",
        name="Conference on Robot Learning",
        abbr="CoRL",
        note="机器人学习",
        openalex_source_id=None,
    ),
    "robotics_rss": ConferencePreset(
        id="robotics_rss",
        name="Robotics: Science and Systems",
        abbr="RSS",
        note="机器人学；id 用 robotics_rss 避免与 RSS 订阅混淆",
        openalex_source_id=None,
    ),
    "icra": ConferencePreset(
        id="icra",
        name="IEEE International Conference on Robotics and Automation",
        abbr="ICRA",
        note="机器人与自动化",
        openalex_source_id=None,
    ),
    "iros": ConferencePreset(
        id="iros",
        name="IEEE/RSJ International Conference on Intelligent Robots and Systems",
        abbr="IROS",
        note="智能机器人与系统",
        openalex_source_id=None,
    ),
    "cikm": ConferencePreset(
        id="cikm",
        name="ACM International Conference on Information and Knowledge Management",
        abbr="CIKM",
        note="信息检索、知识管理与数据挖掘交叉",
        openalex_source_id=None,
    ),
    "wsdm": ConferencePreset(
        id="wsdm",
        name="ACM International Conference on Web Search and Data Mining",
        abbr="WSDM",
        note="网络搜索与数据挖掘",
        openalex_source_id=None,
    ),
    "facct": ConferencePreset(
        id="facct",
        name="ACM Conference on Fairness, Accountability, and Transparency",
        abbr="FAccT",
        note="公平、问责与透明（可信 AI）",
        openalex_source_id=None,
    ),
    "aies": ConferencePreset(
        id="aies",
        name="AAAI/ACM Conference on AI, Ethics, and Society",
        abbr="AIES",
        note="AI 伦理与社会影响",
        openalex_source_id=None,
    ),
    "mm": ConferencePreset(
        id="mm",
        name="ACM International Conference on Multimedia",
        abbr="ACM MM",
        note="多媒体与多模态",
        openalex_source_id=None,
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


def user_subscription_keywords_csv(user) -> str:
    """推荐 / 每日精选统一用：订阅 JSON 优先，否则旧版 keywords CSV。"""
    raw = getattr(user, "subscription_keywords_json", None) or "[]"
    if not isinstance(raw, str):
        raw = "[]"
    s = keywords_csv_from_subscription_json(raw)
    if s.strip():
        return s
    legacy = getattr(user, "keywords", None) or ""
    return legacy.strip() if isinstance(legacy, str) else ""


def _enabled_keyword_texts_from_subscription_json(json_str: str) -> list[str]:
    try:
        arr = json.loads(json_str or "[]")
    except json.JSONDecodeError:
        return []
    if not isinstance(arr, list):
        return []
    parts: list[str] = []
    for x in arr:
        if not isinstance(x, dict):
            continue
        if not x.get("enabled", True):
            continue
        t = (x.get("text") or "").strip()
        if t:
            parts.append(t)
    return parts


def keywords_csv_from_subscription_json(json_str: str) -> str:
    return ",".join(_enabled_keyword_texts_from_subscription_json(json_str))


def user_subscription_keywords_list(user) -> list[str]:
    """与 feed / 每日精选筛选一致：已启用的订阅关键词（顺序与订阅 JSON 相同）。"""
    raw = getattr(user, "subscription_keywords_json", None) or "[]"
    if not isinstance(raw, str):
        raw = "[]"
    lst = _enabled_keyword_texts_from_subscription_json(raw)
    if lst:
        return lst
    legacy = getattr(user, "keywords", None) or ""
    if isinstance(legacy, str) and legacy.strip():
        return [p.strip() for p in legacy.split(",") if p.strip()]
    return []
