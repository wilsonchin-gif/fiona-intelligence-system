from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time, timezone
from enum import Enum
from typing import Any, Iterable

from app.fiona_types import FionaEvent, MarketDirection, NarrativeRecord, NarrativeStatus


DISCLAIMER = "本内容仅供参考，不构成任何投资建议。投资有风险，入市需谨慎。"
MARKET_NEWS_INTRO = "Hi, I'm Fiona. Here is your 4-hour market snapshot."
MORNING_INTRO = "Good morning, I'm Fiona. Here is what matters before the market gets active."
EVENING_INTRO = "Good evening, I'm Fiona. Here is your night-session risk briefing."
DAILY_INTRO = "Hi, investors, I'm your assistant Fiona.\nThe following is the market information I just collected. I'll sort it out for you."
WEEKLY_INTRO = "Hi, I'm Fiona. Here is your weekly market intelligence summary."
DAILY_DISCLAIMER = "The above content is for your reference only and does not constitute investment advice.\nWish you achieve your great ambition."
MISSING_SUMMARY = "部分数据暂缺，等待下一轮更新。"
FORBIDDEN_TERMS = ("买入", "卖出", "加仓", "减仓", "梭哈", "抄底", "逃顶", "目标价", "必涨", "必跌")
FORBIDDEN_REPLACEMENTS = {
    "买入": "观察",
    "卖出": "回避",
    "加仓": "提高观察权重",
    "减仓": "降低风险暴露",
    "梭哈": "过度集中",
    "抄底": "等待确认",
    "逃顶": "风险控制",
    "目标价": "观察区间",
    "必涨": "上行信号",
    "必跌": "下行风险",
}


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
    intro: str = ""

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
            self.intro,
            "",
            self.body_text(),
        ]
        if include_disclaimer:
            lines.extend(["", "【Disclaimer】", DISCLAIMER])
        return sanitize_output("\n".join(line for line in lines if line is not None))

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
        return sanitize_output("\n".join(line for line in lines if line is not None))


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
        FionaBriefSection("Intelligence Value", compact_intelligence_value_lines(event_list, narrative_list, "Today’s Intelligence Value")),
        FionaBriefSection("Overnight Market", overnight_lines(top_narrative, top_event, event_list)[:1]),
        FionaBriefSection("Today’s Watch", watch_detail_lines(event_list, narrative_list, limit=2)),
        FionaBriefSection("Today’s Key Events", today_key_event_lines(event_list)[:2]),
        FionaBriefSection("What Changed", what_changed_lines(event_list, None, limit=1)),
        FionaBriefSection("Risk Radar", risk_radar_lines(event_list, narrative_list)),
    ]
    view = morning_view(event_list, narrative_list)
    return FionaBrief(
        kind=FionaBriefKind.MORNING,
        title="Fiona Morning",
        generated_at=now,
        sections=sections,
        fiona_view=view,
        linked_event_ids=[event.event_id for event in event_list[:5]],
        linked_narrative_ids=[record.narrative_id for record in narrative_list[:3]],
        max_body_chars=560,
        intro=MORNING_INTRO,
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
        FionaBriefSection("Intelligence Value", compact_intelligence_value_lines(event_list, narrative_list, "Tonight’s Intelligence Value")),
        FionaBriefSection("Tonight’s Focus", evening_focus_lines(event_list)[:2]),
        FionaBriefSection("Night Risk Radar", risk_watch_lines(event_list, narrative_list)[:1]),
        FionaBriefSection("ETF / Macro / Crypto", [compact_triplet(etf, macro, crypto)]),
        FionaBriefSection("What Changed", what_changed_lines(event_list, None, limit=1)),
        FionaBriefSection("What Could Change Tonight", scenario_lines(event_list)[:2]),
    ]
    view = evening_view(event_list, narrative_list)
    return FionaBrief(
        kind=FionaBriefKind.EVENING,
        title="Fiona Evening",
        generated_at=now,
        sections=sections,
        fiona_view=view,
        linked_event_ids=[event.event_id for event in event_list[:6]],
        linked_narrative_ids=[record.narrative_id for record in narrative_list[:3]],
        intro=EVENING_INTRO,
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
        FionaBriefSection("Intelligence Value", intelligence_value_lines(event_list, narrative_list, "4H Intelligence Value")),
        FionaBriefSection("Market Heat Map", heatmap_lines(snapshot) or fallback_heatmap(event_list, narrative_list)),
        FionaBriefSection("Key Markets", market_lines(snapshot, event_list)),
        FionaBriefSection("Current Narrative", narrative_lines(current, empty="暂无高置信主叙事")),
        FionaBriefSection("What Changed", what_changed_lines(event_list, snapshot, limit=3)),
        FionaBriefSection("Market Temperature", market_temperature_lines(snapshot, event_list, narrative_list)),
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
        intro=MARKET_NEWS_INTRO,
    )


