from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone

from app.config import MARKET_TITLES
from app.models import MarketReport, NewsItem


def build_report(market: str, items: list[NewsItem], limit: int = 18) -> MarketReport:
    now = datetime.now(timezone.utc)
    selected = [item for item in items if item.market == market][:limit]
    title = MARKET_TITLES.get(market, market)
    return MarketReport(
        market=market,
        title=title,
        generated_at=now,
        items=selected,
        briefing=briefing_for(market, selected),
        advice=advice_for(market, selected),
        risk_flags=risk_flags_for(selected),
    )


def briefing_for(market: str, items: list[NewsItem]) -> str:
    if not items:
        return "本小时未抓取到足够的有效新闻。请检查数据源连通性，或补充授权资讯源。"
    priority_counts = Counter(item.priority for item in items)
    top = items[0]
    hot_tags = Counter(tag for item in items for tag in item.tags).most_common(3)
    tag_text = "、".join(tag for tag, _ in hot_tags) or "暂无明显主题"
    return (
        f"本小时共筛出 {len(items)} 条有效动态，"
        f"其中一级/二级关注 {priority_counts['一级关注'] + priority_counts['二级关注']} 条。"
        f"主线集中在 {tag_text}。最高优先级消息来自 {top.source}：{top.title}"
    )


def advice_for(market: str, items: list[NewsItem]) -> str:
    if not items:
        return "建议先修复或补充数据源，再进行交易判断；不要基于空报表行动。"
    risk_count = sum(1 for item in items if item.stance == "偏利空")
    positive_count = sum(1 for item in items if item.stance == "偏利好")
    top_score = items[0].score

    if market == "us_equities":
        base = "美股部分优先观察宏观利率预期、科技权重股和监管变量。"
    elif market == "china_equities":
        base = "中国股市部分优先观察政策兑现、流动性边际变化与核心行业轮动。"
    else:
        base = "加密市场部分优先观察流动性、监管、ETF/稳定币进展与交易所安全事件。"

    if top_score >= 82 or risk_count > positive_count:
        return f"{base} 当前高冲击或偏利空信号较突出，建议降低追涨冲动，等待价格对消息的二次确认。"
    if positive_count > risk_count:
        return f"{base} 偏利好信号占优，但仍建议用成交量、资金流和关键价位确认，不把单条快讯当作充分依据。"
    return f"{base} 当前信号较分散，适合做信息跟踪和仓位复盘，暂不宜过度外推。"


def risk_flags_for(items: list[NewsItem]) -> list[str]:
    flags: list[str] = []
    for item in items[:8]:
        if item.priority in {"一级关注", "二级关注"} and item.stance == "偏利空":
            flags.append(f"{item.source}: {item.title}")
    return flags[:5]

