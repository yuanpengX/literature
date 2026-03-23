"""根据候选池与 collect 统计生成 Feed 空态提示（中文）与机器可读 code。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.schemas import FeedDiagnostics

if TYPE_CHECKING:
    from app.models import UserProfile
    from app.services.feed_blurbs import FeedCollectStats

# 与产品说明一致，固定返回给客户端
FEED_PIPELINE_NOTE_ZH = (
    "服务端顺序：合并多频道候选 → 仅保留标题或摘要命中已启用订阅关键词的论文 → 再按当前 Tab 频道过滤 → "
    "按所选排序排好序 → 最后才同步调用您配置的大模型生成卡片中文摘要（无摘要的条目不返回，后台补全后下刷可见）。"
)


def build_feed_diagnostics(
    merged_n: int,
    filtered_n: int,
    papers_n: int,
    ordered_n: int,
    stats: FeedCollectStats | None,
) -> FeedDiagnostics:
    return FeedDiagnostics(
        merged_count=merged_n,
        filtered_count=filtered_n,
        channel_count=papers_n,
        ordered_count=ordered_n,
        collect_batches=stats.batches_processed if stats else 0,
        collect_batches_no_blurb=stats.batches_zero_blurb_yield if stats else 0,
    )


def hint_for_no_llm(user_id: str, user: UserProfile | None) -> tuple[str, str]:
    if user_id == "anonymous":
        return (
            "anonymous",
            "当前请求未携带有效登录态，服务器无法读取您的大模型配置。请使用微信登录或 App 登录后再打开推荐。",
        )
    missing: list[str] = []
    if user is None:
        missing.append("用户资料未初始化")
    else:
        if not (user.llm_base_url or "").strip():
            missing.append("缺少大模型接口根地址")
        if not (user.llm_api_key or "").strip():
            missing.append("缺少 API Key")
        if not (user.llm_model or "").strip():
            missing.append("缺少模型 ID")
    detail = "、".join(missing) if missing else "配置不完整"
    return (
        "no_llm_config",
        f"{detail}。请在设置中填写 OpenAI 兼容接口地址、密钥与模型，保存以同步到服务器，然后下拉刷新本页。",
    )


def hint_for_zero_ordered(
    merged_n: int,
    filtered_n: int,
    papers_n: int,
    channel_label: str,
    subscription_keywords_enabled_count: int,
) -> tuple[str, str]:
    if merged_n <= 0:
        return (
            "pool_empty",
            "近期库内合并候选为 0（各频道在上限内没有可用论文）。请稍后下拉刷新触发抓取，或在「订阅配置」中增加关键词、期刊与会议后再下拉。",
        )
    if filtered_n <= 0:
        if subscription_keywords_enabled_count <= 0:
            return (
                "no_subscription_keywords",
                f"合并候选共 {merged_n} 篇，但您尚未在订阅中启用任何关键词；推荐列表只展示标题或摘要命中已启用关键词的论文。"
                "请到「订阅配置」启用至少一个关键词后再下拉刷新。",
            )
        return (
            "subscription_filtered_empty",
            f"合并候选共 {merged_n} 篇，但没有任何一篇在标题或摘要中命中您已启用的订阅关键词。"
            "请增加或调整关键词，或稍后下拉刷新以拉取更多文献后再试。",
        )
    if papers_n <= 0:
        return (
            "channel_empty",
            f"预筛后仍有 {filtered_n} 篇，但当前「{channel_label}」频道下没有论文。请切换频道、调整订阅以覆盖该频道，或等待后台抓取该来源。",
        )
    return (
        "ordered_empty",
        "内部异常：频道内有论文但排序后列表为空。请重试或反馈服务端日志。",
    )


def hint_after_collect(
    ordered_n: int,
    page_n: int,
    incomplete: bool,
    stats: FeedCollectStats,
) -> tuple[str, str]:
    if page_n > 0:
        if incomplete:
            return (
                "ok_partial_incomplete",
                "本次在时间预算内只来得及生成部分卡片摘要，其余条目后台仍在写入，请稍后下拉刷新。",
            )
        return "ok", ""

    if ordered_n <= 0:
        return "ok", ""

    if incomplete:
        return (
            "blurb_wall_timeout",
            "同步时间预算内未能为排在前面的候选全部生成中文摘要，后台会继续补全。请稍后下拉刷新；若长时间仍为空，请检查大模型接口是否过慢、超时或被限流。",
        )

    bp, bz = stats.batches_processed, stats.batches_zero_blurb_yield
    if bp > 0 and bz == bp:
        return (
            "blurb_llm_fail",
            f"已有 {ordered_n} 篇按相关性排好序的候选，但本次请求内共 {bp} 批大模型调用均未得到任何有效摘要。"
            "请核对接口地址、密钥、模型 ID 与网络；也可查看服务端日志中的 feed_blurbs 相关 WARNING。",
        )

    return (
        "blurb_exhausted",
        f"有 {ordered_n} 篇候选，但在单次请求允许的扫描范围内仍凑不够带摘要的条目（已处理 {bp} 批，其中 {bz} 批未产出摘要）。"
        "请下拉刷新；若频繁出现，可适当调大 FEED_LLM_ENSURE_MAX_SCAN_MULTIPLIER 或检查模型稳定性。",
    )
