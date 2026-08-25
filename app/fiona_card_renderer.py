from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageDraw, ImageFont

from app.design_tokens import FIONA_IOS_TOKENS, FIONA_TOKENS, FionaDesignTokens
from app.fiona_card_components import (
    FONT_BOLD,
    FONT_DIR,
    FONT_REGULAR,
    BrandSignatureComponent,
    CardComponent,
    ComponentRenderResult,
    EvidenceComponent,
    EvidenceInput,
    FooterComponent,
    HeaderComponent,
    HeaderInput,
    HeatMapComponent,
    HeroJudgmentComponent,
    HeroJudgmentInput,
    HistoricalContextComponent,
    HistoricalContextInput,
    KeyMarketsComponent,
    MarketRegimeComponent,
    MarketRegimeInput,
    NarrativeComponent,
    RenderContext,
    WatchNextComponent,
    WhatChangedComponent,
    avoid_orphan_punctuation,
    change_color as component_change_color,
    direction_color as component_direction_color,
    draw_heat_tile as component_draw_heat_tile,
    draw_section_title as component_draw_section_title,
    draw_text_fit as component_draw_text_fit,
    ellipsize,
    font,
    font_asset_paths,
    font_line_height,
    format_narrative,
    hex_rgb,
    mix,
    rounded_box as component_rounded_box,
    semantic_limit,
    text_width,
    tokenize,
    validate_component_regions,
    validate_font_assets,
    wrap_text_pixels,
)
from app.fiona_market_news_image import (
    ChangedEventView,
    HeatMapView,
    KeyMarketView,
    MarketNewsViewModel,
    NarrativeView,
    market_news_visible_strings,
)
from app.fiona_locale import (
    OutputLocale,
    parse_output_locale,
    require_en_us_output,
    strings_for_locale,
    visible_locale_strings,
)


TOKENS = FIONA_TOKENS
VISUAL_SYSTEM_VERSION = "V3"

# Static compatibility contract retained for V3 visual audits. Rendering uses
# centralized locale resources; these labels remain discoverable to legacy QA.
LEGACY_V3_STATIC_LABELS = (
    "TODAY'S JUDGEMENT",
    "NOT A FORECAST",
)

# Compatibility exports. The source of truth is app.design_tokens.
BACKGROUND = TOKENS.colors.background
SURFACE = TOKENS.colors.surface
ELEVATED = TOKENS.colors.elevated
BORDER = TOKENS.colors.border
PRIMARY_TEXT = TOKENS.colors.primary_text
SECONDARY_TEXT = TOKENS.colors.secondary_text
MUTED_TEXT = TOKENS.colors.muted_text
FIONA_GOLD = TOKENS.colors.brand
POSITIVE = TOKENS.colors.positive
NEGATIVE = TOKENS.colors.negative
NEUTRAL = TOKENS.colors.neutral
RISK = TOKENS.colors.risk
DATA_GRAY = TOKENS.colors.unknown

MARKET_ACCENTS = {
    "us": TOKENS.colors.us,
    "china": TOKENS.colors.china,
    "crypto": TOKENS.colors.crypto,
    "rwa": TOKENS.colors.rwa,
}
COMPONENT_REGIONS = {name: region.as_tuple() for name, region in TOKENS.regions.items()}
TYPOGRAPHY = {
    "product_title": TOKENS.typography.product_title,
    "regime": TOKENS.typography.regime_value,
    "fiona_view": TOKENS.typography.hero_body,
    "section_title": TOKENS.typography.section_title,
    "body": TOKENS.typography.body,
    "metric": TOKENS.typography.market_score,
    "metadata": TOKENS.typography.badge_meta,
}


class JudgmentConfidence(str, Enum):
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


class DataConfidence(str, Enum):
    VERIFIED = "Verified"
    PARTIAL = "Partial"
    LIMITED = "Limited"


