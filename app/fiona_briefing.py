from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time, timezone
from enum import Enum
from typing import Any, Iterable

from app.fiona_narrative import format_narrative_lines, weekly_narrative_brief
from app.fiona_types import FionaEvent, MarketDirection, NarrativeRecord, NarrativeStatus


DISCLAIMER = "本内容仅供参考，不构成任何投资建议。投资有风险，入市需谨慎。"
DAILY_INTRO = "Hi, investors, I'm your assistant fiona. The following is the market information I just got. Now I'll sort it out for you to check~"
DAILY_DISCLAIMER = "The above content is for your reference. wish you achieve your great ambition~"


class FionaBriefKind(str, Enum):
    MORNING = "morning"
    EVENING = "evening"
    MARKET_NEWS = "market_news"
    DAILY = "daily"
    WEEKLY = "weekly"


@dataclass(frozen=True)
class FionaBriefSchedule:
    kind: FionaBriefKind
    send_time: time
    label: str
    purpose: str


@dataclass(frozen=True)
class FionaBriefSection:
    title: str
    lines: list[str]


@dataclass
class FionaBrief:
    kind: FionaBriefKind
    title: str
    generated_at: datetime
    sections: list[FionaBriefSection]
    fiona_view: str
    linked_event_ids: list[str] = field(default_factory=list)
    linked_narrative_ids: list[str] = field(default_factory=list)
    max_body_chars: int | None = None

    def body_text(self) -> str:
        body = render_sections(self.sections, self.fiona_view)
        if self.max_body_chars:
            return trim_text(body, self.max_body_chars)
        return body

    def render_text(self, include_disclaimer: bool = True) -> str:
        if self.kind == FionaBriefKind.DAILY:
            return self.render_daily_text(include_disclaimer=include_disclaimer)
        lines = [
            self.title,
            f"更新时间：{self.generated_at.strftime('%Y-%m-%d %H:%M')} UTC+8",
            "",
            self.body_text(),
        ]
        if include_disclaimer:
            lines.extend(["", "【Disclaimer】", DISCLAIMER])
        return "\n".join(line for line in lines if line is not None)

    def render_daily_text(self, include_disclaimer: bool = True) -> str:
        lines = [
            self.title,
            f"{self.generated_at.strftime('%Y-%m-%d %H:%M')} UTC+8",
            "",
            DAILY_INTRO,
            "",
            self.body_text(),
        ]
        if include_disclaimer:
            lines.extend(["", "【Disclaimer】", DAILY_DISCLAIMER])
        return "\n".join(line for line in lines if line is not None)


BRIEF_SCHEDULES: dict[FionaBriefKind, FionaBriefSchedule] = {
    FionaBriefKind.MORNING: FionaBriefSchedule(FionaBriefKind.MORNING, time(7, 30), "Fiona Morning", "开盘前筛出昨夜主线和今日关注"),
    FionaBriefKind.EVENING: FionaBriefSchedule(FionaBriefKind.EVENING, time(20, 30), "Fiona Evening", "美股/宏观/ETF/加密进入夜盘前的风险提示"),
    FionaBriefKind.MARKET_NEWS: FionaBriefSchedule(FionaBriefKind.MARKET_NEWS, time(0, 0), "Fiona Market News", "四市场热力图和主叙事复盘"),
    FionaBriefKind.DAILY: FionaBriefSchedule(FionaBriefKind.DAILY, time(22, 30), "Fiona Daily", "当日五件最重要的市场情报"),
    FionaBriefKind.WEEKLY: FionaBriefSchedule(FionaBriefKind.WEEKLY, time(21, 0), "Fiona Weekly", "周度叙事排名、伪叙事观察和下周关注"),
}


def build_morning_brief(
    events: Iterable[FionaEvent],
    narratives: Iterable[NarrativeRecord],
    generated_at: datetime | None = None,
) -> FionaBrief:
    source_events = list(events)
    now = normalize_now(generated_at, source_events)
    event_list = top_events(source_events, limit=5)
    narrative_list = list(narratives)
    top_narrative = first_by_status(narrative_list, NarrativeStatus.CURRENT) or first_by_status(narrative_list, NarrativeStatus.EMERGING)
    top_event = event_list[0] if event_list else None
    sections = [
        FionaBriefSection("昨夜市场", [brief_market_line(top_narrative, top_event)]),
        FionaBriefSection("今日重点", [watch_line(event_list, narrative_list)]),
    ]
    view = concise_view(event_list, narrative_list, "Morning")
    return FionaBrief(
        kind=FionaBriefKind.MORNING,
        title="Fiona Morning",
        generated_at=now,
        sections=sections,
        fiona_view=view,
        linked_event_ids=[event.event_id for event in event_list[:5]],
        linked_narrative_ids=[record.narrative_id for record in narrative_list[:3]],
        max_body_chars=300,
    )