def build_daily_brief(
    events: Iterable[FionaEvent],
    narratives: Iterable[NarrativeRecord],
    snapshot: dict[str, Any] | None = None,
    generated_at: datetime | None = None,
) -> FionaBrief:
    source_events = list(events)
    now = normalize_now(generated_at, source_events)
    event_list = meaningful_events(source_events, limit=5)
    narrative_list = list(narratives)
    top_five = [daily_event_line(event) for event in event_list] or ["暂无足够高价值事件，今日以观察为主。"]
    current = [record for record in narrative_list if record.status == NarrativeStatus.CURRENT][:3]
    emerging = [record for record in narrative_list if record.status == NarrativeStatus.EMERGING][:3]
    sections = [
        FionaBriefSection("Today’s Market Pulse", market_pulse_lines(snapshot, event_list, narrative_list)),
        FionaBriefSection("What Changed", what_changed_lines(event_list, snapshot, limit=3)),
        FionaBriefSection("Important Events", top_five),
        FionaBriefSection("Current Narrative", narrative_lines(current, empty="暂无高置信主叙事")),
        FionaBriefSection("Emerging Narrative", narrative_lines(emerging, empty="暂无高置信新兴叙事")),
        FionaBriefSection("Market Movers", market_mover_lines(snapshot)),
        FionaBriefSection("Crypto Dashboard", crypto_market_lines(snapshot, event_list)),
        FionaBriefSection("Global Markets", stock_market_lines(snapshot, event_list, include_movers=False)),
        FionaBriefSection("Next Confirmation", next_watch_lines(event_list, narrative_list)),
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
    sections = [
        FionaBriefSection("Intelligence Value", intelligence_value_lines(event_list, narrative_list, "Weekly Intelligence Value")),
        FionaBriefSection("What Changed", what_changed_lines(event_list, snapshot, limit=4)),
        FionaBriefSection("Weekly Winners", weekly_winner_lines(snapshot)),
        FionaBriefSection("Weekly Losers", weekly_loser_lines(snapshot)),
        FionaBriefSection("Narrative Ranking", weekly_narrative_lines(narrative_list)),
        FionaBriefSection("Capital Flow", weekly_capital_flow_lines(snapshot, event_list)),
        FionaBriefSection("False Narrative Watchlist", false_narrative_lines(narrative_list)),
        FionaBriefSection("Next Week Scenario", next_week_scenario_lines(event_list, narrative_list)),
    ]
    return FionaBrief(
        kind=FionaBriefKind.WEEKLY,
        title="Fiona Weekly",
        generated_at=now,
        sections=sections,
        fiona_view=weekly_view(event_list, narrative_list),
        linked_event_ids=[event.event_id for event in event_list[:10]],
        linked_narrative_ids=[record.narrative_id for record in narrative_list[:8]],
        intro=WEEKLY_INTRO,
    )


def render_sections(sections: list[FionaBriefSection], fiona_view: str) -> str:
    lines: list[str] = []
    for section in sections:
        lines.append(f"【{section.title}】")
        lines.extend(compact_missing_lines(normalize_bullets(section.lines)))
    lines.extend(["【Fiona’s View】", fiona_view])
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


def meaningful_events(events: Iterable[FionaEvent], limit: int) -> list[FionaEvent]:
    ranked = top_events(events, limit=12)
    filtered = [event for event in ranked if event.intelligence_score >= 40 or event.level.value in {"S", "A"}]
    return filtered[:limit]


def intelligence_value_lines(events: list[FionaEvent], narratives: list[NarrativeRecord], label: str) -> list[str]:
    value = intelligence_value(events, narratives)
    confidence = confidence_value(events, narratives)
    return [f"{label}：{value} / 100", f"Current Confidence：{confidence}%"]


def compact_intelligence_value_lines(events: list[FionaEvent], narratives: list[NarrativeRecord], label: str) -> list[str]:
    value = intelligence_value(events, narratives)
    confidence = confidence_value(events, narratives)
    return [f"{label}：{value} / 100｜Confidence：{confidence}%"]


def intelligence_value(events: list[FionaEvent], narratives: list[NarrativeRecord]) -> int:
    if not events and not narratives:
        return 40
    event_score = round(sum(event.intelligence_score for event in events[:5]) / max(1, len(events[:5]))) if events else 45
    narrative_score = max([record.narrative_score for record in narratives[:3]] or [45])
    return clamp(round(event_score * 0.65 + narrative_score * 0.35), 0, 100)


def confidence_value(events: list[FionaEvent], narratives: list[NarrativeRecord]) -> int:
    event_confidence = round(sum(event.confidence_score for event in events[:5]) / max(1, len(events[:5])) * 10) if events else 55
    narrative_confidence = max([record.confidence_score for record in narratives[:3]] or [55])
    return clamp(round(event_confidence * 0.55 + narrative_confidence * 0.45), 0, 100)


def clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, int(value)))


