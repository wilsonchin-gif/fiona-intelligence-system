from __future__ import annotations

from app.fiona_types import AlertLevel, EventCategory, FionaEvent, LifecycleStatus, PushDecision


LEVEL_RANK = {AlertLevel.B: 1, AlertLevel.A: 2, AlertLevel.S: 3}


def classify_event(event: FionaEvent) -> FionaEvent:
    if is_s_level_hard_trigger(event):
        event.level = AlertLevel.S
    elif is_a_level_hard_trigger(event):
        event.level = AlertLevel.A
    elif event.intelligence_score >= 75 or (event.impact_score >= 7 and event.confidence_score >= 7):
        event.level = AlertLevel.A
    elif event.intelligence_score >= 60 or (event.impact_score >= 6 and event.urgency_score >= 5):
        event.level = AlertLevel.A
    else:
        event.level = AlertLevel.B
    return event


def decide_push(event: FionaEvent, cooling: bool = False, upgraded: bool = False) -> PushDecision:
    if event.lifecycle_status == LifecycleStatus.RESOLVED:
        if event.level == AlertLevel.S or event.intelligence_score >= 75:
            return PushDecision.SEND_NOW
        return PushDecision.BRIEF_POOL
    if event.lifecycle_status == LifecycleStatus.ONGOING and not upgraded:
        return PushDecision.BRIEF_POOL
    if cooling and event.level != AlertLevel.S:
        return PushDecision.SUPPRESS_DUPLICATE
    if event.level in {AlertLevel.S, AlertLevel.A}:
        return PushDecision.SEND_NOW
    return PushDecision.BRIEF_POOL


def is_level_upgrade(previous: AlertLevel, current: AlertLevel) -> bool:
    return LEVEL_RANK[current] > LEVEL_RANK[previous]


def is_s_level_hard_trigger(event: FionaEvent) -> bool:
    data = event.raw_data
    if event.category == EventCategory.PRICE:
        symbol = str(data.get("symbol", "")).upper()
        change_abs = abs(float(data.get("change_pct", 0) or 0))
        return (symbol == "BTC" and change_abs >= 1.5) or (symbol in {"ETH", "SOL"} and change_abs >= 3)
    if event.category == EventCategory.ETF:
        asset = str(data.get("asset", "")).upper()
        net_flow = abs(float(data.get("net_flow_usd", 0) or 0))
        return (asset == "BTC" and net_flow > 100_000_000) or (asset == "ETH" and net_flow > 50_000_000)
    if event.category == EventCategory.MACRO:
        return bool(data.get("fed_rate_related") or data.get("major_macro_data"))
    if event.category in {EventCategory.REGULATION, EventCategory.RISK}:
        return bool(data.get("major_regulatory_action") or data.get("major_risk_event"))
    if event.category == EventCategory.INSTITUTION:
        institution = str(data.get("institution", "")).lower()
        return any(name in institution for name in ("blackrock", "franklin", "microstrategy")) and bool(data.get("major_event", True))
    return False


def is_a_level_hard_trigger(event: FionaEvent) -> bool:
    data = event.raw_data
    if event.category == EventCategory.ETF and abs(float(data.get("net_flow_usd", 0) or 0)) > 0:
        return True
    if event.category in {EventCategory.RWA, EventCategory.ONCHAIN, EventCategory.INSTITUTION}:
        return bool(data.get("notable_update") or data.get("whale_move") or data.get("position_change"))
    return False


def render_alert(event: FionaEvent) -> str:
    assets = "\n".join(event.affected_assets) or "Market"
    watch_next = "\n".join(f"• {item}" for item in event.watch_next) or "• 等待下一轮信号确认"
    return "\n".join(
        [
            "🚨 Fiona Alert",
            "",
            f"【{event.category.value}】",
            "",
            "发生了什么：",
            event.what_happened,
            "",
            "为什么重要：",
            event.why_important,
            "",
            "影响谁：",
            assets,
            "",
            "接下来关注什么：",
            watch_next,
            "",
            "Direction：",
            event.market_direction.value,
            "",
            "Conviction：",
            str(event.conviction_score),
            "",
            "等级：",
            f"{event.level.value}级",
            "",
            "Fiona’s View：",
            event.fiona_view,
        ]
    )
