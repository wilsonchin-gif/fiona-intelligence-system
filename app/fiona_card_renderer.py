from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageDraw, ImageFont

from app.fiona_market_news_image import (
    DISCLAIMER,
    IMAGE_HEIGHT,
    IMAGE_WIDTH,
    ChangedEventView,
    HeatMapView,
    KeyMarketView,
    MarketNewsViewModel,
    NarrativeView,
)


ROOT = Path(__file__).resolve().parent.parent


def font_asset_paths(root: str | Path) -> tuple[Path, Path]:
    font_dir = Path(root) / "assets" / "fonts"
    return font_dir / "NotoSansSC-Regular.otf", font_dir / "NotoSansSC-Bold.otf"


FONT_REGULAR, FONT_BOLD = font_asset_paths(ROOT)
FONT_DIR = FONT_REGULAR.parent

BACKGROUND = "#08131F"
SURFACE = "#101F2B"
ELEVATED = "#162836"
BORDER = "#294154"
PRIMARY_TEXT = "#F4F7F9"
SECONDARY_TEXT = "#A9B7C2"
MUTED_TEXT = "#718594"
FIONA_GOLD = "#D8AD4A"
POSITIVE = "#4FA989"
NEGATIVE = "#C96A72"
NEUTRAL = "#B59B63"
RISK = "#D08A5B"
DATA_GRAY = "#687C8C"

MARKET_ACCENTS = {
    "us": "#5B8FD9",
    "china": "#C9787E",
    "crypto": "#D8AD4A",
    "rwa": "#4D9A7F",
}

COMPONENT_REGIONS = {
    "header": (0, 0, 1080, 116),
    "market_regime": (0, 116, 1080, 174),
    "fiona_view": (0, 174, 1080, 346),
    "heat_map": (0, 346, 1080, 612),
    "what_changed": (0, 612, 1080, 862),
    "key_markets": (0, 862, 1080, 1024),
    "narrative": (0, 1024, 1080, 1084),
    "watch_next": (0, 1084, 1080, 1178),
    "historical_context": (0, 1178, 1080, 1248),
    "tags": (0, 1248, 1080, 1285),
    "footer": (0, 1285, 1080, 1350),
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


def render_market_news_card(view_model: MarketNewsViewModel, output_path: str | Path) -> Path:
    validate_font_assets()
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (IMAGE_WIDTH, IMAGE_HEIGHT), color=BACKGROUND)
    draw = ImageDraw.Draw(image)
    validate_component_regions()
    confidence = derive_confidence(view_model)
    evidence = derive_evidence_level(view_model)
    regime = derive_market_regime(view_model)
    watch_items = derive_watch_next(view_model)
    historical_context = derive_historical_context(view_model)

    draw_header(draw, view_model)
    draw_evidence_level(draw, evidence)
    draw_market_regime(draw, regime)
    draw_fiona_view(draw, view_model)
    draw_heat_map(draw, view_model.heat_map)
    draw_what_changed(draw, view_model.what_changed, evidence)
    draw_key_markets(draw, view_model.key_markets)
    draw_narrative(draw, view_model.current_narrative)
    draw_watch_next(draw, watch_items)
    draw_historical_context(draw, historical_context)
    draw_tags(draw, view_model.telegram_hashtags)
    draw_footer(draw)

    image.save(target, format="PNG", optimize=True, compress_level=9)
    if not target.exists() or target.stat().st_size == 0:
        raise RuntimeError("Pillow renderer did not create a PNG.")
    with Image.open(target) as rendered:
        if rendered.size != (IMAGE_WIDTH, IMAGE_HEIGHT) or rendered.format != "PNG":
            raise RuntimeError("Pillow renderer created an invalid Market News card.")
    return target


def draw_header(
    draw: ImageDraw.ImageDraw,
    view_model: MarketNewsViewModel,
) -> None:
    draw.rectangle((0, 0, IMAGE_WIDTH, 7), fill=FIONA_GOLD)
    draw.text((48, 20), "FIONA", font=font(21, bold=True), fill=FIONA_GOLD)
    draw.text((48, 45), "Fiona Market News", font=font(44, bold=True), fill=PRIMARY_TEXT)
    draw.text(
        (48, 96),
        view_model.generated_at.strftime("%Y-%m-%d %H:%M UTC+8"),
        font=font(20),
        fill=SECONDARY_TEXT,
    )