def compact_missing_lines(lines: list[str]) -> list[str]:
    missing_markers = ("暂无有效数据", "数据暂未返回", " -，-", "：-")
    missing_count = sum(1 for line in lines if any(marker in line for marker in missing_markers))
    if missing_count <= 3:
        return lines
    compacted = [line for line in lines if not any(marker in line for marker in missing_markers)]
    compacted.append(f"• {MISSING_SUMMARY}")
    return compacted


def sanitize_output(text: str) -> str:
    output = text
    for term in FORBIDDEN_TERMS:
        output = output.replace(term, FORBIDDEN_REPLACEMENTS.get(term, "观察"))
    return output


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
    watch = event.watch_next[0] if event.watch_next else "观察资金流是否确认"
    return f"{event.what_happened or event.title}｜影响：{asset_text(event.affected_assets)}｜等待：{watch}"


def daily_event_line(event: FionaEvent) -> str:
    watch = "；".join(event.watch_next[:2]) or "等待资金和价格确认"
    return f"{event.what_happened or event.title}｜Importance {event.intelligence_score}/100｜Direction：{event.market_direction.value}｜Watch：等待：{watch}"


def overnight_lines(narrative: NarrativeRecord | None, event: FionaEvent | None, events: list[FionaEvent]) -> list[str]:
    lines = []
    if narrative:
        lines.append(f"{narrative.name}｜Direction：{narrative.direction.value}｜Why：资金与叙事是否同步，是今天风险偏好的关键。")
    if event:
        lines.append(f"{event.what_happened or event.title}｜Why：{event.why_important or '它可能影响相关资产的资金流和风险偏好。'}")
    return unique(lines)[:2] or ["昨夜没有形成高价值主线，先观察资金流是否给出方向。"]


def watch_detail_lines(events: list[FionaEvent], narratives: list[NarrativeRecord], limit: int = 3) -> list[str]:
    points = []
    for event in events:
        watch = event.watch_next[0] if event.watch_next else ""
        why = event.why_important or "它决定市场是否把单点消息扩散成主线。"
        if watch:
            points.append(f"{watch}｜Why：{trim_text(why, 54)}")
    for record in narratives:
        if record.status in {NarrativeStatus.CURRENT, NarrativeStatus.EMERGING}:
            points.append(f"{record.name}是否获得资金确认｜Why：决定叙事能否从热度变成市场主线。")
    return unique(points)[:limit] or ["观察资金流、宏观数据与风险资产是否同向变化｜Why：三者共振才更像有效信号。"]


def risk_radar_lines(events: list[FionaEvent], narratives: list[NarrativeRecord]) -> list[str]:
    bearish = [event for event in events if event.market_direction == MarketDirection.BEARISH]
    false_records = [record for record in narratives if record.status == NarrativeStatus.FALSE]
    level = "High" if any(event.level.value == "S" for event in bearish) else "Medium" if bearish or false_records else "Low"
    source = risk_source(events, false_records)
    return [f"当前主要风险：{level}", f"风险来源：{source}"]


def risk_source(events: list[FionaEvent], false_records: list[NarrativeRecord]) -> str:
    category_map = {
        "macro": "宏观",
        "etf": "ETF",
        "price": "Crypto",
        "risk": "流动性",
        "regulation": "政策",
        "rwa": "RWA",
    }
    sources = [category_map.get(event.category.value, event.category.value) for event in events if event.market_direction == MarketDirection.BEARISH]
    if false_records:
        sources.append("叙事")
    return " / ".join(unique(sources)[:3]) or "暂无集中风险"


def evening_focus_lines(events: list[FionaEvent]) -> list[str]:
    high_value = [event for event in events if event.level.value in {"S", "A"} or event.intelligence_score >= 60]
    if not high_value:
        return ["暂无 S/A 级新事件，重点观察资金流与风险偏好变化"]
    return [event_headline(event) for event in high_value[:3]]


def today_key_event_lines(events: list[FionaEvent]) -> list[str]:
    scheduled = []
    for event in events:
        if event.category.value in {"macro", "regulation", "etf", "risk"} and event.intelligence_score >= 55:
            watch = event.watch_next[0] if event.watch_next else "等待后续数据确认"
            scheduled.append(f"{event.category.value.upper()}｜{event.what_happened or event.title}｜等待：{watch}")
    return unique(scheduled)[:3] or ["暂无重大事件。"]