class MarketRegime(str, Enum):
    RISK_ON = "Risk On"
    RISK_OFF = "Risk Off"
    NEUTRAL = "Neutral"
    TRANSITION = "Transition"
    UNKNOWN = "Unknown"


class EvidenceLevel(str, Enum):
    VERIFIED = "Verified"
    STRONG = "Strong"
    MODERATE = "Moderate"
    LIMITED = "Limited"


@dataclass(frozen=True)
class ConfidenceLayer:
    judgment: JudgmentConfidence
    data: DataConfidence


@dataclass(frozen=True)
class MarketRegimeAssessment:
    regime: MarketRegime
    reason: str


@dataclass(frozen=True)
class EvidenceAssessment:
    level: EvidenceLevel
    source_count: int
    completeness: int
    critical_missing: tuple[str, ...]


@dataclass(frozen=True)
class HistoricalContextAssessment:
    topic: str
    reference: str


def render_market_news_card(
    view_model: MarketNewsViewModel,
    output_path: str | Path,
    *,
    tokens: FionaDesignTokens = FIONA_TOKENS,
) -> Path:
    validate_font_assets()
    validate_component_regions(tokens)
    locale = parse_output_locale(view_model.output_locale)
    strings = strings_for_locale(locale)
    components = build_market_news_components(view_model)
    if locale == OutputLocale.EN_US:
        require_en_us_output(
            (
                *visible_locale_strings(locale),
                *market_news_visible_strings(view_model),
                *component_visible_strings(view_model),
            )
        )

    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new(
        tokens.canvas.color_mode,
        (tokens.canvas.width, tokens.canvas.height),
        color=tokens.colors.background,
    )
    context = RenderContext(ImageDraw.Draw(image), tokens, strings, locale)
    render_components(components, context)

    image.save(target, format=tokens.canvas.output_format, optimize=True, compress_level=9)
    validate_rendered_card(target, tokens=tokens)
    return target


def render_market_news_card_ios(view_model: MarketNewsViewModel, output_path: str | Path) -> Path:
    """Render the native iOS photo profile directly at 1440 x 1800."""
    return render_market_news_card(view_model, output_path, tokens=FIONA_IOS_TOKENS)


def build_market_news_components(view_model: MarketNewsViewModel) -> tuple[CardComponent, ...]:
    evidence = derive_evidence_level(view_model)
    regime = derive_market_regime(view_model)
    watch_items = tuple(format_watch_variable(item) for item in derive_watch_next(view_model))
    history = derive_historical_context(view_model)
    return (
        HeaderComponent(HeaderInput(generated_at=view_model.generated_at)),
        MarketRegimeComponent(
            MarketRegimeInput(
                label=regime.regime.value,
                reason=regime.reason,
                tone=regime_tone(regime.regime),
            )
        ),
        EvidenceComponent(
            EvidenceInput(
                label=evidence.level.value,
                source_count=evidence.source_count,
                completeness=evidence.completeness,
                tone=evidence_tone(evidence.level),
            )
        ),
        HeroJudgmentComponent(
            HeroJudgmentInput(
                judgment=view_model.fiona_view,
                primary_driver=dominant_driver(view_model),
                next_confirmation=next_confirmation(view_model),
            )
        ),
        HeatMapComponent(tuple(view_model.heat_map)),
        WhatChangedComponent(
            tuple(view_model.what_changed),
            verification=evidence.level.value.upper(),
            verification_tone=evidence_tone(evidence.level),
        ),
        KeyMarketsComponent(tuple(view_model.key_markets)),
        NarrativeComponent(tuple(view_model.current_narrative)),
        WatchNextComponent(watch_items),
        HistoricalContextComponent(HistoricalContextInput(history.topic, history.reference)),
        BrandSignatureComponent(tuple(view_model.telegram_hashtags)),
        FooterComponent(),
    )