def draw_evidence_level(draw: ImageDraw.ImageDraw, evidence: EvidenceAssessment) -> None:
    badge_text = f"EVIDENCE · {evidence.level.value.upper()}"
    badge_width = text_width(draw, badge_text, font(20, bold=True)) + 32
    badge_x = IMAGE_WIDTH - 48 - badge_width
    badge_color = evidence_color(evidence.level)
    rounded_box(draw, (badge_x, 56, IMAGE_WIDTH - 48, 96), fill=mix(BACKGROUND, badge_color, 0.16), outline=badge_color)
    draw.text((badge_x + 16, 64), badge_text, font=font(20, bold=True), fill=badge_color)
    metadata = f"{evidence.source_count} SOURCES · {evidence.completeness}% COVERAGE"
    draw.text((IMAGE_WIDTH - 48, 101), metadata, font=font(15, bold=True), fill=MUTED_TEXT, anchor="ra")


def draw_market_regime(draw: ImageDraw.ImageDraw, assessment: MarketRegimeAssessment) -> None:
    color = regime_color(assessment.regime)
    rounded_box(draw, (48, 124, 1032, 166), fill=mix(SURFACE, color, 0.1), outline=BORDER)
    draw.text((66, 131), "MARKET REGIME", font=font(19, bold=True), fill=SECONDARY_TEXT)
    draw.text((258, 130), assessment.regime.value.upper(), font=font(21, bold=True), fill=color)
    draw_text_fit(
        draw,
        (440, 130, 1008, 158),
        semantic_limit(assessment.reason, 32),
        font(19, bold=True),
        SECONDARY_TEXT,
        max_lines=1,
    )


def draw_fiona_view(
    draw: ImageDraw.ImageDraw,
    view_model: MarketNewsViewModel,
) -> None:
    box = (48, 178, 1032, 340)
    rounded_box(draw, box, fill=ELEVATED, outline="#36566A")
    draw.rounded_rectangle((48, 178, 55, 340), radius=4, fill=FIONA_GOLD)
    draw.text((72, 191), "FIONA'S VIEW", font=font(22, bold=True), fill=FIONA_GOLD)

    driver = dominant_driver(view_model)
    draw_text_fit(draw, (292, 192, 1008, 218), f"Driver · {driver}", font(19, bold=True), SECONDARY_TEXT, max_lines=1)

    judgment = semantic_limit(view_model.fiona_view, 62)
    draw_text_fit(draw, (72, 222, 1008, 298), judgment, font(24, bold=True), PRIMARY_TEXT, max_lines=2, line_gap=0)

    confirmation = next_confirmation(view_model)
    draw_text_fit(
        draw,
        (72, 307, 1008, 333),
        f"Next · {semantic_limit(confirmation, 40)}",
        font(19, bold=True),
        FIONA_GOLD,
        max_lines=1,
    )


def draw_heat_map(draw: ImageDraw.ImageDraw, heat_map: Iterable[HeatMapView]) -> None:
    draw_section_title(draw, 348, "MARKET HEAT MAP", "CROSS-MARKET STATE")
    cards = list(heat_map)[:4]
    while len(cards) < 4:
        cards.append(HeatMapView("", "Unavailable", None, "Unavailable", "Data unavailable"))
    positions = ((48, 378), (546, 378), (48, 486), (546, 486))
    for card, (x, y) in zip(cards, positions):
        draw_heat_tile(draw, card, x, y, 486, 96)


def draw_heat_tile(
    draw: ImageDraw.ImageDraw,
    card: HeatMapView,
    x: int,
    y: int,
    width: int,
    height: int,
) -> None:
    direction = card.direction if card.score is not None else "Awaiting"
    semantic_color = direction_color(direction)
    intensity = 0.08 if card.score is None else 0.08 + min(0.08, abs(card.score - 50) / 625)
    fill = mix(SURFACE, semantic_color, intensity)
    rounded_box(draw, (x, y, x + width, y + height), fill=fill, outline=BORDER)
    accent = MARKET_ACCENTS.get(card.key, DATA_GRAY)
    draw.rounded_rectangle((x, y, x + 5, y + height), radius=3, fill=accent)
    draw.text((x + 22, y + 13), card.label, font=font(21, bold=True), fill=PRIMARY_TEXT)
    score = str(card.score) if card.score is not None else "—"
    draw.text((x + 22, y + 43), score, font=font(43, bold=True), fill=PRIMARY_TEXT)
    if card.score is not None:
        draw.text((x + 94, y + 61), "/100", font=font(20), fill=SECONDARY_TEXT)
    draw.text((x + width - 20, y + 16), direction, font=font(21, bold=True), fill=semantic_color, anchor="ra")
    metric = "Data unavailable" if card.score is None else semantic_limit(card.key_metric, 16)
    draw_text_fit(draw, (x + 150, y + 45, x + width - 20, y + 72), metric, font(20), SECONDARY_TEXT, max_lines=1)
    risk_state = "Unknown"
    risk_color = DATA_GRAY
    draw.text((x + 150, y + 70), f"Risk · {risk_state}", font=font(18, bold=True), fill=risk_color)