def risk_watch_lines(events: list[FionaEvent], narratives: list[NarrativeRecord]) -> list[str]:
    risks = []
    for event in events:
        if event.market_direction == MarketDirection.BEARISH:
            watch = event.watch_next[0] if event.watch_next else "观察资金流是否异常"
            risks.append(f"{event.what_happened or event.title}｜等待：{watch}")
    for record in narratives:
        if record.status == NarrativeStatus.FALSE:
            risks.append(f"{record.name}｜等待：热度是否缺少资金跟随")
    return unique(risks)[:3] or ["暂无集中风险，但需观察是否出现资金流异常"]


def scenario_lines(events: list[FionaEvent]) -> list[str]:
    lines = []
    etf_event = first_category(events, {"etf"})
    macro_event = first_category(events, {"macro", "regulation"})
    crypto_event = first_asset(events, {"BTC", "ETH", "SOL"})
    if etf_event:
        lines.append("如果ETF资金恢复净流入，那么Crypto风险偏好可能改善；等待净流入是否连续出现。")
    else:
        lines.append("如果ETF资金继续缺席，那么Crypto反弹更容易停留在价格层面；等待资金确认。")
    if macro_event:
        lines.append("如果美元和美债收益率继续上行，那么风险资产可能继续承压；等待宏观变量是否同向。")
    if crypto_event:
        asset = asset_text(crypto_event.affected_assets[:3])
        lines.append(f"如果{asset}波动扩散到相关资产，那么夜盘风险会升温；等待成交量是否同步放大。")
    return unique(lines)[:3]


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
        f"Macro：{short_event(macro)}",
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


def morning_view(events: list[FionaEvent], narratives: list[NarrativeRecord]) -> str:
    current = first_by_status(narratives, NarrativeStatus.CURRENT) or first_by_status(narratives, NarrativeStatus.EMERGING)
    risk = risk_radar_lines(events, narratives)[0].replace("当前主要风险：", "")
    if current:
        return f"今天先看{current.name}是否获得资金确认。当前风险级别{risk}，关键是宏观变量、ETF资金和核心资产能否同向，否则仍按噪音处理。"
    return f"今天暂无强主线。当前风险级别{risk}，先等资金流、宏观数据和Crypto波动是否同向确认。"


def evening_view(events: list[FionaEvent], narratives: list[NarrativeRecord]) -> str:
    direction = dominant_event_direction(events)
    current = first_by_status(narratives, NarrativeStatus.CURRENT)
    if current:
        return f"夜盘看{current.name}能否继续获得资金确认。当前事件方向偏{direction.value}，只有ETF、宏观和Crypto同向时，信号才更值得保留。"
    return f"夜盘暂无强主线。先看资金流是否异常、宏观标题是否改变风险偏好，以及BTC/ETH波动是否扩散到美股科技和RWA。"


def daily_view(events: list[FionaEvent], narratives: list[NarrativeRecord]) -> str:
    current = first_by_status(narratives, NarrativeStatus.CURRENT)
    direction = dominant_event_direction(events)
    if current:
        return f"本周期市场状态偏{direction.value}，核心驱动是{current.name}能否继续扩散到资金流与跨市场资产。下一周期重点看ETF/稳定币资金、宏观变量和关键资产波动是否同向确认；如果信号分裂，Fiona会把它视为短线噪音，而不是稳定主线。"
    if events:
        return f"本周期事件不少，但市场状态仍偏{direction.value}，主线还没有完全收敛。主要驱动来自宏观、资金流和Crypto波动的相互验证。下一周期重点看这些信号是否同向，如果继续分散，就说明市场仍在等待更高置信确认。"
    return "本周期没有形成高价值主线，市场更像是在等待新变量。下一周期重点观察资金流、宏观数据和风险事件是否出现同向确认。"


def weekly_view(events: list[FionaEvent], narratives: list[NarrativeRecord]) -> str:
    false_count = sum(1 for record in narratives if record.status == NarrativeStatus.FALSE)
    current = first_by_status(narratives, NarrativeStatus.CURRENT)
    if current:
        return f"本周主线集中在{current.name}，但它是否能延续，关键不在热度，而在资金流、政策口径和跨市场资产是否继续确认。下周Fiona会重点观察主线是否扩散到更多资产，同时跟踪{false_count}条伪叙事风险，避免把短期情绪误判成长期方向。"
    return f"本周主线较分散，市场更像是在多个叙事之间切换。下周先看资金流、宏观数据和Crypto风险偏好是否给出一致方向；伪叙事风险数量为{false_count}，热度高但资金弱的主题需要特别过滤。"