def component_visible_strings(view_model: MarketNewsViewModel) -> tuple[str, ...]:
    evidence = derive_evidence_level(view_model)
    regime = derive_market_regime(view_model)
    history = derive_historical_context(view_model)
    return (
        evidence.level.value,
        regime.regime.value,
        regime.reason,
        dominant_driver(view_model),
        next_confirmation(view_model),
        *derive_watch_next(view_model),
        history.topic,
        history.reference,
    )


def render_components(
    components: Iterable[CardComponent],
    context: RenderContext,
) -> tuple[ComponentRenderResult, ...]:
    return tuple(component.render(context) for component in components)


def validate_rendered_card(
    target: Path,
    *,
    tokens: FionaDesignTokens = FIONA_TOKENS,
) -> None:
    if not target.exists() or target.stat().st_size == 0:
        raise RuntimeError("Pillow renderer did not create a PNG.")
    if target.stat().st_size >= tokens.canvas.max_file_size_bytes:
        raise RuntimeError("Pillow renderer created a Market News card above the size limit.")
    with Image.open(target) as rendered:
        if rendered.size != (tokens.canvas.width, tokens.canvas.height):
            raise RuntimeError("Pillow renderer created an invalid Market News card size.")
        if rendered.format != tokens.canvas.output_format:
            raise RuntimeError("Pillow renderer created an invalid Market News card format.")


# Backward-compatible component entry points used by existing tests and local tools.
def draw_header(draw: ImageDraw.ImageDraw, view_model: MarketNewsViewModel) -> None:
    HeaderComponent(HeaderInput(view_model.generated_at)).render(RenderContext(draw, TOKENS))


def draw_evidence_level(draw: ImageDraw.ImageDraw, evidence: EvidenceAssessment) -> None:
    EvidenceComponent(
        EvidenceInput(
            evidence.level.value,
            evidence.source_count,
            evidence.completeness,
            evidence_tone(evidence.level),
        )
    ).render(RenderContext(draw, TOKENS))


def draw_market_regime(draw: ImageDraw.ImageDraw, assessment: MarketRegimeAssessment) -> None:
    MarketRegimeComponent(
        MarketRegimeInput(assessment.regime.value, assessment.reason, regime_tone(assessment.regime))
    ).render(RenderContext(draw, TOKENS))


def draw_fiona_view(draw: ImageDraw.ImageDraw, view_model: MarketNewsViewModel) -> None:
    HeroJudgmentComponent(
        HeroJudgmentInput(
            view_model.fiona_view,
            dominant_driver(view_model),
            next_confirmation(view_model),
        )
    ).render(RenderContext(draw, TOKENS))


def draw_heat_map(draw: ImageDraw.ImageDraw, heat_map: Iterable[HeatMapView]) -> None:
    HeatMapComponent(tuple(heat_map)).render(RenderContext(draw, TOKENS))


def draw_heat_tile(
    draw: ImageDraw.ImageDraw,
    card: HeatMapView,
    x: int,
    y: int,
    width: int,
    height: int,
) -> None:
    component_draw_heat_tile(RenderContext(draw, TOKENS), card, x, y, width, height)


def draw_what_changed(
    draw: ImageDraw.ImageDraw,
    changes: Iterable[ChangedEventView],
    evidence: EvidenceAssessment,
) -> None:
    WhatChangedComponent(
        tuple(changes),
        evidence.level.value.upper(),
        evidence_tone(evidence.level),
    ).render(RenderContext(draw, TOKENS))


def draw_key_markets(draw: ImageDraw.ImageDraw, key_markets: Iterable[KeyMarketView]) -> None:
    KeyMarketsComponent(tuple(key_markets)).render(RenderContext(draw, TOKENS))


def draw_narrative(draw: ImageDraw.ImageDraw, narratives: Iterable[NarrativeView]) -> None:
    NarrativeComponent(tuple(narratives)).render(RenderContext(draw, TOKENS))


