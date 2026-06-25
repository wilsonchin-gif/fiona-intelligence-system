from __future__ import annotations

from app.fiona_types import AlertLevel, EventCategory, FionaEvent, LifecycleStatus, PushDecision


LEVEL_RANK = {AlertLevel.C: 0, AlertLevel.B: 1, AlertLevel.A: 2, AlertLevel.S: 3}
ALERT_CATEGORY_LABELS = {
    EventCategory.PRICE: "Price",
    EventCategory.ETF: "ETF",
    EventCategory.MACRO: "Macro",
    EventCategory.INSTITUTION: "Institution",
    EventCategory.RISK: "Risk",
    EventCategory.ONCHAIN: "On-chain",
    EventCategory.NARRATIVE: "Narrative",
    EventCategory.RWA: "Narrative",
    EventCategory.REGULATION: "Macro",
    EventCategory.OTHER: "Narrative",
}


def classify_event(event: FionaEvent) -> FionaEvent:
    if is_s_level_hard_trigger(event):
        event.level = AlertLevel.S
    elif is_a_level_hard_trigger(event):
        event.level = AlertLevel.A
    elif event.intelligence_score >= 85 or (event.impact_score >= 9 and event.urgency_score >= 8):
        event.level = AlertLevel.S
    elif event.intelligence_score >= 70:
        event.level = AlertLevel.A
    elif event.intelligence_score >= 40:
        event.level = AlertLevel.B
    else:
        event.level = AlertLevel.C
    event.cooldown_minutes = cooldown_minutes_for(event)
    return event


def decide_push(event: FionaEvent, cooling: bool = False, upgraded: bool = False) -> PushDecision:
    if event.level == AlertLevel.C:
        return PushDecision.IGNORE
    if event.lifecycle_status == LifecycleStatus.RESOLVED:
        if event.level == AlertLevel.S or event.intelligence_score >= 75:
            return PushDecision.SEND_NOW
        return PushDecision.BRIEF_POOL
    if event.lifecycle_status == LifecycleStatus.ONGOING and not upgraded:
        return PushDecision.BRIEF_POOL
    if cooling and not upgraded:
        return PushDecision.SUPPRESS_DUPLICATE
    if event.level in {AlertLevel.S, AlertLevel.A}:
        return PushDecision.SEND_NOW
    return PushDecision.BRIEF_POOL


def is_level_upgrade(previous: AlertLevel, current: AlertLevel) -> bool:
    return LEVEL_RANK[current] > LEVEL_RANK[previous]


def is_s_level_hard_trigger(event: FionaEvent) -> bool:
    data = event.raw_data
    if event.category == EventCategory.ETF:
        asset = str(data.get("asset", "")).upper()
        net_flow = abs(float(data.get("net_flow_usd", 0) or 0))
        return (
            (asset == "BTC" and net_flow > 100_000_000)
            or (asset == "ETH" and net_flow > 50_000_000)
            or bool(data.get("three_day_streak"))
            or bool(data.get("thirty_day_extreme"))
        )
    if event.category == EventCategory.MACRO:
        return bool(data.get("fed_rate_related") or data.get("major_macro_data"))
    if event.category in {EventCategory.REGULATION, EventCategory.RISK}:
        return bool(data.get("major_regulatory_action") or data.get("major_risk_event"))
    if event.category == EventCategory.INSTITUTION:
        institution = str(data.get("institution", "")).lower()
        return any(name in institution for name in ("blackrock", "franklin", "microstrategy")) and bool(data.get("major_event", True))
    if event.category == EventCategory.ONCHAIN:
        return bool(data.get("major_onchain_move"))
    return False


def is_a_level_hard_trigger(event: FionaEvent) -> bool:
    data = event.raw_data
    if event.category == EventCategory.PRICE:
        symbol = str(data.get("symbol", "")).upper()
        change_abs = abs(float(data.get("change_pct", 0) or 0))
        return (
            (symbol == "BTC" and change_abs >= 1.5)
            or (symbol == "ETH" and change_abs >= 3)
            or (symbol == "SOL" and change_abs >= 4)
            or (symbol == "SPX" and change_abs >= 2)
            or (symbol == "QQQ" and change_abs >= 2.5)
            or (symbol in {"NVDA", "TSLA"} and change_abs >= 5)
            or (symbol in {"ONDO", "MKR", "ENA"} and change_abs >= 5)
        )
    if event.category == EventCategory.ETF and abs(float(data.get("net_flow_usd", 0) or 0)) > 0:
        return True
    if event.category in {EventCategory.RWA, EventCategory.ONCHAIN, EventCategory.INSTITUTION}:
        return bool(data.get("notable_update") or data.get("whale_move") or data.get("position_change"))
    if event.category == EventCategory.NARRATIVE:
        return (
            float(data.get("narrative_delta", 0) or 0) >= 15
            or float(data.get("narrative_score", 0) or 0) >= 70
            or float(data.get("false_narrative_risk", 0) or 0) > 80
            or int(data.get("brief_appearances", 0) or 0) >= 3
            or bool(data.get("narrative_switch"))
        )
    return False


def render_alert(event: FionaEvent) -> str:
    assets = "\n".join(event.affected_assets) or "Market"
    watch_next = "\n".join(f"• {item}" for item in event.watch_next[:3]) or "• 等待下一轮信号确认"
    return sanitize_alert_text("\n".join(
        [
            "🚨 Fiona Alert",
            "",
            "Category：",
            category_label(event),
            "",
            "Importance：",
            f"{event.intelligence_score} / 100",
            "",
            "Confidence：",
            f"{event.conviction_score}%",
            "",
            "━━━━━━━━━━━━━━",
            "",
            "What Happened",
            event.what_happened,
            "",
            "━━━━━━━━━━━━━━",
            "",
            "Why It Matters",
            event.why_important,
            "",
            "━━━━━━━━━━━━━━",
            "",
            "Affected Assets",
            assets,
            "",
            "━━━━━━━━━━━━━━",
            "",
            "What To Watch",
            watch_next,
            "",
            "━━━━━━━━━━━━━━",
            "",
            "Fiona’s View",
            event.fiona_view,
            "",
            "━━━━━━━━━━━━━━",
            "",
            "Disclaimer：",
            "This content is for informational purposes only and does not constitute investment advice.",
        ]
    ))


def category_label(event: FionaEvent) -> str:
    return ALERT_CATEGORY_LABELS.get(event.category, event.category.value.title())


def cooldown_minutes_for(event: FionaEvent) -> int:
    if event.category == EventCategory.PRICE:
        return 60
    if event.category in {EventCategory.MACRO, EventCategory.REGULATION}:
        return 24 * 60
    if event.category == EventCategory.INSTITUTION:
        return 240
    if event.category == EventCategory.NARRATIVE:
        return 12 * 60
    if event.category == EventCategory.RISK:
        return 24 * 60
    return max(60, event.cooldown_minutes)


def sanitize_alert_text(text: str) -> str:
    replacements = {
        "买入": "观察",
        "卖出": "回避",
        "加仓": "提高观察权重",
        "减仓": "降低风险暴露",
        "目标价": "观察区间",
        "必涨": "上行信号",
        "必跌": "下行风险",
    }
    output = text
    for term, replacement in replacements.items():
        output = output.replace(term, replacement)
    return output