def market_news_view(snapshot: dict[str, Any] | None, events: list[FionaEvent], narratives: list[NarrativeRecord]) -> str:
    if snapshot and snapshot.get("wilson_view"):
        base = str(snapshot["wilson_view"]).replace("Wilson", "Fiona")[:120]
        return f"{base} Fiona当前更关注资金流是否确认，而不是单一价格波动。下一轮重点看美股、A股、BTC与RWA是否出现同向变化。"
    return daily_view(events, narratives)


def dominant_event_direction(events: list[FionaEvent]) -> MarketDirection:
    weights = {MarketDirection.BULLISH: 0, MarketDirection.NEUTRAL: 0, MarketDirection.BEARISH: 0}
    for event in events:
        weights[event.market_direction] += max(1, event.intelligence_score)
    return max(weights, key=weights.get) if events else MarketDirection.NEUTRAL


def market_temperature_lines(snapshot: dict[str, Any] | None, events: list[FionaEvent], narratives: list[NarrativeRecord]) -> list[str]:
    temp = market_temperature(snapshot, events, narratives)
    risk = risk_appetite(temp, events)
    liquidity = liquidity_state(snapshot)
    narrative = narrative_strength(narratives)
    return [
        f"Today’s Market Temperature：{temp} / 100",
        f"Risk Appetite：{risk}",
        f"Liquidity：{liquidity}",
        f"Narrative Strength：{narrative}",
        f"Summary：{market_temperature_summary(temp, risk, liquidity, narrative)}",
    ]


def market_pulse_lines(snapshot: dict[str, Any] | None, events: list[FionaEvent], narratives: list[NarrativeRecord]) -> list[str]:
    temp = market_temperature(snapshot, events, narratives)
    return [
        f"Today’s Intelligence Value：{intelligence_value(events, narratives)} / 100",
        f"Market Temperature：{temp} / 100",
        f"Risk Appetite：{risk_appetite(temp, events)}",
        f"Liquidity：{liquidity_state(snapshot)}",
        f"Volatility：{volatility_state(events)}",
        f"Confidence：{confidence_value(events, narratives)}%",
        f"Summary：{market_temperature_summary(temp, risk_appetite(temp, events), liquidity_state(snapshot), narrative_strength(narratives))}",
    ]


def market_temperature(snapshot: dict[str, Any] | None, events: list[FionaEvent], narratives: list[NarrativeRecord]) -> int:
    heatmap_scores = []
    if snapshot and isinstance(snapshot.get("heatmap"), list):
        for card in snapshot.get("heatmap", []):
            if isinstance(card, dict) and safe_float(card.get("score")) is not None:
                heatmap_scores.append(float(card.get("score")))
    heat_score = round(sum(heatmap_scores) / len(heatmap_scores)) if heatmap_scores else 50
    event_score = round(sum(event.intelligence_score for event in events[:5]) / max(1, len(events[:5]))) if events else 45
    narrative_score = max([record.narrative_score for record in narratives[:3]] or [45])
    return clamp(round(heat_score * 0.45 + event_score * 0.35 + narrative_score * 0.20), 0, 100)


def risk_appetite(temp: int, events: list[FionaEvent]) -> str:
    direction = dominant_event_direction(events)
    if direction == MarketDirection.BEARISH and temp < 55:
        return "Low"
    if temp >= 70 and direction != MarketDirection.BEARISH:
        return "High"
    return "Medium"


def liquidity_state(snapshot: dict[str, Any] | None) -> str:
    if not snapshot:
        return "Unknown"
    crypto = snapshot.get("crypto_market") if isinstance(snapshot.get("crypto_market"), dict) else {}
    stable = crypto.get("stablecoin_growth") if isinstance(crypto.get("stablecoin_growth"), dict) else {}
    change = safe_float(stable.get("change_1d"))
    if change is None:
        return "Stable"
    if change > 0.1:
        return "Improving"
    if change < -0.1:
        return "Tightening"
    return "Stable"


def volatility_state(events: list[FionaEvent]) -> str:
    high_urgency = [event for event in events if event.urgency_score >= 8]
    bearish = [event for event in events if event.market_direction == MarketDirection.BEARISH]
    if len(high_urgency) >= 2 or len(bearish) >= 3:
        return "High"
    if high_urgency or bearish:
        return "Medium"
    return "Low"


def narrative_strength(narratives: list[NarrativeRecord]) -> str:
    score = max([record.narrative_score for record in narratives[:3]] or [0])
    if score >= 80:
        return "Strong"
    if score >= 60:
        return "Medium"
    return "Weak"


def market_temperature_summary(temp: int, risk: str, liquidity: str, narrative: str) -> str:
    if temp >= 70 and risk == "High":
        return "当前市场风险偏好较强，但仍需要资金流继续确认。"
    if risk == "Low":
        return "当前市场偏防守，资金和叙事都在等待新的确认信号。"
    if narrative == "Weak":
        return "当前市场属于震荡整理，等待新的确认信号。"
    return f"当前市场温度中性，流动性{liquidity}，主线强度{narrative}。"


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
        lines.append(f"{label}：{score}/100｜{status}｜{summary}")
    return lines[:4]