def draw_watch_next(draw: ImageDraw.ImageDraw, watch_items: Iterable[str]) -> None:
    WatchNextComponent(tuple(format_watch_variable(item) for item in watch_items)).render(
        RenderContext(draw, TOKENS)
    )


def draw_historical_context(
    draw: ImageDraw.ImageDraw,
    context: HistoricalContextAssessment,
) -> None:
    HistoricalContextComponent(HistoricalContextInput(context.topic, context.reference)).render(
        RenderContext(draw, TOKENS)
    )


def draw_tags(draw: ImageDraw.ImageDraw, hashtags: Iterable[str]) -> None:
    BrandSignatureComponent(tuple(hashtags)).render(RenderContext(draw, TOKENS))


def draw_footer(draw: ImageDraw.ImageDraw) -> None:
    FooterComponent().render(RenderContext(draw, TOKENS))


def derive_confidence(view_model: MarketNewsViewModel) -> ConfidenceLayer:
    data_status = view_model.data_quality.status.lower()
    if data_status == "full":
        data = DataConfidence.VERIFIED
    elif data_status == "partial":
        data = DataConfidence.PARTIAL
    else:
        data = DataConfidence.LIMITED
    scores = [item.confidence for item in view_model.current_narrative if item.confidence is not None]
    average = sum(scores) / len(scores) if scores else 0
    if data == DataConfidence.VERIFIED and average >= 80:
        judgment = JudgmentConfidence.HIGH
    elif data != DataConfidence.LIMITED and average >= 55:
        judgment = JudgmentConfidence.MEDIUM
    else:
        judgment = JudgmentConfidence.LOW
    return ConfidenceLayer(judgment=judgment, data=data)


def derive_evidence_level(view_model: MarketNewsViewModel) -> EvidenceAssessment:
    total_core_fields = 9
    missing = tuple(view_model.data_quality.missing_fields)
    completeness = round(max(0, total_core_fields - len(missing)) / total_core_fields * 100)
    critical_keys = {
        "heat_map.us",
        "heat_map.crypto",
        "key_markets.btc",
        "key_markets.spx",
        "key_markets.us10y",
    }
    critical_missing = tuple(item for item in missing if item in critical_keys)
    source_count = max(0, int(view_model.source_count))

    if view_model.data_quality.status == "Full" and source_count >= 3 and not critical_missing:
        level = EvidenceLevel.VERIFIED
    elif completeness >= 80 and source_count >= 2 and not critical_missing:
        level = EvidenceLevel.STRONG
    elif completeness >= 50 and source_count >= 1 and len(critical_missing) <= 1:
        level = EvidenceLevel.MODERATE
    else:
        level = EvidenceLevel.LIMITED
    return EvidenceAssessment(
        level=level,
        source_count=source_count,
        completeness=completeness,
        critical_missing=critical_missing,
    )


def derive_market_regime(view_model: MarketNewsViewModel) -> MarketRegimeAssessment:
    locale = parse_output_locale(view_model.output_locale)
    cards = [item for item in view_model.heat_map if item.score is not None]
    if len(cards) < 3:
        reason = (
            "Coverage is insufficient for a reliable regime call"
            if locale == OutputLocale.EN_US
            else "有效市场覆盖不足，暂不判断状态"
        )
        return MarketRegimeAssessment(MarketRegime.UNKNOWN, reason)

    scores = [int(item.score) for item in cards if item.score is not None]
    average = sum(scores) / len(scores)
    bullish = sum(item.direction == "Bullish" for item in cards)
    bearish = sum(item.direction == "Bearish" for item in cards)
    spread = max(scores) - min(scores)
    if bearish == 0 and (bullish >= 2 or average >= 62):
        reason = "Risk appetite is aligned across markets" if locale == OutputLocale.EN_US else "多市场风险偏好形成正向共振"
        return MarketRegimeAssessment(MarketRegime.RISK_ON, reason)
    if bullish == 0 and (bearish >= 2 or average <= 38):
        reason = "Broad weakness is compressing risk appetite" if locale == OutputLocale.EN_US else "多市场同步走弱，风险偏好收缩"
        return MarketRegimeAssessment(MarketRegime.RISK_OFF, reason)
    if (bullish and bearish) or spread >= 24:
        reason = "Cross-market signals are diverging" if locale == OutputLocale.EN_US else "市场信号分化，状态仍在切换"
        return MarketRegimeAssessment(MarketRegime.TRANSITION, reason)
    reason = "Cross-market direction is not yet aligned" if locale == OutputLocale.EN_US else "跨市场方向尚未形成一致共振"
    return MarketRegimeAssessment(MarketRegime.NEUTRAL, reason)


