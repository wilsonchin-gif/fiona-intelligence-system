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
    watch_next = "\n".join(f"• 等待：{normalize_watch_point(item)}" for item in event.watch_next[:3]) or "• 等待：下一轮信号确认"
    return sanitize_alert_text("\n".join(
        [
            f"🚨 Fiona Alert｜{event.level.value}级",
            "",
            "【事件】",
            event.what_happened or event.title,
            "",
            "【为什么重要】",
            event.why_important,
            "",
            "【影响资产】",
            format_affected_assets(event),
            "",
            "【Fiona 判断】",
            f"Category：{category_label(event)}",
            f"Direction：{event.market_direction.value}",
            f"Conviction：{event.conviction_score}%",
            f"Importance：{event.intelligence_score}/100",
            "",
            "【接下来确认】",
            watch_next,
            "",
            "【Fiona’s View】",
            event.fiona_view,
            "",
            "Disclaimer：",
            "This content is for informational purposes only and does not constitute investment advice.",
        ]
    ))


def category_label(event: FionaEvent) -> str:
    return ALERT_CATEGORY_LABELS.get(event.category, event.category.value.title())


def format_affected_assets(event: FionaEvent) -> str:
    assets = [asset.strip().upper() for asset in event.affected_assets if asset.strip()]
    if not assets:
        return "直接：Market\n传导：Risk Assets\n观察：资金流、波动率、成交量"

    direct = assets[0]
    transmission_assets = assets[1:4]
    watch_assets = inferred_watch_assets(event, assets)

    lines = [f"直接：{direct}"]
    if transmission_assets:
        lines.append(f"传导：{'、'.join(transmission_assets)}")
    if watch_assets:
        lines.append(f"观察：{'、'.join(watch_assets)}")
    return "\n".join(lines)


def inferred_watch_assets(event: FionaEvent, assets: list[str]) -> list[str]:
    if event.category == EventCategory.PRICE:
        if "BTC" in assets or "ETH" in assets or "SOL" in assets:
            return unique_assets(["ETF Flow", "Stablecoin", "Liquidation"], assets)
        if "SPX" in assets or "QQQ" in assets:
            return unique_assets(["DXY", "US10Y", "VIX"], assets)
        return unique_assets(["Volume", "Sector Beta", "Risk Appetite"], assets)
    if event.category == EventCategory.ETF:
        return unique_assets(["BTC", "ETH", "Stablecoin", "Crypto Beta"], assets)
    if event.category in {EventCategory.MACRO, EventCategory.REGULATION}:
        return unique_assets(["DXY", "US10Y", "SPX", "QQQ", "BTC"], assets)
    if event.category == EventCategory.INSTITUTION:
        return unique_assets(["ETF Flow", "RWA TVL", "Related Tokens"], assets)
    if event.category == EventCategory.RISK:
        return unique_assets(["Liquidation", "Stablecoin", "Exchange Flow"], assets)
    if event.category == EventCategory.ONCHAIN:
        return unique_assets(["Exchange Flow", "Stablecoin", "DEX Volume"], assets)
    if event.category in {EventCategory.NARRATIVE, EventCategory.RWA, EventCategory.OTHER}:
        return unique_assets(["Narrative Strength", "Capital Flow", "Persistence"], assets)
    return []


def unique_assets(candidates: list[str], existing: list[str]) -> list[str]:
    existing_upper = {item.upper() for item in existing}
    result: list[str] = []
    for item in candidates:
        if item.upper() not in existing_upper and item not in result:
            result.append(item)
    return result[:3]


def normalize_watch_point(point: str) -> str:
    text = point.strip()
    if not text:
        return "下一轮信号确认"
    for prefix in ("等待：", "等待:", "关注：", "关注:", "观察：", "观察:"):
        if text.startswith(prefix):
            return text[len(prefix):].strip() or "下一轮信号确认"
    return text


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