def fallback_heatmap(events: list[FionaEvent], narratives: list[NarrativeRecord]) -> list[str]:
    direction = dominant_event_direction(events)
    score = round(sum(event.intelligence_score for event in events[:5]) / max(1, len(events[:5]))) if events else 50
    top = narratives[0].name if narratives else "暂无明确叙事"
    return [f"Market：{score}/100｜{direction.value}｜主线：{top}"]


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
    return f"BTC {format_number(btc.get('current_price') or btc.get('price'))}，{format_pct(btc.get('price_change_percentage_24h') or btc.get('change_pct'))}；ETH {format_number(eth.get('current_price') or eth.get('price'))}，{format_pct(eth.get('price_change_percentage_24h') or eth.get('change_pct'))}"


def rwa_primary_line(rwa: Any) -> str:
    data = rwa if isinstance(rwa, dict) else {}
    tvl = data.get("tvl") if isinstance(data.get("tvl"), dict) else {}
    market_cap = data.get("market_cap") if isinstance(data.get("market_cap"), dict) else {}
    volume = data.get("volume") if isinstance(data.get("volume"), dict) else {}
    flow = data.get("capital_flow") if isinstance(data.get("capital_flow"), dict) else {}
    return f"TVL {format_money(tvl.get('value'))}；MCAP {format_money(market_cap.get('value'))}；Flow {format_money(flow.get('value') or volume.get('change_24h'))}"


def narrative_lines(records: list[NarrativeRecord], empty: str) -> list[str]:
    if not records:
        return [empty]
    return [
        f"{record.name}｜Direction：{record.direction.value}｜Conviction：{record.confidence_score}/100"
        for record in records[:3]
    ]


def what_changed_lines(events: list[FionaEvent], snapshot: dict[str, Any] | None, limit: int = 3) -> list[str]:
    lines = []
    for event in events[:limit]:
        watch = event.watch_next[0] if event.watch_next else "观察资金流是否确认"
        lines.append(f"{event.what_happened or event.title}｜Why：{trim_text(event.why_important, 46)}｜等待：{watch}")
    if not lines and snapshot:
        lines.append("本轮主要变化不明显，重点观察下一轮资金流和风险偏好是否给出新方向。")
    return unique(lines)[:limit] or ["暂无新增高价值变化。"]


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
        f"Stablecoin：{format_money(stable.get('current'))} / 24h {format_pct(stable.get('change_1d'))} / 观察点：供给变化是否支持风险偏好",
        f"RWA：{rwa_flow_line(rwa)}",
        crypto_asset_flow_line("BTC", crypto_asset_lookup(crypto, top100, daily_assets, "BTC")),
        crypto_asset_flow_line("ETH", crypto_asset_lookup(crypto, top100, daily_assets, "ETH")),
        crypto_asset_flow_line("SOL", crypto_asset_lookup(crypto, top100, daily_assets, "SOL")),
        crypto_asset_flow_line("BNB", crypto_asset_lookup(crypto, top100, daily_assets, "BNB")),
        crypto_asset_flow_line("HYPE", crypto_asset_lookup(crypto, top100, daily_assets, "HYPE")),
        crypto_asset_flow_line("UNI", crypto_asset_lookup(crypto, top100, daily_assets, "UNI")),
    ]


def stock_market_lines(snapshot: dict[str, Any] | None, events: list[FionaEvent], include_movers: bool = True) -> list[str]:
    if not snapshot:
        return [asset_summary_line(events)]
    us = snapshot.get("us_market") if isinstance(snapshot.get("us_market"), dict) else {}
    china = snapshot.get("china_market") if isinstance(snapshot.get("china_market"), dict) else {}
    daily_market = snapshot.get("daily_market") if isinstance(snapshot.get("daily_market"), dict) else {}
    daily_quotes = daily_market.get("quotes") if isinstance(daily_market.get("quotes"), list) else []
    lines = [
        f"DJI：{quote_brief(find_quote(us.get('indices'), 'DJI', 'Dow Jones'))}",
        f"IXIC：{quote_brief(find_quote(us.get('indices'), 'IXIC', 'Nasdaq'))}",
        f"SPX：{quote_brief(find_quote(us.get('indices'), 'GSPC', 'S&P 500'))}",
        f"HSI：{quote_brief(find_quote(daily_quotes, 'HSI', 'HSI'))}",
        f"SSE / 000001：{quote_brief(find_quote(china.get('indices'), '000001', '上证指数'))}",
        f"GOLD：{quote_brief(find_quote(daily_quotes, 'GC=F', 'GOLD'))}",
        f"SILVER：{quote_brief(find_quote(daily_quotes, 'SI=F', 'SILVER'))}",
        f"USOIL：{quote_brief(find_quote(daily_quotes, 'CL=F', 'USOIL'))}",
        f"UKOIL：{quote_brief(find_quote(daily_quotes, 'BZ=F', 'UKOIL'))}",
    ]
    if include_movers:
        lines.extend(market_mover_lines(snapshot))
    return lines


