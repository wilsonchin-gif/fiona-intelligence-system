from __future__ import annotations

from app.fiona_types import EventCategory, FionaEvent, IntelligenceComponents, MarketDirection


STRATEGIC_CATEGORIES = {EventCategory.MACRO, EventCategory.REGULATION, EventCategory.RISK, EventCategory.ETF}
CROSS_MARKET_ASSETS = {"BTC", "ETH", "SOL", "SPY", "QQQ", "DXY", "VIX", "US10Y", "RWA"}


def clamp_int(value: float, minimum: int, maximum: int) -> int:
    return int(max(minimum, min(maximum, round(value))))


def compute_intelligence_score(components: IntelligenceComponents) -> int:
    raw = (
        components.impact_weight
        + components.time_horizon_weight
        + components.narrative_weight
        + components.cross_market_weight
        + components.novelty_weight
        + components.decision_value_weight
        + components.confidence_adjustment
        - components.noise_penalty
        - components.repetition_penalty
    )
    return clamp_int(raw, 1, 100)


def derive_intelligence_components(event: FionaEvent, repeated: bool = False) -> IntelligenceComponents:
    impact_weight = clamp_int(event.impact_score * 2.5, 0, 25)
    time_horizon_weight = time_horizon_weight_for(event)
    narrative_weight = clamp_int(event.raw_data.get("narrative_strength", 0), 0, 20)
    cross_market_weight = cross_market_weight_for(event)
    novelty_weight = 3 if repeated else clamp_int(event.raw_data.get("novelty", 7), 0, 10)
    decision_value_weight = decision_value_weight_for(event)
    confidence_adjustment = clamp_int((event.confidence_score - 6) * 1.25, -5, 5)
    noise_penalty = noise_penalty_for(event)
    repetition_penalty = 12 if repeated else clamp_int(event.raw_data.get("repetition_penalty", 0), 0, 20)
    return IntelligenceComponents(
        impact_weight=impact_weight,
        time_horizon_weight=time_horizon_weight,
        narrative_weight=narrative_weight,
        cross_market_weight=cross_market_weight,
        novelty_weight=novelty_weight,
        decision_value_weight=decision_value_weight,
        confidence_adjustment=confidence_adjustment,
        noise_penalty=noise_penalty,
        repetition_penalty=repetition_penalty,
    )


def score_event(event: FionaEvent, repeated: bool = False) -> FionaEvent:
    components = derive_intelligence_components(event, repeated=repeated)
    event.intelligence_components = components
    event.intelligence_score = compute_intelligence_score(components)
    event.conviction_score = compute_conviction_score(event)
    return event


def time_horizon_weight_for(event: FionaEvent) -> int:
    if event.category in {EventCategory.MACRO, EventCategory.REGULATION}:
        return 15
    if event.category in {EventCategory.ETF, EventCategory.INSTITUTION, EventCategory.RISK}:
        return 12
    if event.category in {EventCategory.RWA, EventCategory.ONCHAIN}:
        return 9
    change_abs = abs(float(event.raw_data.get("change_pct", 0) or 0))
    if event.category == EventCategory.PRICE and change_abs >= 3:
        return 8
    if event.category == EventCategory.PRICE:
        return 5
    return 6


def cross_market_weight_for(event: FionaEvent) -> int:
    assets = {asset.upper() for asset in event.affected_assets}
    base = min(10, max(0, len(assets) * 3))
    if event.category in STRATEGIC_CATEGORIES:
        base += 5
    if assets & CROSS_MARKET_ASSETS and len(assets) >= 2:
        base += 3
    return clamp_int(base, 0, 15)


def decision_value_weight_for(event: FionaEvent) -> int:
    watch_points = [point for point in event.watch_next if point.strip()]
    if not watch_points:
        return 2
    if event.category in STRATEGIC_CATEGORIES:
        return 10
    return clamp_int(4 + len(watch_points) * 2, 0, 10)


def noise_penalty_for(event: FionaEvent) -> int:
    penalty = 0
    if event.category == EventCategory.PRICE and not event.raw_data.get("support_break") and not event.raw_data.get("liquidation_confirmed"):
        penalty += 8
    if event.confidence_score <= 4:
        penalty += 6
    if not event.why_important.strip() or not event.fiona_view.strip():
        penalty += 5
    return clamp_int(penalty, 0, 15)


def compute_conviction_score(event: FionaEvent) -> int:
    signals = event.raw_data.get("signals", {})
    if not isinstance(signals, dict):
        signals = {}
    direction = event.market_direction
    aligned = 0
    total = 0
    for key in ("funds", "macro", "narrative", "price", "risk"):
        value = str(signals.get(key, "")).lower()
        if not value:
            continue
        total += 1
        if signal_matches_direction(value, direction):
            aligned += 1
    if total == 0:
        base = event.confidence_score * 8
    else:
        base = 35 + (aligned / total) * 45 + event.confidence_score * 2
    if event.intelligence_score >= 90:
        base += 5
    if event.market_direction == MarketDirection.NEUTRAL:
        base = min(base, 70)
    return clamp_int(base, 0, 100)


def signal_matches_direction(value: str, direction: MarketDirection) -> bool:
    bullish = {"bullish", "positive", "inflow", "risk_on", "supportive", "up"}
    bearish = {"bearish", "negative", "outflow", "risk_off", "stress", "down"}
    neutral = {"neutral", "mixed", "flat"}
    if direction == MarketDirection.BULLISH:
        return value in bullish
    if direction == MarketDirection.BEARISH:
        return value in bearish
    return value in neutral
