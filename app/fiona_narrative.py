from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable

from app.fiona_scoring import clamp_int
from app.fiona_types import FionaEvent, MarketDirection, NarrativeRecord, NarrativeStatus


@dataclass(frozen=True)
class NarrativeDefinition:
    narrative_id: str
    name: str
    category: str
    assets: tuple[str, ...]
    keywords: tuple[str, ...]


NARRATIVE_LIBRARY: dict[str, NarrativeDefinition] = {
    "ai_valuation_reset": NarrativeDefinition(
        narrative_id="ai_valuation_reset",
        name="AI估值修正",
        category="AI / US Equity",
        assets=("NVDA", "AMD", "TSM", "QQQ", "AI"),
        keywords=("ai", "nvidia", "nvda", "semiconductor", "valuation", "capex", "earnings", "tsm", "amd", "人工智能", "估值", "半导体"),
    ),
    "btc_etf_flow_weakness": NarrativeDefinition(
        narrative_id="btc_etf_flow_weakness",
        name="BTC ETF资金流减弱",
        category="Crypto / ETF",
        assets=("BTC", "IBIT", "FBTC", "GBTC", "ETF"),
        keywords=("btc etf", "bitcoin etf", "ibit", "fbtc", "gbtc", "outflow", "inflow", "资金流", "净流出", "净流入"),
    ),
    "rwa_institutional_adoption": NarrativeDefinition(
        narrative_id="rwa_institutional_adoption",
        name="RWA机构化持续推进",
        category="RWA / Institution",
        assets=("RWA", "ONDO", "MKR", "BUIDL", "USYC"),
        keywords=("rwa", "tokenized", "tokenization", "blackrock", "franklin", "ondo", "buidl", "usyc", "代币化", "机构化"),
    ),
    "meme_short_term_hype": NarrativeDefinition(
        narrative_id="meme_short_term_hype",
        name="短期Meme热点",
        category="Crypto / Meme",
        assets=("DOGE", "SHIB", "PEPE", "MEME"),
        keywords=("meme", "doge", "shib", "pepe", "bonk", "wif", "memecoin", "迷因"),
    ),
    "macro_liquidity_repricing": NarrativeDefinition(
        narrative_id="macro_liquidity_repricing",
        name="宏观流动性重新定价",
        category="Macro",
        assets=("DXY", "US10Y", "SPY", "QQQ", "BTC"),
        keywords=("fed", "cpi", "ppi", "nfp", "gdp", "unemployment", "rate", "yield", "dxy", "美联储", "通胀", "利率", "美元"),
    ),
    "china_policy_flow_watch": NarrativeDefinition(
        narrative_id="china_policy_flow_watch",
        name="中国政策与资金承接",
        category="China / Policy",
        assets=("CSI500", "ASHR", "MCHI", "CNH"),
        keywords=("china", "policy", "pboc", "csrc", "lpr", "rrr", "liquidity", "中国", "政策", "央行", "证监", "流动性", "人民币"),
    ),
}


