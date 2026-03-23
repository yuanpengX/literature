import json
import re
from collections import Counter

_TOKEN = re.compile(r"[\w]+|[\u4e00-\u9fff]")


def tokenize(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN.findall(text or "") if len(t) > 1]


def merge_interest_weights(blob_json: str, text: str, boost: float = 1.0) -> str:
    cur = json.loads(blob_json or "{}")
    if not isinstance(cur, dict):
        cur = {}
    c = Counter({str(k): float(v) for k, v in cur.items()})
    for tok in tokenize(text):
        c[tok] += boost
    # trim to top 200 keys by weight
    top = dict(c.most_common(200))
    return json.dumps(top, ensure_ascii=False)


def interest_match_score(blob_json: str, title: str, abstract: str) -> float:
    weights = json.loads(blob_json or "{}")
    if not isinstance(weights, dict) or not weights:
        return 0.0
    toks = tokenize(f"{title} {abstract}")
    if not toks:
        return 0.0
    s = sum(float(weights.get(t, 0) or 0) for t in toks)
    return s / len(toks)
