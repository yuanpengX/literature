"""论文作者展示串：截断 + et al."""


def format_author_line(names: list[str], max_show: int = 5) -> str:
    clean = [str(n).strip() for n in names if n and str(n).strip()]
    if not clean:
        return ""
    if len(clean) <= max_show:
        return ", ".join(clean)
    return ", ".join(clean[:max_show]) + " et al."


def openalex_authors_from_work(w: dict) -> str:
    auth = w.get("authorships") or []
    names: list[str] = []
    for a in auth:
        if not isinstance(a, dict):
            continue
        au = a.get("author") or {}
        if not isinstance(au, dict):
            continue
        dn = (au.get("display_name") or "").strip()
        if dn:
            names.append(dn)
    return format_author_line(names)