def derive_watch_next(view_model: MarketNewsViewModel) -> tuple[str, ...]:
    output: list[str] = []
    seen: set[str] = set()
    for item in view_model.what_changed:
        value = re.sub(r"\s+", " ", item.watch).strip()
        key = value.casefold()
        if not value or key in seen:
            continue
        seen.add(key)
        output.append(value)
        if len(output) == 3:
            break
    if not output:
        output.append(strings_for_locale(view_model.output_locale).waiting_confirmation)
    return tuple(output)


def format_watch_variable(value: str) -> str:
    normalized = re.sub(r"\s+", " ", str(value)).strip()
    lower = normalized.lower()
    if ("美债" in lower or "us10y" in lower or "yield" in lower) and ("美元" in lower or "dxy" in lower):
        return "US10Y / DXY direction"
    if "etf" in lower and ("稳定币" in lower or "stablecoin" in lower):
        return "ETF Flow / Stablecoin supply"
    if "tvl" in lower and any(token in lower for token in ("使用", "成交", "usage", "volume")):
        return "RWA TVL / Usage"
    if "cpi" in lower:
        return "US CPI"
    if "funding" in lower or "资金费率" in lower:
        return "BTC Funding Rate"
    if "dxy" in lower or "美元" in lower:
        return "DXY"
    if "treasury" in lower or "us10y" in lower:
        return "US10Y direction"
    if "etf" in lower:
        return "ETF Flow confirmation"
    if "rwa" in lower or "tvl" in lower:
        return "RWA TVL / Usage"
    if "price" in lower and ("flow" in lower or "volume" in lower):
        return "Price / Flow confirmation"
    return semantic_limit(normalized, 20)


def derive_historical_context(view_model: MarketNewsViewModel) -> HistoricalContextAssessment:
    corpus = " ".join(
        [
            view_model.fiona_view,
            *(f"{item.event} {item.why} {item.watch}" for item in view_model.what_changed),
            *(item.name for item in view_model.current_narrative),
            *(tag.display_name for tag in view_model.tags),
        ]
    ).lower()
    rules = (
        (("liquidity", "流动性", "美元", "dxy"), HistoricalContextAssessment("Liquidity", "Previous liquidity tightening cycle")),
        (("etf", "ibit", "fbtc"), HistoricalContextAssessment("ETF Flow", "Previous ETF inflow period")),
        (("fed", "fomc", "rate", "yield", "利率", "美债", "us10y"), HistoricalContextAssessment("Rates", "Historical Fed tightening phase")),
        (("rwa", "tokenized", "代币化"), HistoricalContextAssessment("RWA", "Previous institutional adoption phase")),
    )
    for keywords, context in rules:
        if any(keyword in corpus for keyword in keywords):
            return context
    return HistoricalContextAssessment("Context", "No comparable pattern selected")


def market_state(heat_map: Iterable[HeatMapView]) -> str:
    cards = [item for item in heat_map if item.score is not None]
    if len(cards) < 2:
        return "Evidence Limited"
    directions = {item.direction for item in cards}
    if len(directions) == 1:
        return next(iter(directions))
    return "Neutral / Fragmented"