def draw_what_changed(
    draw: ImageDraw.ImageDraw,
    changes: Iterable[ChangedEventView],
    evidence: EvidenceAssessment,
) -> None:
    draw_section_title(draw, 604, "WHAT CHANGED", "MATERIAL CHANGE ONLY · MAX 2")
    observations = list(changes)[:2]
    if not observations:
        observations = [
            ChangedEventView(
                event="暂无新增高价值变化。",
                why="现有信号尚未形成新的市场结构。",
                watch="等待资金流与关键资产同步确认。",
            )
        ]
    row_height = 96 if len(observations) == 2 else 112
    gap = 8
    y = 636
    verification = evidence.level.value.upper()
    verification_color = evidence_color(evidence.level)
    for item in observations:
        rounded_box(draw, (48, y, 1032, y + row_height), fill=SURFACE, outline=BORDER)
        draw.text((66, y + 10), verification, font=font(20, bold=True), fill=verification_color)
        headline = semantic_limit(item.event, 36)
        draw_text_fit(draw, (190, y + 8, 1008, y + 38), headline, font(24, bold=True), PRIMARY_TEXT, max_lines=1)
        why = semantic_limit(item.why, 48)
        watch = semantic_limit(item.watch, 40)
        draw_text_fit(draw, (66, y + 42, 1008, y + 69), f"Why · {why}", font(20), SECONDARY_TEXT, max_lines=1)
        draw_text_fit(draw, (66, y + 68, 1008, y + 94), f"Watch · {watch}", font(19, bold=True), POSITIVE, max_lines=1)
        y += row_height + gap


def draw_key_markets(draw: ImageDraw.ImageDraw, key_markets: Iterable[KeyMarketView]) -> None:
    draw_section_title(draw, 852, "KEY MARKETS", "FIVE VERIFICATION ANCHORS")
    markets = list(key_markets)[:5]
    while len(markets) < 5:
        markets.append(KeyMarketView("", "Awaiting", "—", "Data unavailable"))
    gap = 16
    width = (984 - gap * 4) // 5
    for index, item in enumerate(markets):
        x = 48 + index * (width + gap)
        rounded_box(draw, (x, 884, x + width, 1008), fill=SURFACE, outline=BORDER)
        draw_text_fit(draw, (x + 16, 897, x + width - 14, 923), item.label, font(19, bold=True), SECONDARY_TEXT, max_lines=1)
        draw_text_fit(draw, (x + 16, 931, x + width - 14, 968), item.value, font(29, bold=True), PRIMARY_TEXT, max_lines=1)
        draw.text((x + 16, 975), item.change, font=font(19, bold=True), fill=change_color(item.change))


def draw_narrative(draw: ImageDraw.ImageDraw, narratives: Iterable[NarrativeView]) -> None:
    draw_section_title(draw, 1018, "NARRATIVE CONTEXT", "MAX 2")
    items = list(narratives)[:2]
    text = "暂无高置信主叙事" if not items else "  |  ".join(format_narrative(item) for item in items)
    draw_text_fit(draw, (48, 1048, 1032, 1077), text, font(19, bold=True), SECONDARY_TEXT, max_lines=1)