def build_evening_brief(
    events: Iterable[FionaEvent],
    narratives: Iterable[NarrativeRecord],
    generated_at: datetime | None = None,
) -> FionaBrief:
    source_events = list(events)
    now = normalize_now(generated_at, source_events)
    event_list = top_events(source_events, limit=6)
    narrative_list = list(narratives)
    macro = first_category(event_list, {"macro", "regulation"})
    etf = first_category(event_list, {"etf"})
    crypto = first_asset(event_list, {"BTC", "ETH", "SOL"})
    sections = [
        FionaBriefSection("今晚重点", [event_headline(event_list[0]) if event_list else "暂无S/A级新事件，保留观察。"]),
        FionaBriefSection("风险提示", [risk_line(event_list, narrative_list)]),
        FionaBriefSection("ETF / 宏观 / Crypto", [compact_triplet(etf, macro, crypto)]),
    ]
    view = concise_view(event_list, narrative_list, "Evening")
    return FionaBrief(
        kind=FionaBriefKind.EVENING,
        title="Fiona Evening",
        generated_at=now,
        sections=sections,
        fiona_view=view,
        linked_event_ids=[event.event_id for event in event_list[:6]],
        linked_narrative_ids=[record.narrative_id for record in narrative_list[:3]],
        max_body_chars=300,
    )


def build_market_news_brief(
    events: Iterable[FionaEvent],
    narratives: Iterable[NarrativeRecord],
    snapshot: dict[str, Any] | None = None,
    generated_at: datetime | None = None,
) -> FionaBrief:
    source_events = list(events)
    now = normalize_now(generated_at, source_events)
    event_list = top_events(source_events, limit=6)
    narrative_list = list(narratives)
    current = [record for record in narrative_list if record.status == NarrativeStatus.CURRENT][:3]
    sections = [
        FionaBriefSection("Heat Map", heatmap_lines(snapshot) or fallback_heatmap(event_list, narrative_list)),
        FionaBriefSection("美国 / 中国 / Crypto / RWA", market_lines(snapshot, event_list)),
        FionaBriefSection("Current Narrative", format_narrative_lines(current) or ["暂无明确主叙事"]),
    ]
    view = market_news_view(snapshot, event_list, narrative_list)
    return FionaBrief(
        kind=FionaBriefKind.MARKET_NEWS,
        title="Fiona Market News",
        generated_at=now,
        sections=sections,
        fiona_view=view,
        linked_event_ids=[event.event_id for event in event_list[:6]],
        linked_narrative_ids=[record.narrative_id for record in narrative_list[:5]],
    )


def build_daily_brief(
    events: Iterable[FionaEvent],
    narratives: Iterable[NarrativeRecord],
    snapshot: dict[str, Any] | None = None,
    generated_at: datetime | None = None,
) -> FionaBrief:
    source_events = list(events)
    now = normalize_now(generated_at, source_events)
    event_list = top_events(source_events, limit=8)
    narrative_list = list(narratives)
    top_five = [daily_event_line(event) for event in event_list[:5]] or ["暂无足够高价值事件，今日以观察为主。"]
    current = [record for record in narrative_list if record.status == NarrativeStatus.CURRENT][:3]
    emerging = [record for record in narrative_list if record.status == NarrativeStatus.EMERGING][:3]
    sections = [
        FionaBriefSection("Important events", top_five),
        FionaBriefSection("Current Narrative", format_narrative_lines(current) or ["暂无明确主叙事"]),
        FionaBriefSection("Emerging Narrative", format_narrative_lines(emerging) or ["暂无高置信新兴叙事"]),
        FionaBriefSection("Crypto market", crypto_market_lines(snapshot, event_list)),
        FionaBriefSection("Stock market", stock_market_lines(snapshot, event_list)),
        FionaBriefSection("Future note", next_watch_lines(event_list, narrative_list)),
    ]
    return FionaBrief(
        kind=FionaBriefKind.DAILY,
        title="Fiona Daily",
        generated_at=now,
        sections=sections,
        fiona_view=daily_view(event_list, narrative_list),
        linked_event_ids=[event.event_id for event in event_list[:8]],
        linked_narrative_ids=[record.narrative_id for record in narrative_list[:5]],
    )