def market_mover_lines(snapshot: dict[str, Any] | None) -> list[str]:
    if not snapshot:
        return [MISSING_SUMMARY]
    us = snapshot.get("us_market") if isinstance(snapshot.get("us_market"), dict) else {}
    china = snapshot.get("china_market") if isinstance(snapshot.get("china_market"), dict) else {}
    crypto = snapshot.get("crypto_market") if isinstance(snapshot.get("crypto_market"), dict) else {}
    ranking = crypto.get("top100_ranking") if isinstance(crypto.get("top100_ranking"), dict) else {}
    return [
        f"US Gainers：{ranking_line(us.get('top_gainers'), limit=5)}",
        f"US Losers：{ranking_line(us.get('top_losers'), limit=5)}",
        f"US Volume Leaders：{ranking_line(us.get('top_traded'), limit=5)}",
        f"CN Gainers：{ranking_line(china.get('top_gainers'), limit=5)}",
        f"CN Losers：{ranking_line(china.get('top_losers'), limit=5)}",
        f"CN Volume Leaders：{ranking_line(china.get('top_traded'), limit=5)}",
        f"Crypto Gainers：{ranking_line(ranking.get('gainers'), limit=5)}",
        f"Crypto Losers：{ranking_line(ranking.get('losers'), limit=5)}",
    ]


def rwa_flow_line(rwa: dict[str, Any]) -> str:
    market_cap = rwa.get("market_cap") if isinstance(rwa.get("market_cap"), dict) else {}
    tvl = rwa.get("tvl") if isinstance(rwa.get("tvl"), dict) else {}
    value = market_cap.get("value") or tvl.get("value")
    change = market_cap.get("change_24h")
    if change is None:
        change = tvl.get("change_1d")
    volume = rwa.get("volume") if isinstance(rwa.get("volume"), dict) else {}
    flow = rwa.get("capital_flow") if isinstance(rwa.get("capital_flow"), dict) else {}
    return f"TVL/MCAP {format_money_or_na(value)} / Volume {format_money_or_na(volume.get('value'))} / Flow {format_money_or_na(flow.get('value'))} / 24h {format_pct_or_na(change)}"


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
        f"{symbol}：{format_price_or_na(price)} / 市值 {format_money_or_na(asset.get('market_cap'))} / "
        f"24h {format_pct_or_na(change)} / 观察点：资金流与成交是否确认"
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
            f"US Winners：{ranking_line((snapshot.get('us_market') or {}).get('top_gainers'), limit=5)}",
            f"US Losers：{ranking_line((snapshot.get('us_market') or {}).get('top_losers'), limit=5)}",
            f"Crypto Winners：{ranking_line(((snapshot.get('crypto_market') or {}).get('top100_ranking') or {}).get('gainers'), limit=5)}",
            f"Crypto Losers：{ranking_line(((snapshot.get('crypto_market') or {}).get('top100_ranking') or {}).get('losers'), limit=5)}",
        ]
    return [asset_summary_line(events)]


def weekly_winner_lines(snapshot: dict[str, Any] | None) -> list[str]:
    if not snapshot:
        return [MISSING_SUMMARY]
    crypto = snapshot.get("crypto_market") if isinstance(snapshot.get("crypto_market"), dict) else {}
    ranking = crypto.get("top100_ranking") if isinstance(crypto.get("top100_ranking"), dict) else {}
    return [
        f"US Winners：{ranking_line((snapshot.get('us_market') or {}).get('top_gainers'), limit=5)}",
        f"Crypto Winners：{ranking_line(ranking.get('gainers'), limit=5)}",
    ]


def weekly_loser_lines(snapshot: dict[str, Any] | None) -> list[str]:
    if not snapshot:
        return [MISSING_SUMMARY]
    crypto = snapshot.get("crypto_market") if isinstance(snapshot.get("crypto_market"), dict) else {}
    ranking = crypto.get("top100_ranking") if isinstance(crypto.get("top100_ranking"), dict) else {}
    return [
        f"US Losers：{ranking_line((snapshot.get('us_market') or {}).get('top_losers'), limit=5)}",
        f"Crypto Losers：{ranking_line(ranking.get('losers'), limit=5)}",
    ]