class NarrativeEngine:
    def __init__(self, library: dict[str, NarrativeDefinition] | None = None) -> None:
        self.library = library or NARRATIVE_LIBRARY

    def build(self, events: Iterable[FionaEvent], now: datetime | None = None, lookback_days: int = 7) -> list[NarrativeRecord]:
        event_list = list(events)
        if not event_list:
            return []
        current_time = now or max(event.created_at for event in event_list)
        window_start = current_time - timedelta(days=lookback_days)
        recent_events = [event for event in event_list if event.created_at >= window_start]
        grouped: dict[str, list[FionaEvent]] = defaultdict(list)
        for event in recent_events:
            for narrative_id in self.infer_narratives(event):
                grouped[narrative_id].append(event)

        records = [self.build_record(narrative_id, items, current_time, lookback_days) for narrative_id, items in grouped.items()]
        records.sort(key=lambda item: (status_rank(item.status), item.narrative_score, item.momentum_score), reverse=True)
        return records

    def infer_narratives(self, event: FionaEvent) -> list[str]:
        explicit = event.raw_data.get("narratives", [])
        if isinstance(explicit, str):
            explicit = [explicit]
        narrative_ids: list[str] = []
        for item in explicit if isinstance(explicit, list) else []:
            narrative_id = self.resolve_narrative_id(str(item))
            if narrative_id and narrative_id not in narrative_ids:
                narrative_ids.append(narrative_id)

        text = " ".join(
            [
                event.title,
                event.what_happened,
                event.why_important,
                event.fiona_view,
                " ".join(event.affected_assets),
            ]
        ).lower()
        for narrative_id, definition in self.library.items():
            if narrative_id in narrative_ids:
                continue
            if any(keyword.lower() in text for keyword in definition.keywords):
                narrative_ids.append(narrative_id)
        if not narrative_ids:
            narrative_ids.append(custom_narrative_id(event))
        return narrative_ids

    def resolve_narrative_id(self, value: str) -> str:
        normalized = slug(value)
        if value in self.library:
            return value
        for narrative_id, definition in self.library.items():
            if value == definition.name or normalized == slug(definition.name):
                return narrative_id
        return normalized

    def build_record(self, narrative_id: str, events: list[FionaEvent], now: datetime, lookback_days: int) -> NarrativeRecord:
        definition = self.library.get(narrative_id) or custom_definition(narrative_id, events)
        first_seen = min(event.created_at for event in events)
        last_seen = max(event.created_at for event in events)
        mention_count = sum(int(event.raw_data.get("mention_count", 1) or 1) for event in events)
        sources = {event.source for event in events}
        assets = sorted({asset.upper() for event in events for asset in event.affected_assets} | set(definition.assets))
        avg_intelligence = sum(event.intelligence_score for event in events) / len(events)
        confidence = sum(event.confidence_score for event in events) / len(events)
        funds_score = average_funds_score(events)
        persistence_score = compute_persistence_score(events, lookback_days)
        momentum_score = compute_momentum_score(events, now)
        cross_market_score = compute_cross_market_score(events, assets)
        direction = dominant_direction(events)
        narrative_score = compute_narrative_score(
            mention_count=mention_count,
            source_count=len(sources),
            asset_count=len(assets),
            avg_intelligence_score=avg_intelligence,
            momentum_score=momentum_score,
            funds_score=funds_score,
            persistence_score=persistence_score,
            cross_market_score=cross_market_score,
        )
        false_reasons = false_narrative_reasons(events, mention_count, funds_score, persistence_score, avg_intelligence)
        status = classify_narrative(narrative_score, false_reasons, last_seen, now)
        return NarrativeRecord(
            narrative_id=narrative_id,
            name=definition.name,
            category=definition.category,
            assets=assets,
            keywords=list(definition.keywords),
            first_seen_at=first_seen,
            last_seen_at=last_seen,
            mention_count=mention_count,
            source_count=len(sources),
            event_count=len(events),
            avg_intelligence_score=avg_intelligence,
            momentum_score=momentum_score,
            confidence_score=clamp_int(confidence * 10, 0, 100),
            narrative_score=narrative_score,
            funds_score=funds_score,
            persistence_score=persistence_score,
            cross_market_score=cross_market_score,
            direction=direction,
            status=status,
            summary=build_narrative_summary(definition.name, status, direction, funds_score, persistence_score),
            false_reasons=false_reasons,
            event_ids=[event.event_id for event in events],
            sources=sources,
        )


def compute_narrative_score(
    mention_count: int,
    source_count: int,
    asset_count: int,
    avg_intelligence_score: float,
    momentum_score: int,
    funds_score: int,
    persistence_score: int,
    cross_market_score: int,
) -> int:
    raw = (
        min(20, mention_count * 4)
        + min(15, source_count * 5)
        + min(10, asset_count * 2)
        + avg_intelligence_score * 0.25
        + momentum_score * 0.15
        + funds_score * 0.1
        + persistence_score * 0.15
        + cross_market_score * 0.1
    )
    return clamp_int(raw, 0, 100)


def classify_narrative(score: int, false_reasons: list[str], last_seen: datetime, now: datetime) -> NarrativeStatus:
    if false_reasons:
        return NarrativeStatus.FALSE
    if now - last_seen > timedelta(days=2):
        return NarrativeStatus.FADING
    if score >= 80:
        return NarrativeStatus.CURRENT
    if score >= 60:
        return NarrativeStatus.EMERGING
    if score >= 40:
        return NarrativeStatus.WATCHLIST
    return NarrativeStatus.FADING


def false_narrative_reasons(events: list[FionaEvent], mention_count: int, funds_score: int, persistence_score: int, avg_intelligence: float) -> list[str]:
    explicit = any(event.raw_data.get("false_narrative_signal") for event in events)
    meme_or_hype = any(event.raw_data.get("meme_or_hype") for event in events) or any("MEME" in {asset.upper() for asset in event.affected_assets} for event in events)
    reasons = []
    if explicit:
        reasons.append("已被上游标记为伪叙事风险")
    if mention_count >= 3 and funds_score < 40:
        reasons.append("热度高但资金确认弱")
    if meme_or_hype and persistence_score < 45:
        reasons.append("持续性不足，容易退化为短期热点")
    if avg_intelligence < 55 and mention_count >= 3:
        reasons.append("情报价值不足以形成主线")
    return reasons


def average_funds_score(events: list[FionaEvent]) -> int:
    values = [funds_score_for(event) for event in events]
    return clamp_int(sum(values) / len(values), 0, 100) if values else 50