def dominant_driver(view_model: MarketNewsViewModel) -> str:
    if view_model.what_changed:
        why = view_model.what_changed[0].why
        lower = why.lower()
        if "rates" in lower or "dollar" in lower or "treasury" in lower:
            return "Rates and dollar transmission"
        if "etf" in lower:
            return "ETF flow persistence"
        if "rwa" in lower or "institutional" in lower:
            return "Institutional capital and usage"
        return semantic_limit(why, 36)
    if view_model.current_narrative:
        return semantic_limit(view_model.current_narrative[0].name, 16)
    if parse_output_locale(view_model.output_locale) == OutputLocale.EN_US:
        return "No new high-value driver"
    return "暂无新增高价值驱动"


def next_confirmation(view_model: MarketNewsViewModel) -> str:
    if view_model.what_changed:
        return format_watch_variable(view_model.what_changed[0].watch)
    return strings_for_locale(view_model.output_locale).waiting_confirmation


def draw_section_title(draw: ImageDraw.ImageDraw, y: int, title: str, meta: str) -> None:
    component_draw_section_title(RenderContext(draw, TOKENS), y, title, meta)


def draw_text_fit(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    text: str,
    selected_font: ImageFont.FreeTypeFont,
    fill: str,
    *,
    max_lines: int,
    line_gap: int = 5,
) -> list[str]:
    return component_draw_text_fit(
        RenderContext(draw, TOKENS),
        box,
        text,
        selected_font,
        fill,
        max_lines=max_lines,
        line_gap=line_gap,
    )


def rounded_box(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    *,
    fill: str,
    outline: str,
    radius: int = 8,
) -> None:
    component_rounded_box(RenderContext(draw, TOKENS), box, fill=fill, outline=outline, radius=radius)


def direction_color(direction: str) -> str:
    return component_direction_color(TOKENS, direction)


def change_color(change: str) -> str:
    return component_change_color(TOKENS, change)


def confidence_color(value: JudgmentConfidence | DataConfidence) -> str:
    if value in {JudgmentConfidence.HIGH, DataConfidence.VERIFIED}:
        return TOKENS.colors.high_confidence
    if value in {JudgmentConfidence.MEDIUM, DataConfidence.PARTIAL}:
        return TOKENS.colors.neutral
    return TOKENS.colors.limited_confidence


def evidence_color(value: EvidenceLevel) -> str:
    return {
        EvidenceLevel.VERIFIED: TOKENS.colors.high_confidence,
        EvidenceLevel.STRONG: TOKENS.colors.strong_confidence,
        EvidenceLevel.MODERATE: TOKENS.colors.neutral,
        EvidenceLevel.LIMITED: TOKENS.colors.limited_confidence,
    }[value]


def regime_color(value: MarketRegime) -> str:
    return {
        MarketRegime.RISK_ON: TOKENS.colors.positive,
        MarketRegime.RISK_OFF: TOKENS.colors.negative,
        MarketRegime.TRANSITION: TOKENS.colors.brand,
        MarketRegime.NEUTRAL: TOKENS.colors.neutral,
        MarketRegime.UNKNOWN: TOKENS.colors.unknown,
    }[value]


def evidence_tone(value: EvidenceLevel) -> str:
    return {
        EvidenceLevel.VERIFIED: "high_confidence",
        EvidenceLevel.STRONG: "strong_confidence",
        EvidenceLevel.MODERATE: "neutral",
        EvidenceLevel.LIMITED: "limited_confidence",
    }[value]


def regime_tone(value: MarketRegime) -> str:
    return {
        MarketRegime.RISK_ON: "positive",
        MarketRegime.RISK_OFF: "negative",
        MarketRegime.TRANSITION: "brand",
        MarketRegime.NEUTRAL: "neutral",
        MarketRegime.UNKNOWN: "unknown",
    }[value]