def weekly_narrative_lines(narratives: list[NarrativeRecord]) -> list[str]:
    current = [record for record in narratives if record.status == NarrativeStatus.CURRENT][:3]
    emerging = [record for record in narratives if record.status == NarrativeStatus.EMERGING][:3]
    fading = [record for record in narratives if record.status == NarrativeStatus.FADING][:3]
    false_records = [record for record in narratives if record.status == NarrativeStatus.FALSE][:3]
    false_text = []
    for record in false_records:
        reasons = "；".join(record.false_reasons[:3]) or "热度需要资金和持续性确认"
        false_text.append(f"{record.name}｜热度：{record.mention_count}｜资金：{record.funds_score}/100｜持续性：{record.persistence_score}/100｜{reasons}")
    return [
        f"Current Narrative：{narrative_summary(current)}",
        f"Emerging Narrative：{narrative_summary(emerging)}",
        f"Fading Narrative：{narrative_summary(fading)}",
        f"False Narrative Watchlist：{'；'.join(false_text) if false_text else '暂无高置信伪叙事'}",
    ]


def narrative_summary(records: list[NarrativeRecord]) -> str:
    if not records:
        return "暂无高置信叙事"
    return "；".join(
        f"{record.name} / {record.direction.value} / Conviction {record.confidence_score}/100"
        for record in records[:3]
    )


def weekly_flow_risk_lines(snapshot: dict[str, Any] | None, events: list[FionaEvent], narratives: list[NarrativeRecord]) -> list[str]:
    crypto_lines = crypto_market_lines(snapshot, events) if snapshot else []
    lines = [
        line for line in crypto_lines
        if line.startswith(("• Stablecoin", "Stablecoin", "• RWA", "RWA", "• BTC", "BTC", "• ETH", "ETH"))
    ]
    lines.append(f"Major Assets：{asset_summary_line(events).replace('影响资产：', '')}")
    bearish = [event for event in events if event.market_direction == MarketDirection.BEARISH][:2]
    false_records = [record for record in narratives if record.status == NarrativeStatus.FALSE][:2]
    lines.extend([f"Major Risk Events：{event.what_happened or event.title}" for event in bearish])
    lines.extend([f"False Narrative Risk：{record.name}｜{';'.join(record.false_reasons[:2]) or '热度、资金和持续性仍需确认'}" for record in false_records])
    return lines or ["暂无集中风险。"]


def weekly_capital_flow_lines(snapshot: dict[str, Any] | None, events: list[FionaEvent]) -> list[str]:
    if not snapshot:
        return [asset_summary_line(events)]
    crypto_lines = crypto_market_lines(snapshot, events)
    selected = [
        line for line in crypto_lines
        if line.startswith(("Stablecoin", "RWA", "BTC", "ETH"))
    ]
    selected.append(f"Major Assets：{asset_summary_line(events).replace('影响资产：', '')}")
    return selected


def false_narrative_lines(narratives: list[NarrativeRecord]) -> list[str]:
    records = [record for record in narratives if record.status == NarrativeStatus.FALSE][:5]
    if not records:
        return ["暂无高置信伪叙事。"]
    return [
        (
            f"{record.name}｜Heat {record.mention_count}｜Money Flow {record.funds_score}｜"
            f"Persistence {record.persistence_score}｜Confidence {record.confidence_score}｜"
            f"{'；'.join(record.false_reasons[:3]) or '热度较高，但资金和持续性仍需确认。'}"
        )
        for record in records
    ]


def next_week_scenario_lines(events: list[FionaEvent], narratives: list[NarrativeRecord]) -> list[str]:
    direction = dominant_event_direction(events)
    narrative = narrative_strength(narratives)
    if direction == MarketDirection.BEARISH:
        bullish, neutral, bearish = 25, 50, 25
    elif direction == MarketDirection.BULLISH:
        bullish, neutral, bearish = 40, 45, 15
    else:
        bullish, neutral, bearish = 35, 50, 15
    if narrative == "Weak":
        neutral += 5
        bullish -= 3
        bearish -= 2
    return [
        f"Bullish：{bullish}%",
        f"Neutral：{neutral}%",
        f"Bearish：{bearish}%",
        "说明：当前仅代表 Fiona 对市场状态的概率评估，不是预测。",
    ]


def next_watch_lines(events: list[FionaEvent], narratives: list[NarrativeRecord], limit: int = 3) -> list[str]:
    points = []
    for event in events:
        points.extend([f"等待：{point}" for point in event.watch_next])
    for record in narratives:
        if record.status in {NarrativeStatus.CURRENT, NarrativeStatus.EMERGING}:
            points.append(f"等待：{record.name}是否继续获得资金确认")
    return unique(points)[:limit] or ["等待：资金流、宏观数据、监管事件三类确认信号是否同向。"]


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