def funds_score_for(event: FionaEvent) -> int:
    if "funds_score" in event.raw_data:
        return clamp_int(float(event.raw_data.get("funds_score", 50) or 50), 0, 100)
    funds_signal = str((event.raw_data.get("signals") or {}).get("funds", "")).lower()
    if funds_signal in {"inflow", "positive", "supportive", "risk_on"}:
        return 80
    if funds_signal in {"outflow", "negative", "weak", "risk_off"}:
        return 25
    return 50


def compute_persistence_score(events: list[FionaEvent], lookback_days: int) -> int:
    unique_days = {event.created_at.date() for event in events}
    if not unique_days:
        return 0
    return clamp_int(len(unique_days) / max(1, min(lookback_days, 7)) * 100, 0, 100)


def compute_momentum_score(events: list[FionaEvent], now: datetime) -> int:
    recent = [event for event in events if now - event.created_at <= timedelta(hours=24)]
    if not events:
        return 0
    return clamp_int((len(recent) / len(events)) * 70 + min(30, len(recent) * 5), 0, 100)


def compute_cross_market_score(events: list[FionaEvent], assets: list[str]) -> int:
    categories = {event.category.value for event in events}
    asset_score = min(50, len(set(assets)) * 8)
    category_score = min(50, len(categories) * 16)
    return clamp_int(asset_score + category_score, 0, 100)


def dominant_direction(events: list[FionaEvent]) -> MarketDirection:
    scores = {MarketDirection.BULLISH: 0, MarketDirection.NEUTRAL: 0, MarketDirection.BEARISH: 0}
    for event in events:
        scores[event.market_direction] += max(1, event.intelligence_score)
    return max(scores, key=scores.get)


def build_narrative_summary(name: str, status: NarrativeStatus, direction: MarketDirection, funds_score: int, persistence_score: int) -> str:
    return f"{name}处于{status.value}状态，方向为{direction.value}，资金确认度{funds_score}/100，持续性{persistence_score}/100。"


def daily_narrative_brief(records: list[NarrativeRecord], limit: int = 3) -> str:
    current = [record for record in records if record.status == NarrativeStatus.CURRENT][:limit]
    emerging = [record for record in records if record.status == NarrativeStatus.EMERGING][:limit]
    lines = ["【Current Narrative】"]
    lines.extend(format_narrative_lines(current) or ["暂无明确主叙事"])
    lines.append("【Emerging Narrative】")
    lines.extend(format_narrative_lines(emerging) or ["暂无高置信新兴叙事"])
    return "\n".join(lines)


def weekly_narrative_brief(records: list[NarrativeRecord], limit: int = 5) -> str:
    ranking = sorted(records, key=lambda record: record.narrative_score, reverse=True)[:limit]
    false_watchlist = [record for record in records if record.status == NarrativeStatus.FALSE][:limit]
    lines = ["【Narrative Ranking】"]
    lines.extend(format_narrative_lines(ranking) or ["暂无有效叙事排名"])
    lines.append("【False Narrative Watchlist】")
    if false_watchlist:
        for record in false_watchlist:
            reason = "；".join(record.false_reasons) or "热度与资金/持续性不匹配"
            lines.append(f"• {record.name}：{reason}")
    else:
        lines.append("暂无明显伪叙事")
    return "\n".join(lines)


def format_narrative_lines(records: list[NarrativeRecord]) -> list[str]:
    return [f"• {record.name}：{record.narrative_score}/100，{record.direction.value}" for record in records]


def status_rank(status: NarrativeStatus) -> int:
    order = {
        NarrativeStatus.CURRENT: 5,
        NarrativeStatus.EMERGING: 4,
        NarrativeStatus.WATCHLIST: 3,
        NarrativeStatus.FALSE: 2,
        NarrativeStatus.FADING: 1,
    }
    return order[status]


def custom_definition(narrative_id: str, events: list[FionaEvent]) -> NarrativeDefinition:
    assets = tuple(sorted({asset.upper() for event in events for asset in event.affected_assets}))
    keywords = tuple(sorted({word for event in events for word in tokenize(event.title)[:6]}))
    return NarrativeDefinition(narrative_id=narrative_id, name=narrative_id.replace("_", " ").title(), category="Custom", assets=assets, keywords=keywords)


def custom_narrative_id(event: FionaEvent) -> str:
    asset = event.affected_assets[0].lower() if event.affected_assets else "market"
    return f"custom_{event.category.value}_{slug(asset)}"


def slug(value: str) -> str:
    lowered = value.lower().strip()
    lowered = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "_", lowered)
    return lowered.strip("_") or "narrative"


def tokenize(value: str) -> list[str]:
    return [token for token in re.split(r"\W+", value.lower()) if token]