def draw_watch_next(draw: ImageDraw.ImageDraw, watch_items: Iterable[str]) -> None:
    draw_section_title(draw, 1082, "WATCH NEXT", "OBSERVABLE VARIABLES · MAX 3")
    items = list(watch_items)[:3]
    while len(items) < 3:
        items.append("等待下一轮高价值数据确认")
    gap = 12
    width = (984 - gap * 2) // 3
    for index, item in enumerate(items):
        x = 48 + index * (width + gap)
        rounded_box(draw, (x, 1112, x + width, 1166), fill=SURFACE, outline=BORDER)
        draw.text((x + 14, 1120), f"0{index + 1}", font=font(17, bold=True), fill=FIONA_GOLD)
        draw_text_fit(
            draw,
            (x + 48, 1118, x + width - 12, 1156),
            format_watch_variable(item),
            font(18, bold=True),
            PRIMARY_TEXT,
            max_lines=1,
        )


def draw_historical_context(
    draw: ImageDraw.ImageDraw,
    context: HistoricalContextAssessment,
) -> None:
    draw_section_title(draw, 1174, "HISTORICAL CONTEXT", "RULE-BASED REFERENCE")
    rounded_box(draw, (48, 1204, 1032, 1238), fill=mix(SURFACE, FIONA_GOLD, 0.05), outline=BORDER)
    draw.text((64, 1210), context.topic.upper(), font=font(17, bold=True), fill=FIONA_GOLD)
    draw_text_fit(
        draw,
        (214, 1208, 796, 1234),
        semantic_limit(context.reference, 40),
        font(18, bold=True),
        SECONDARY_TEXT,
        max_lines=1,
    )
    draw.text((1014, 1211), "参照不代表情景重演", font=font(16, bold=True), fill=MUTED_TEXT, anchor="ra")


def draw_tags(draw: ImageDraw.ImageDraw, hashtags: Iterable[str]) -> None:
    x = 48
    y = 1248
    for tag in list(dict.fromkeys(hashtags))[:3]:
        label = semantic_limit(str(tag), 16)
        width = text_width(draw, label, font(18, bold=True)) + 26
        if x + width > 1032:
            break
        rounded_box(draw, (x, y, x + width, y + 28), fill=mix(SURFACE, FIONA_GOLD, 0.08), outline=BORDER, radius=7)
        draw.text((x + 13, y + 3), label, font=font(18, bold=True), fill=SECONDARY_TEXT)
        x += width + 12


def draw_footer(draw: ImageDraw.ImageDraw) -> None:
    draw.line((48, 1285, 1032, 1285), fill=BORDER, width=1)
    draw_text_fit(draw, (48, 1300, 760, 1335), DISCLAIMER, font(16), MUTED_TEXT, max_lines=1)
    draw.text((1032, 1300), "FIONA INTELLIGENCE SYSTEM", font=font(16, bold=True), fill=MUTED_TEXT, anchor="ra")


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

    if (
        view_model.data_quality.status == "Full"
        and source_count >= 3
        and not critical_missing
    ):
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
    cards = [item for item in view_model.heat_map if item.score is not None]
    if len(cards) < 3:
        return MarketRegimeAssessment(
            regime=MarketRegime.UNKNOWN,
            reason="有效市场覆盖不足，暂不判断状态",
        )

    scores = [int(item.score) for item in cards if item.score is not None]
    average = sum(scores) / len(scores)
    bullish = sum(item.direction == "Bullish" for item in cards)
    bearish = sum(item.direction == "Bearish" for item in cards)
    spread = max(scores) - min(scores)

    if len(cards) >= 3 and bearish == 0 and (bullish >= 2 or average >= 62):
        return MarketRegimeAssessment(
            regime=MarketRegime.RISK_ON,
            reason="多市场风险偏好形成正向共振",
        )
    if len(cards) >= 3 and bullish == 0 and (bearish >= 2 or average <= 38):
        return MarketRegimeAssessment(
            regime=MarketRegime.RISK_OFF,
            reason="多市场同步走弱，风险偏好收缩",
        )
    if (bullish and bearish) or spread >= 24:
        return MarketRegimeAssessment(
            regime=MarketRegime.TRANSITION,
            reason="市场信号分化，状态仍在切换",
        )
    return MarketRegimeAssessment(
        regime=MarketRegime.NEUTRAL,
        reason="跨市场方向尚未形成一致共振",
    )


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
        output.append("等待资金流与关键资产形成同向确认")
    return tuple(output)


def format_watch_variable(value: str) -> str:
    normalized = re.sub(r"\s+", " ", str(value)).strip()
    lower = normalized.lower()
    if ("美债" in lower or "us10y" in lower or "yield" in lower) and (
        "美元" in lower or "dxy" in lower
    ):
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
    return semantic_limit(normalized, 20)