def build_weekly_brief(
    events: Iterable[FionaEvent],
    narratives: Iterable[NarrativeRecord],
    snapshot: dict[str, Any] | None = None,
    generated_at: datetime | None = None,
) -> FionaBrief:
    source_events = list(events)
    now = normalize_now(generated_at, source_events)
    event_list = top_events(source_events, limit=10)
    narrative_list = list(narratives)
    weekly_lines = weekly_narrative_brief(narrative_list).splitlines()
    sections = [
        FionaBriefSection("本周赢家 / 输家", weekly_winner_loser_lines(snapshot, event_list)),
        FionaBriefSection("Narrative Ranking / False Narrative Watchlist", weekly_lines),
        FionaBriefSection("资金流 / 风险点", weekly_flow_risk_lines(snapshot, event_list, narrative_list)),
        FionaBriefSection("下周关注", next_watch_lines(event_list, narrative_list, limit=4)),
    ]
    return FionaBrief(
        kind=FionaBriefKind.WEEKLY,
        title="Fiona Weekly",
        generated_at=now,
        sections=sections,
        fiona_view=weekly_view(event_list, narrative_list),
        linked_event_ids=[event.event_id for event in event_list[:10]],
        linked_narrative_ids=[record.narrative_id for record in narrative_list[:8]],
    )


def render_sections(sections: list[FionaBriefSection], fiona_view: str) -> str:
    lines: list[str] = []
    for section in sections:
        lines.append(f"【{section.title}】")
        lines.extend(normalize_bullets(section.lines))
    lines.extend(["【Fiona's View】", fiona_view])
    return "\n".join(lines)


def normalize_bullets(lines: list[str]) -> list[str]:
    normalized = []
    for line in lines:
        stripped = str(line).strip()
        if not stripped:
            continue
        normalized.append(stripped if stripped.startswith(("•", "【")) else f"• {stripped}")
    return normalized


def top_events(events: Iterable[FionaEvent], limit: int) -> list[FionaEvent]:
    return sorted(
        list(events),
        key=lambda event: (event.intelligence_score, event.impact_score, event.urgency_score, event.confidence_score),
        reverse=True,
    )[:limit]


def normalize_now(generated_at: datetime | None, events: Iterable[FionaEvent]) -> datetime:
    if generated_at:
        return ensure_timezone(generated_at)
    event_list = list(events)
    if event_list:
        return ensure_timezone(max(event.created_at for event in event_list))
    return datetime.now(timezone.utc)


def ensure_timezone(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def first_by_status(records: list[NarrativeRecord], status: NarrativeStatus) -> NarrativeRecord | None:
    for record in sorted(records, key=lambda item: item.narrative_score, reverse=True):
        if record.status == status:
            return record
    return None


def first_category(events: list[FionaEvent], categories: set[str]) -> FionaEvent | None:
    for event in events:
        if event.category.value in categories:
            return event
    return None


def first_asset(events: list[FionaEvent], assets: set[str]) -> FionaEvent | None:
    for event in events:
        if {asset.upper() for asset in event.affected_assets} & assets:
            return event
    return None


def event_headline(event: FionaEvent | None) -> str:
    if not event:
        return "暂无关键事件。"
    return f"{event.what_happened or event.title} 影响：{asset_text(event.affected_assets)}。"


def daily_event_line(event: FionaEvent) -> str:
    watch = "；".join(event.watch_next[:2]) or "等待资金和价格确认"
    return f"{event.what_happened or event.title}｜重要性{event.intelligence_score}/100｜关注：{watch}"


def brief_market_line(narrative: NarrativeRecord | None, event: FionaEvent | None) -> str:
    if narrative:
        return f"{narrative.name}是当前主线，方向{narrative.direction.value}，情报值{narrative.narrative_score}/100。"
    if event:
        return f"{event.what_happened or event.title}，影响{asset_text(event.affected_assets)}。"
    return "暂无足够高价值隔夜事件。"


def watch_line(events: list[FionaEvent], narratives: list[NarrativeRecord]) -> str:
    points = []
    for event in events:
        points.extend(event.watch_next[:1])
    if not points and narratives:
        points.append(f"{narratives[0].name}是否获得资金确认")
    return "；".join(unique(points)[:3]) or "等待新的资金、宏观或监管信号。"


def risk_line(events: list[FionaEvent], narratives: list[NarrativeRecord]) -> str:
    bearish = [event for event in events if event.market_direction == MarketDirection.BEARISH]
    false_records = [record for record in narratives if record.status == NarrativeStatus.FALSE]
    if bearish:
        return f"{bearish[0].what_happened or bearish[0].title}；若资金流同步转弱，先按风险事件处理。"
    if false_records:
        return f"{false_records[0].name}存在伪叙事风险，热度需要资金确认。"
    return "暂无集中风险，但不把单一标题外推成趋势。"


def compact_triplet(etf: FionaEvent | None, macro: FionaEvent | None, crypto: FionaEvent | None) -> str:
    parts = [
        f"ETF：{short_event(etf)}",
        f"宏观：{short_event(macro)}",
        f"Crypto：{short_event(crypto)}",
    ]
    return "；".join(parts)


def short_event(event: FionaEvent | None) -> str:
    if not event:
        return "暂无高价值新信号"
    return trim_text(event.what_happened or event.title, 34)


def concise_view(events: list[FionaEvent], narratives: list[NarrativeRecord], scope: str) -> str:
    direction = dominant_event_direction(events)
    current = first_by_status(narratives, NarrativeStatus.CURRENT)
    if current:
        return f"{scope}重点是{current.name}能否获得资金确认；当前方向{direction.value}，只做条件观察，不做价格预测。"
    if events:
        return f"{scope}信号以{direction.value}为主，先看资金流和关键事件是否共振，避免被单条消息带节奏。"
    return f"{scope}暂无强信号，保持低频观察，等待资金、宏观或监管变量给出确认。"


def daily_view(events: list[FionaEvent], narratives: list[NarrativeRecord]) -> str:
    current = first_by_status(narratives, NarrativeStatus.CURRENT)
    if current:
        return f"今天市场的核心不是单点涨跌，而是{current.name}是否继续扩散到资金流与跨市场资产。后续只看确认，不做价格预测。"
    if events:
        return "今天事件较多但主线仍需确认，重点看资金流、宏观变量和风险事件是否指向同一方向。"
    return "今天没有形成高价值主线，低频跟踪比追逐噪音更重要。"


def weekly_view(events: list[FionaEvent], narratives: list[NarrativeRecord]) -> str:
    false_count = sum(1 for record in narratives if record.status == NarrativeStatus.FALSE)
    current = first_by_status(narratives, NarrativeStatus.CURRENT)
    if current:
        return f"本周主线是{current.name}，下周重点看资金和政策是否继续确认；同时关注{false_count}条伪叙事风险。"
    return f"本周主线分散，下周先看资金流和宏观数据是否给出方向；伪叙事风险数量：{false_count}。"


def market_news_view(snapshot: dict[str, Any] | None, events: list[FionaEvent], narratives: list[NarrativeRecord]) -> str:
    if snapshot and snapshot.get("wilson_view"):
        return str(snapshot["wilson_view"]).replace("Wilson", "Fiona")[:180]
    return daily_view(events, narratives)


def dominant_event_direction(events: list[FionaEvent]) -> MarketDirection:
    weights = {MarketDirection.BULLISH: 0, MarketDirection.NEUTRAL: 0, MarketDirection.BEARISH: 0}
    for event in events:
        weights[event.market_direction] += max(1, event.intelligence_score)
    return max(weights, key=weights.get) if events else MarketDirection.NEUTRAL


def heatmap_lines(snapshot: dict[str, Any] | None) -> list[str]:
    if not snapshot:
        return []
    lines = []
    for card in snapshot.get("heatmap", []) if isinstance(snapshot.get("heatmap"), list) else []:
        if not isinstance(card, dict):
            continue
        label = str(card.get("label", "Market"))
        score = card.get("score", "-")
        status = card.get("status", "Neutral")
        summary = card.get("summary", "")
        lines.append(f"{label}：{score}/100，{status}，{summary}")
    return lines[:4]


def fallback_heatmap(events: list[FionaEvent], narratives: list[NarrativeRecord]) -> list[str]:
    direction = dominant_event_direction(events)
    score = round(sum(event.intelligence_score for event in events[:5]) / max(1, len(events[:5]))) if events else 50
    top = narratives[0].name if narratives else "暂无明确叙事"
    return [f"Market：{score}/100，{direction.value}，主线：{top}"]


def market_lines(snapshot: dict[str, Any] | None, events: list[FionaEvent]) -> list[str]:
    if snapshot:
        return [
            f"US：{market_primary_line(snapshot.get('us_market'), 'S&P 500')}",
            f"China：{market_primary_line(snapshot.get('china_market'), '中证500')}",
            f"Crypto：{crypto_primary_line(snapshot.get('crypto_market'))}",
            f"RWA：{rwa_primary_line(snapshot.get('rwa_market'))}",
        ]
    return [asset_summary_line(events)]


def market_primary_line(market: Any, fallback_name: str) -> str:
    data = market if isinstance(market, dict) else {}
    primary = data.get("primary") if isinstance(data.get("primary"), dict) else {}
    name = primary.get("name") or fallback_name
    price = primary.get("price")
    change = primary.get("change_pct")
    return f"{name} {format_number(price)}，{format_pct(change)}"


def crypto_primary_line(crypto: Any) -> str:
    data = crypto if isinstance(crypto, dict) else {}
    btc = data.get("btc") if isinstance(data.get("btc"), dict) else {}
    eth = data.get("eth") if isinstance(data.get("eth"), dict) else {}
    return f"BTC {format_number(btc.get('current_price') or btc.get('price'))} / {format_pct(btc.get('price_change_percentage_24h') or btc.get('change_pct'))}；ETH {format_number(eth.get('current_price') or eth.get('price'))}"


def rwa_primary_line(rwa: Any) -> str:
    data = rwa if isinstance(rwa, dict) else {}
    tvl = data.get("tvl") if isinstance(data.get("tvl"), dict) else {}
    market_cap = data.get("market_cap") if isinstance(data.get("market_cap"), dict) else {}
    return f"TVL {format_money(tvl.get('value'))}；MCAP {format_money(market_cap.get('value'))}"


def daily_market_lines(snapshot: dict[str, Any] | None, events: list[FionaEvent]) -> list[str]:
    return crypto_market_lines(snapshot, events) + stock_market_lines(snapshot, events)


def crypto_market_lines(snapshot: dict[str, Any] | None, events: list[FionaEvent]) -> list[str]:
    if not snapshot:
        return [asset_summary_line(events)]
    crypto = snapshot.get("crypto_market") if isinstance(snapshot.get("crypto_market"), dict) else {}
    rwa = snapshot.get("rwa_market") if isinstance(snapshot.get("rwa_market"), dict) else {}
    stable = crypto.get("stablecoin_growth") if isinstance(crypto.get("stablecoin_growth"), dict) else {}
    top100 = crypto.get("top100") if isinstance(crypto.get("top100"), list) else []
    daily_assets = crypto.get("daily_assets") if isinstance(crypto.get("daily_assets"), dict) else {}
    return [
        f"稳定币：{format_money(stable.get('current'))}，24h {format_pct(stable.get('change_1d'))}",
        f"RWA：{rwa_flow_line(rwa)}",
        crypto_asset_flow_line("BTC", crypto_asset_lookup(crypto, top100, daily_assets, "BTC")),
        crypto_asset_flow_line("ETH", crypto_asset_lookup(crypto, top100, daily_assets, "ETH")),
        crypto_asset_flow_line("SOL", crypto_asset_lookup(crypto, top100, daily_assets, "SOL")),
        crypto_asset_flow_line("BNB", crypto_asset_lookup(crypto, top100, daily_assets, "BNB")),
        crypto_asset_flow_line("HYPE", crypto_asset_lookup(crypto, top100, daily_assets, "HYPE")),
        crypto_asset_flow_line("UNI", crypto_asset_lookup(crypto, top100, daily_assets, "UNI")),
    ]


def stock_market_lines(snapshot: dict[str, Any] | None, events: list[FionaEvent]) -> list[str]:
    if not snapshot:
        return [asset_summary_line(events)]
    us = snapshot.get("us_market") if isinstance(snapshot.get("us_market"), dict) else {}
    china = snapshot.get("china_market") if isinstance(snapshot.get("china_market"), dict) else {}
    crypto = snapshot.get("crypto_market") if isinstance(snapshot.get("crypto_market"), dict) else {}
    daily_market = snapshot.get("daily_market") if isinstance(snapshot.get("daily_market"), dict) else {}
    daily_quotes = daily_market.get("quotes") if isinstance(daily_market.get("quotes"), list) else []
    ranking = crypto.get("top100_ranking") if isinstance(crypto.get("top100_ranking"), dict) else {}
    return [
        f"DJI：{quote_brief(find_quote(us.get('indices'), 'DJI', 'Dow Jones'))}",
        f"IXIC：{quote_brief(find_quote(us.get('indices'), 'IXIC', 'Nasdaq'))}",
        f"SPX：{quote_brief(find_quote(us.get('indices'), 'GSPC', 'S&P 500'))}",
        f"HSI：{quote_brief(find_quote(daily_quotes, 'HSI', 'HSI'))}",
        f"000001：{quote_brief(find_quote(china.get('indices'), '000001', '上证指数'))}",
        f"GOLD：{quote_brief(find_quote(daily_quotes, 'GC=F', 'GOLD'))}",
        f"SILVER：{quote_brief(find_quote(daily_quotes, 'SI=F', 'SILVER'))}",
        f"USOIL：{quote_brief(find_quote(daily_quotes, 'CL=F', 'USOIL'))}",
        f"UKOIL：{quote_brief(find_quote(daily_quotes, 'BZ=F', 'UKOIL'))}",
        f"US 涨幅榜：{ranking_line(us.get('top_gainers'))}",
        f"US 跌幅榜：{ranking_line(us.get('top_losers'))}",
        f"US 成交榜：{ranking_line(us.get('top_traded'))}",
        f"CN 涨幅榜：{ranking_line(china.get('top_gainers'))}",
        f"CN 跌幅榜：{ranking_line(china.get('top_losers'))}",
        f"CN 成交榜：{ranking_line(china.get('top_traded'))}",
        f"Crypto 涨幅榜：{ranking_line(ranking.get('gainers'))}",
        f"Crypto 跌幅榜：{ranking_line(ranking.get('losers'))}",
    ]


def rwa_flow_line(rwa: dict[str, Any]) -> str:
    market_cap = rwa.get("market_cap") if isinstance(rwa.get("market_cap"), dict) else {}
    tvl = rwa.get("tvl") if isinstance(rwa.get("tvl"), dict) else {}
    value = market_cap.get("value") or tvl.get("value")
    change = market_cap.get("change_24h")
    if change is None:
        change = tvl.get("change_1d")
    return f"{format_money_or_na(value)}，24h {format_pct_or_na(change)}"


def crypto_asset_lookup(crypto: dict[str, Any], top100: list[Any], daily_assets: dict[str, Any], symbol: str) -> dict[str, Any] | None:
    asset = daily_assets.get(symbol.upper())
    if isinstance(asset, dict):
        return asset
    lowered = symbol.lower()
    direct = crypto.get(lowered)
    if isinstance(direct, dict):
        return direct
    for item in top100:
        if isinstance(item, dict) and str(item.get("symbol", "")).upper() == symbol.upper():
            return item
    return None


def crypto_asset_flow_line(symbol: str, asset: dict[str, Any] | None) -> str:
    if not asset:
        return f"{symbol}：数据暂未返回"
    change = asset.get("change_pct")
    if change is None:
        change = asset.get("price_change_percentage_24h")
    price = asset.get("price")
    if price is None:
        price = asset.get("current_price")
    return (
        f"{symbol}：{format_money_or_na(asset.get('market_cap'))}，24h {format_pct_or_na(change)} "
        f"当前价格 {format_price_or_na(price)}，24h {format_pct_or_na(change)}"
    )


def find_quote(rows: Any, symbol: str, name: str = "") -> dict[str, Any] | None:
    if not isinstance(rows, list):
        return None
    symbol_upper = symbol.upper().replace("^", "")
    name_lower = name.lower()
    for row in rows:
        if not isinstance(row, dict):
            continue
        row_symbol = str(row.get("symbol", "")).upper().replace("^", "")
        row_name = str(row.get("name", "")).lower()
        if row_symbol == symbol_upper or (name_lower and name_lower in row_name):
            return row
    return None


def quote_brief(quote: dict[str, Any] | None) -> str:
    if not quote:
        return "数据暂未返回"
    return f"{format_number_or_na(quote.get('price'))}，24h {format_pct_or_na(quote.get('change_pct'))}"


def weekly_winner_loser_lines(snapshot: dict[str, Any] | None, events: list[FionaEvent]) -> list[str]:
    if snapshot:
        return [
            f"US赢家：{ranking_line((snapshot.get('us_market') or {}).get('top_gainers'))}",
            f"US输家：{ranking_line((snapshot.get('us_market') or {}).get('top_losers'))}",
            f"Crypto赢家：{ranking_line(((snapshot.get('crypto_market') or {}).get('top100_ranking') or {}).get('gainers'))}",
            f"Crypto输家：{ranking_line(((snapshot.get('crypto_market') or {}).get('top100_ranking') or {}).get('losers'))}",
        ]
    return [asset_summary_line(events)]


def weekly_flow_risk_lines(snapshot: dict[str, Any] | None, events: list[FionaEvent], narratives: list[NarrativeRecord]) -> list[str]:
    lines = daily_market_lines(snapshot, events)
    bearish = [event for event in events if event.market_direction == MarketDirection.BEARISH][:2]
    false_records = [record for record in narratives if record.status == NarrativeStatus.FALSE][:2]
    lines.extend([f"风险：{event.what_happened or event.title}" for event in bearish])
    lines.extend([f"伪叙事：{record.name}，{';'.join(record.false_reasons[:2])}" for record in false_records])
    return lines or ["暂无集中风险。"]


def next_watch_lines(events: list[FionaEvent], narratives: list[NarrativeRecord], limit: int = 3) -> list[str]:
    points = []
    for event in events:
        points.extend(event.watch_next)
    for record in narratives:
        if record.status in {NarrativeStatus.CURRENT, NarrativeStatus.EMERGING}:
            points.append(f"{record.name}是否继续获得资金确认")
    return unique(points)[:limit] or ["等待资金流、宏观数据、监管事件三类确认信号。"]


def asset_summary_line(events: list[FionaEvent]) -> str:
    assets = []
    for event in events:
        assets.extend(event.affected_assets)
    return f"影响资产：{asset_text(assets)}"


def asset_text(assets: Iterable[str]) -> str:
    values = unique([asset.upper() for asset in assets if asset])
    return "、".join(values[:8]) if values else "Market"


def ranking_line(rows: Any, limit: int = 3) -> str:
    if not isinstance(rows, list) or not rows:
        return "暂无有效数据"
    output = []
    for row in rows[:limit]:
        if isinstance(row, dict):
            symbol = row.get("symbol") or row.get("code") or row.get("name") or "-"
            change = row.get("change_pct") or row.get("price_change_percentage_24h")
            output.append(f"{symbol} {format_pct(change)}")
        else:
            output.append(str(row))
    return "、".join(output)


def format_number(value: Any) -> str:
    number = safe_float(value)
    if number is None:
        return "-"
    if abs(number) >= 1000:
        return f"{number:,.2f}"
    return f"{number:.2f}"


def format_number_or_na(value: Any) -> str:
    return "数据暂未返回" if safe_float(value) is None else format_number(value)


def format_price_or_na(value: Any) -> str:
    number = safe_float(value)
    if number is None:
        return "数据暂未返回"
    if abs(number) >= 1000:
        return f"${number:,.2f}"
    if abs(number) >= 1:
        return f"${number:.2f}"
    return f"${number:.6f}"


def format_money(value: Any) -> str:
    number = safe_float(value)
    if number is None:
        return "-"
    absolute = abs(number)
    if absolute >= 1_000_000_000_000:
        return f"${number / 1_000_000_000_000:.2f}T"
    if absolute >= 1_000_000_000:
        return f"${number / 1_000_000_000:.2f}B"
    if absolute >= 1_000_000:
        return f"${number / 1_000_000:.2f}M"
    return f"${number:,.0f}"


def format_money_or_na(value: Any) -> str:
    return "数据暂未返回" if safe_float(value) is None else format_money(value)


def format_pct(value: Any) -> str:
    number = safe_float(value)
    if number is None:
        return "-"
    sign = "+" if number > 0 else ""
    return f"{sign}{number:.2f}%"


def format_pct_or_na(value: Any) -> str:
    return "数据暂未返回" if safe_float(value) is None else format_pct(value)


def safe_float(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def unique(values: Iterable[str]) -> list[str]:
    seen = set()
    output = []
    for value in values:
        key = str(value).strip()
        if not key or key in seen:
            continue
        seen.add(key)
        output.append(key)
    return output


def trim_text(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[: max(0, limit - 1)].rstrip() + "…"