def derive_historical_context(view_model: MarketNewsViewModel) -> HistoricalContextAssessment:
    corpus = " ".join(
        [
            view_model.fiona_view,
            *(
                f"{item.event} {item.why} {item.watch}"
                for item in view_model.what_changed
            ),
            *(item.name for item in view_model.current_narrative),
            *(tag.display_name for tag in view_model.tags),
        ]
    ).lower()
    rules = (
        (
            ("liquidity", "流动性", "美元", "dxy"),
            HistoricalContextAssessment("Liquidity", "Previous liquidity tightening cycle"),
        ),
        (
            ("etf", "ibit", "fbtc"),
            HistoricalContextAssessment("ETF Flow", "Previous ETF inflow period"),
        ),
        (
            ("fed", "fomc", "rate", "yield", "利率", "美债", "us10y"),
            HistoricalContextAssessment("Rates", "Historical Fed tightening phase"),
        ),
        (
            ("rwa", "tokenized", "代币化"),
            HistoricalContextAssessment("RWA", "Previous institutional adoption phase"),
        ),
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
        return semantic_limit(view_model.what_changed[0].why, 28)
    if view_model.current_narrative:
        return semantic_limit(view_model.current_narrative[0].name, 16)
    return "暂无新增高价值驱动"


def next_confirmation(view_model: MarketNewsViewModel) -> str:
    if view_model.what_changed:
        return view_model.what_changed[0].watch
    return "等待资金流与关键资产形成同向确认"


def format_narrative(item: NarrativeView) -> str:
    confidence = f"{item.confidence}%" if item.confidence is not None else "Confidence unavailable"
    return f"{semantic_limit(item.name, 16)} · {item.direction} · {confidence}"


def draw_section_title(draw: ImageDraw.ImageDraw, y: int, title: str, meta: str) -> None:
    draw.text((48, y), title, font=font(22, bold=True), fill=PRIMARY_TEXT)
    draw.text((1032, y + 2), meta, font=font(20, bold=True), fill=MUTED_TEXT, anchor="ra")


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
    left, top, right, bottom = box
    lines = wrap_text_pixels(draw, str(text), selected_font, right - left, max_lines)
    line_height = font_line_height(selected_font) + line_gap
    max_height_lines = max(1, (bottom - top + line_gap) // line_height)
    lines = lines[:max_height_lines]
    for index, line in enumerate(lines):
        draw.text((left, top + index * line_height), line, font=selected_font, fill=fill)
    return lines


def wrap_text_pixels(
    draw: ImageDraw.ImageDraw,
    text: str,
    selected_font: ImageFont.FreeTypeFont,
    max_width: int,
    max_lines: int,
) -> list[str]:
    clean = re.sub(r"\s+", " ", str(text)).strip()
    if not clean:
        return [""]
    tokens = tokenize(clean)
    lines: list[str] = []
    current = ""
    consumed = 0
    for token in tokens:
        candidate = current + token
        if current and text_width(draw, candidate.rstrip(), selected_font) > max_width:
            lines.append(current.rstrip())
            current = token.lstrip()
            if len(lines) == max_lines:
                break
        else:
            current = candidate
        consumed += 1
    if len(lines) < max_lines and current:
        lines.append(current.rstrip())
    if consumed < len(tokens) and lines:
        lines[-1] = ellipsize(draw, lines[-1], selected_font, max_width)
    return lines[:max_lines]


def tokenize(text: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9][A-Za-z0-9._/%+\-]*|\s+|.", text, flags=re.DOTALL)


def ellipsize(
    draw: ImageDraw.ImageDraw,
    text: str,
    selected_font: ImageFont.FreeTypeFont,
    max_width: int,
) -> str:
    value = text.rstrip("… ")
    while value and text_width(draw, value + "…", selected_font) > max_width:
        tokens = tokenize(value)
        if not tokens:
            break
        tokens.pop()
        value = "".join(tokens).rstrip()
    return (value + "…") if value else "…"


def semantic_limit(text: str, max_chars: int) -> str:
    clean = re.sub(r"\s+", " ", str(text)).strip()
    if len(clean) <= max_chars:
        return clean
    prefix = clean[:max_chars]
    boundary = max(prefix.rfind(mark) for mark in ("。", "！", "？", "；", "，", "、", ".", ";", ","))
    if boundary >= max_chars // 2:
        result = prefix[: boundary + 1].rstrip()
        if result[-1] in {"，", "；", "、", ",", ";"}:
            result = result[:-1].rstrip() + "。"
        return result
    while prefix and prefix[-1].isascii() and prefix[-1].isalnum():
        prefix = prefix[:-1]
    return prefix.rstrip("，；、 ") + "…"


def validate_font_assets() -> None:
    missing = [str(path) for path in (FONT_REGULAR, FONT_BOLD) if not path.exists()]
    if missing:
        raise RuntimeError(f"Missing fixed Fiona font assets: {', '.join(missing)}")


@lru_cache(maxsize=64)
def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    path = FONT_BOLD if bold else FONT_REGULAR
    if not path.exists():
        raise RuntimeError(f"Missing fixed Fiona font asset: {path}")
    return ImageFont.truetype(str(path), size=size)


def font_line_height(selected_font: ImageFont.FreeTypeFont) -> int:
    ascent, descent = selected_font.getmetrics()
    return ascent + descent


def text_width(
    draw: ImageDraw.ImageDraw,
    text: str,
    selected_font: ImageFont.FreeTypeFont,
) -> int:
    left, _, right, _ = draw.textbbox((0, 0), text, font=selected_font)
    return right - left


def rounded_box(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    *,
    fill: str,
    outline: str,
    radius: int = 8,
) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=1)


def direction_color(direction: str) -> str:
    normalized = str(direction).lower()
    if normalized == "bullish":
        return POSITIVE
    if normalized == "bearish":
        return NEGATIVE
    if normalized in {"neutral", "awaiting"}:
        return NEUTRAL if normalized == "neutral" else DATA_GRAY
    return DATA_GRAY


def change_color(change: str) -> str:
    if str(change).startswith("+"):
        return POSITIVE
    if str(change).startswith("-"):
        return NEGATIVE
    return DATA_GRAY


def confidence_color(value: JudgmentConfidence | DataConfidence) -> str:
    if value in {JudgmentConfidence.HIGH, DataConfidence.VERIFIED}:
        return POSITIVE
    if value in {JudgmentConfidence.MEDIUM, DataConfidence.PARTIAL}:
        return NEUTRAL
    return DATA_GRAY


def evidence_color(value: EvidenceLevel) -> str:
    if value == EvidenceLevel.VERIFIED:
        return POSITIVE
    if value == EvidenceLevel.STRONG:
        return "#65A6C7"
    if value == EvidenceLevel.MODERATE:
        return NEUTRAL
    return DATA_GRAY


def regime_color(value: MarketRegime) -> str:
    if value == MarketRegime.RISK_ON:
        return POSITIVE
    if value == MarketRegime.RISK_OFF:
        return NEGATIVE
    if value == MarketRegime.TRANSITION:
        return FIONA_GOLD
    if value == MarketRegime.NEUTRAL:
        return NEUTRAL
    return DATA_GRAY


def validate_component_regions() -> None:
    regions = sorted(COMPONENT_REGIONS.items(), key=lambda item: item[1][1])
    previous_bottom = 0
    for name, (left, top, right, bottom) in regions:
        if left != 0 or right != IMAGE_WIDTH:
            raise RuntimeError(f"{name} does not span the fixed canvas width.")
        if top < previous_bottom or bottom <= top:
            raise RuntimeError(f"{name} overlaps another component region.")
        if bottom > IMAGE_HEIGHT:
            raise RuntimeError(f"{name} exceeds the fixed canvas height.")
        previous_bottom = bottom
    if previous_bottom != IMAGE_HEIGHT:
        raise RuntimeError("Component regions do not fill the fixed canvas height.")


def mix(base: str, overlay: str, alpha: float) -> str:
    base_rgb = hex_rgb(base)
    overlay_rgb = hex_rgb(overlay)
    mixed = tuple(round(base_rgb[index] * (1 - alpha) + overlay_rgb[index] * alpha) for index in range(3))
    return "#" + "".join(f"{value:02X}" for value in mixed)


def hex_rgb(value: str) -> tuple[int, int, int]:
    clean = value.lstrip("#")
    return tuple(int(clean[index : index + 2], 16) for index in (0, 2, 4))
