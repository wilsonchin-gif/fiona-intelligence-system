from __future__ import annotations

import html
import re
import struct
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

from app.fiona_briefing import sanitize_output
from app.fiona_contracts import FionaTag, TagType
from app.fiona_types import FionaEvent, NarrativeRecord, NarrativeStatus


IMAGE_WIDTH = 1080
IMAGE_HEIGHT = 1350
CAPTION_MIN_CHARS = 120
CAPTION_MAX_CHARS = 350
MAX_TAGS = 8
DISCLAIMER = "本内容仅供参考，不构成任何投资建议。投资有风险，入市需谨慎。"


@dataclass(frozen=True)
class HeatMapView:
    key: str
    label: str
    score: int | None
    direction: str
    key_metric: str


@dataclass(frozen=True)
class KeyMarketView:
    key: str
    label: str
    value: str
    change: str


@dataclass(frozen=True)
class ChangedEventView:
    event: str
    why: str
    watch: str


@dataclass(frozen=True)
class NarrativeView:
    name: str
    direction: str
    confidence: int | None


@dataclass(frozen=True)
class DataQualityView:
    status: str
    missing_fields: tuple[str, ...] = ()
    source_errors: tuple[str, ...] = ()


@dataclass(frozen=True)
class MarketNewsViewModel:
    generated_at: datetime
    heat_map: tuple[HeatMapView, ...]
    key_markets: tuple[KeyMarketView, ...]
    what_changed: tuple[ChangedEventView, ...]
    current_narrative: tuple[NarrativeView, ...]
    fiona_view: str
    tags: tuple[FionaTag, ...]
    data_quality: DataQualityView
    source_count: int = 0

    @property
    def telegram_hashtags(self) -> tuple[str, ...]:
        return tuple(tag.telegram_hashtag for tag in self.tags[:MAX_TAGS])


@dataclass(frozen=True)
class MarketNewsPrototypeResult:
    mode: str
    caption: str
    fallback_text: str
    image_path: Path | None = None
    error: str = ""


def build_market_news_view_model(
    snapshot: dict[str, Any] | None,
    events: Iterable[FionaEvent],
    narratives: Iterable[NarrativeRecord],
    generated_at: datetime | None = None,
) -> MarketNewsViewModel:
    source = snapshot if isinstance(snapshot, dict) else {}
    event_list = sorted(list(events), key=lambda item: item.intelligence_score, reverse=True)
    narrative_list = list(narratives)
    now = normalize_generated_at(source, generated_at)
    heat_map = build_heat_map(source)
    key_markets = build_key_markets(source, event_list)
    what_changed = build_changed_events(event_list)
    current_narrative = build_narrative_views(narrative_list)
    fiona_view = build_fiona_view(source, event_list, current_narrative)
    tags = build_market_news_tags(event_list, narrative_list)
    data_quality = assess_data_quality(source, heat_map, key_markets)
    source_count = count_data_sources(source, event_list)
    return MarketNewsViewModel(
        generated_at=now,
        heat_map=tuple(heat_map),
        key_markets=tuple(key_markets),
        what_changed=tuple(what_changed),
        current_narrative=tuple(current_narrative),
        fiona_view=fiona_view,
        tags=tuple(tags),
        data_quality=data_quality,
        source_count=source_count,
    )


def compose_market_news_caption(view_model: MarketNewsViewModel) -> str:
    state = summarize_market_state(view_model.heat_map)
    changed = view_model.what_changed[0].event if view_model.what_changed else "暂无新增高价值变化"
    view = ensure_sentence(compact_text(view_model.fiona_view, 118))
    hashtags = " ".join(view_model.telegram_hashtags)
    caption = (
        "Fiona Market News\n\n"
        f"过去4小时市场概览：{state}\n\n"
        f"关键变化：{compact_text(changed, 72)}。\n\n"
        f"【Fiona’s View】{view}\n\n"
        f"{hashtags}"
    ).strip()
    if len(caption) < CAPTION_MIN_CHARS:
        quality = (
            "当前数据覆盖完整，"
            if view_model.data_quality.status == "Full"
            else "部分数据仍待下一轮确认，"
        )
        caption = caption.replace(
            "【Fiona’s View】",
            f"市场判断：{quality}单一资产波动暂不代表跨市场方向。\n\n【Fiona’s View】",
            1,
        )
    if len(caption) > CAPTION_MAX_CHARS:
        fixed = (
            "Fiona Market News\n\n"
            f"过去4小时市场概览：{compact_text(state, 82)}\n\n"
            f"关键变化：{compact_text(changed, 48)}。\n\n"
        )
        suffix = f"\n\n{' '.join(view_model.telegram_hashtags)}"
        allowance = CAPTION_MAX_CHARS - len(fixed) - len("【Fiona’s View】") - len(suffix)
        caption = f"{fixed}【Fiona’s View】{compact_text(view_model.fiona_view, max(42, allowance))}{suffix}"
    return sanitize_output(caption)


def render_market_news_svg(view_model: MarketNewsViewModel) -> str:
    parts: list[str] = []
    add = parts.append
    add(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{IMAGE_WIDTH}" '
        f'height="{IMAGE_HEIGHT}" viewBox="0 0 {IMAGE_WIDTH} {IMAGE_HEIGHT}">'
    )
    add("<defs>")
    add(
        '<linearGradient id="page" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset="0" stop-color="#071421"/><stop offset="1" stop-color="#0b1722"/>'
        "</linearGradient>"
    )
    add(
        '<linearGradient id="view" x1="0" y1="0" x2="1" y2="1">'
        '<stop offset="0" stop-color="#17344d"/><stop offset="1" stop-color="#163f38"/>'
        "</linearGradient>"
    )
    add(
        '<filter id="shadow" x="-10%" y="-10%" width="120%" height="140%">'
        '<feDropShadow dx="0" dy="7" stdDeviation="9" flood-color="#000814" flood-opacity=".32"/>'
        "</filter>"
    )
    add("</defs>")
    add('<rect width="1080" height="1350" fill="url(#page)"/>')
    add('<rect x="0" y="0" width="1080" height="8" fill="#e8b84a"/>')
    add(svg_text(48, 60, "FIONA", 18, "#e8b84a", weight=800, letter_spacing=2))
    add(svg_text(48, 112, "Fiona Market News", 42, "#f5f7fa", weight=800))
    add(
        svg_text(
            48,
            146,
            view_model.generated_at.strftime("%Y-%m-%d %H:%M UTC+8"),
            20,
            "#9fb0bd",
            weight=500,
        )
    )
    add(svg_text(1032, 68, "AI MARKET", 15, "#7f93a3", anchor="end", weight=700))
    add(svg_text(1032, 92, "INTELLIGENCE", 15, "#7f93a3", anchor="end", weight=700))

    section_label(add, 48, 198, "MARKET HEAT MAP", "10-SECOND READ")
    card_colors = {
        "us": ("#132f55", "#5fa3ff"),
        "china": ("#4a2329", "#e66f75"),
        "crypto": ("#403617", "#e8b84a"),
        "rwa": ("#173c32", "#54b992"),
    }
    card_width = 234
    for index, card in enumerate(view_model.heat_map[:4]):
        x = 48 + index * 246
        bg, accent = card_colors.get(card.key, ("#172736", "#7890a3"))
        add(rounded_rect(x, 222, card_width, 154, 8, bg, "#274055"))
        add(f'<rect x="{x}" y="222" width="5" height="154" rx="2" fill="{accent}"/>')
        add(svg_text(x + 20, 253, card.label, 19, "#dce5ec", weight=700))
        score = str(card.score) if card.score is not None else "—"
        add(svg_text(x + 20, 306, score, 39, "#ffffff", weight=850))
        if card.score is not None:
            add(svg_text(x + 74, 306, "/100", 16, "#91a4b3", weight=600))
        add(svg_text(x + 20, 335, card.direction, 17, accent, weight=750))
        add(svg_text(x + 20, 361, compact_text(card.key_metric, 24), 15, "#aebdc8", weight=500))

    section_label(add, 48, 428, "WHAT CHANGED", "LAST 4 HOURS")
    changed = list(view_model.what_changed[:3])
    if not changed:
        changed = [ChangedEventView("暂无新增高价值变化", "现有信号尚未形成新的市场结构。", "等待资金流与关键资产同步确认。")]
    for index, item in enumerate(changed):
        y = 454 + index * 112
        add(rounded_rect(48, y, 984, 98, 8, "#111f2b", "#23394a"))
        add(svg_text(68, y + 31, f"0{index + 1}", 17, "#e8b84a", weight=800))
        event_lines = wrap_text(item.event, 54, 1)
        add(svg_text(112, y + 31, event_lines[0], 20, "#f3f6f8", weight=750))
        why = f"重要性：{item.why}"
        watch = f"确认点：{item.watch}"
        add(svg_text(112, y + 58, wrap_text(why, 62, 1)[0], 17, "#aebcc7", weight=500))
        add(svg_text(112, y + 83, wrap_text(watch, 62, 1)[0], 17, "#75c4ab", weight=600))

    section_label(add, 48, 810, "KEY MARKETS", "STRUCTURE")
    market_width = 185
    for index, item in enumerate(view_model.key_markets[:5]):
        x = 48 + index * 200
        add(rounded_rect(x, 836, market_width, 126, 8, "#f3f5f6", "#d5dde2"))
        add(svg_text(x + 16, 865, item.label, 17, "#40515e", weight=700))
        add(svg_text(x + 16, 906, item.value, 25, "#111c24", weight=850))
        change_color = direction_color(item.change)
        add(svg_text(x + 16, 938, item.change, 17, change_color, weight=750))

    section_label(add, 48, 1014, "CURRENT NARRATIVE", data_quality_label(view_model.data_quality))
    narrative_text = format_narrative_line(view_model.current_narrative)
    add(rounded_rect(48, 1040, 984, 78, 8, "#111f2b", "#294154"))
    for index, line in enumerate(wrap_text(narrative_text, 76, 2)):
        add(svg_text(70, 1073 + index * 27, line, 19, "#dfe7ed", weight=650))

    add(rounded_rect(48, 1142, 984, 142, 8, "url(#view)", "#3b6b65", shadow=True))
    add(svg_text(70, 1178, "FIONA’S VIEW", 19, "#e8b84a", weight=850, letter_spacing=1))
    for index, line in enumerate(wrap_text(view_model.fiona_view, 58, 3)):
        add(svg_text(70, 1210 + index * 27, line, 19, "#f2f6f7", weight=600))

    add(svg_text(48, 1320, DISCLAIMER, 14, "#748895", weight=450))
    add(svg_text(1032, 1320, "FIONA INTELLIGENCE SYSTEM", 13, "#586d7b", anchor="end", weight=700))
    add("</svg>")
    return "\n".join(parts)


def render_market_news_png(
    view_model: MarketNewsViewModel,
    output_path: str | Path,
    converter: Callable[[Path, Path], None] | None = None,
) -> Path:
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if converter is None:
        from app.fiona_card_renderer import render_market_news_card

        render_market_news_card(view_model, target)
    else:
        svg = render_market_news_svg(view_model)
        with tempfile.TemporaryDirectory(prefix="fiona-market-news-") as temp_dir:
            svg_path = Path(temp_dir) / "market_news.svg"
            svg_path.write_text(svg, encoding="utf-8")
            converter(svg_path, target)
    if not target.exists() or target.stat().st_size == 0:
        raise RuntimeError("Market News PNG renderer did not create an output file.")
    width, height = read_png_dimensions(target)
    if (width, height) != (IMAGE_WIDTH, IMAGE_HEIGHT):
        raise RuntimeError(f"Unexpected PNG dimensions: {width}x{height}")
    return target


def build_market_news_prototype(
    view_model: MarketNewsViewModel,
    output_path: str | Path,
    original_text: str = "",
    converter: Callable[[Path, Path], None] | None = None,
) -> MarketNewsPrototypeResult:
    caption = compose_market_news_caption(view_model)
    fallback_text = original_text.strip() or caption
    try:
        image_path = render_market_news_png(view_model, output_path, converter=converter)
        return MarketNewsPrototypeResult(
            mode="image_with_caption",
            caption=caption,
            fallback_text=fallback_text,
            image_path=image_path,
        )
    except Exception as exc:  # noqa: BLE001 - a renderer failure must preserve the text payload.
        return MarketNewsPrototypeResult(
            mode="text_fallback",
            caption=caption,
            fallback_text=fallback_text,
            error=str(exc),
        )


def read_png_dimensions(path: str | Path) -> tuple[int, int]:
    with Path(path).open("rb") as handle:
        header = handle.read(24)
    if len(header) < 24 or header[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("Not a valid PNG file.")
    return struct.unpack(">II", header[16:24])


def build_heat_map(snapshot: dict[str, Any]) -> list[HeatMapView]:
    expected = (
        ("us", "US Market"),
        ("china", "China Market"),
        ("crypto", "Crypto Market"),
        ("rwa", "RWA Market"),
    )
    indexed: dict[str, dict[str, Any]] = {}
    for item in snapshot.get("heatmap", []):
        if not isinstance(item, dict):
            continue
        key = str(item.get("key", "")).lower() or infer_heat_key(item.get("label"))
        if key and key not in indexed:
            indexed[key] = item
    output: list[HeatMapView] = []
    for key, label in expected:
        card = indexed.get(key, {})
        score = safe_int(card.get("score"))
        output.append(
            HeatMapView(
                key=key,
                label=str(card.get("label") or label),
                score=score,
                direction=normalize_direction(card.get("status"), score),
                key_metric=str(card.get("summary") or "数据暂缺"),
            )
        )
    return output


def build_key_markets(snapshot: dict[str, Any], events: list[FionaEvent] | None = None) -> list[KeyMarketView]:
    us = dict_or_empty(snapshot.get("us_market"))
    crypto = dict_or_empty(snapshot.get("crypto_market"))
    rwa = dict_or_empty(snapshot.get("rwa_market"))
    daily = dict_or_empty(snapshot.get("daily_market"))
    btc = dict_or_empty(crypto.get("btc"))
    eth = dict_or_empty(crypto.get("eth"))
    spx = dict_or_empty(us.get("primary"))
    us10y = find_quote(daily.get("quotes"), {"TNX", "^TNX", "US10Y"})
    gold = find_quote(daily.get("quotes"), {"GC=F", "GOLD", "XAUUSD"})
    hsi = find_quote(daily.get("quotes"), {"HSI", "^HSI"})
    rwa_tvl = dict_or_empty(rwa.get("tvl"))
    structural = [
        market_item("btc", "BTC", first_number(btc, "current_price", "price"), first_number(btc, "change_pct", "price_change_percentage_24h"), usd=True),
        market_item("spx", "S&P 500", first_number(spx, "price", "current_price"), first_number(spx, "change_pct", "price_change_percentage_24h")),
        market_item("us10y", "US10Y", first_number(us10y, "price", "current_price"), first_number(us10y, "change_pct", "price_change_percentage_24h"), suffix="%"),
        market_item("gold", "Gold", first_number(gold, "price", "current_price"), first_number(gold, "change_pct", "price_change_percentage_24h"), usd=True),
    ]
    dynamic_options = {
        "eth": market_item("eth", "ETH", first_number(eth, "current_price", "price"), first_number(eth, "change_pct", "price_change_percentage_24h"), usd=True),
        "hsi": market_item("hsi", "HSI", first_number(hsi, "price", "current_price"), first_number(hsi, "change_pct", "price_change_percentage_24h")),
        "rwa": market_item("rwa", "RWA TVL", first_number(rwa_tvl, "value", "current"), first_number(rwa_tvl, "change_1d", "change_24h"), usd=True, compact=True),
    }
    return [*structural, select_dynamic_market(events or [], dynamic_options)]


def build_changed_events(events: list[FionaEvent]) -> list[ChangedEventView]:
    output: list[ChangedEventView] = []
    seen: set[str] = set()
    for event in events:
        key = re.sub(r"\s+", " ", event.what_happened.strip().lower())
        if not key or key in seen:
            continue
        seen.add(key)
        output.append(
            ChangedEventView(
                event=sanitize_output(event.what_happened),
                why=sanitize_output(event.why_important),
                watch=sanitize_output(event.watch_next[0] if event.watch_next else "等待下一轮数据确认"),
            )
        )
        if len(output) == 3:
            break
    return output


def build_narrative_views(narratives: list[NarrativeRecord]) -> list[NarrativeView]:
    selected = [item for item in narratives if item.status == NarrativeStatus.CURRENT]
    if not selected:
        selected = [item for item in narratives if item.status == NarrativeStatus.EMERGING]
    if not selected:
        selected = narratives[:1]
    return [
        NarrativeView(
            name=item.name,
            direction=item.direction.value,
            confidence=safe_int(item.confidence_score),
        )
        for item in selected[:3]
    ]


def build_fiona_view(
    snapshot: dict[str, Any],
    events: list[FionaEvent],
    narratives: list[NarrativeView],
) -> str:
    raw = str(snapshot.get("wilson_view") or "").replace("Wilson", "Fiona").strip()
    if raw:
        return compact_text(sanitize_output(raw), 170)
    if narratives:
        return f"当前主线集中在{narratives[0].name}，但价格、资金与跨市场信号仍需相互确认。下一轮重点等待关键资产和流动性变量是否给出同向变化。"
    if events:
        return "过去4小时出现新的市场信号，但主线仍未收敛。Fiona更关注资金流、宏观变量与关键资产是否形成跨市场共振。"
    return "当前没有新增高价值变化，市场仍在等待更清晰的资金与风险偏好信号。下一轮重点验证关键资产是否出现同向变化。"


def build_market_news_tags(
    events: list[FionaEvent],
    narratives: list[NarrativeRecord],
) -> list[FionaTag]:
    candidates: list[FionaTag] = []
    text = " ".join(
        [
            " ".join(event.affected_assets)
            + " "
            + event.title
            + " "
            + event.what_happened
            + " "
            + event.why_important
            for event in events
        ]
        + [item.name + " " + item.category for item in narratives]
    ).lower()
    definitions = [
        (("btc", "bitcoin"), "asset_btc", "Bitcoin", TagType.ASSET, "#BTC"),
        (("eth", "ethereum"), "asset_eth", "Ethereum", TagType.ASSET, "#ETH"),
        (("rwa", "tokenized", "代币化"), "narrative_rwa", "RWA", TagType.NARRATIVE, "#RWA"),
        (("fed", "fomc", "美联储"), "policy_federal_reserve", "Federal Reserve", TagType.POLICY, "#Fed"),
        (("liquidity", "流动性", "资金流"), "narrative_liquidity", "Liquidity", TagType.NARRATIVE, "#Liquidity"),
        (("china", "中国", "a股"), "market_china", "China Market", TagType.MARKET, "#ChinaMarket"),
        (("ai", "nvda", "人工智能"), "narrative_ai", "AI", TagType.NARRATIVE, "#AI"),
        (("etf", "ibit", "fbtc"), "institution_etf", "ETF", TagType.INSTITUTION, "#ETF"),
        (("risk", "风险", "liquidation", "爆仓"), "risk_market", "Market Risk", TagType.RISK, "#Risk"),
    ]
    for keywords, canonical_id, display, tag_type, hashtag in definitions:
        if any(contains_keyword(text, keyword) for keyword in keywords):
            candidates.append(
                FionaTag(
                    canonical_id=canonical_id,
                    display_name=display,
                    tag_type=tag_type,
                    telegram_hashtag=hashtag,
                )
            )
    if not candidates:
        candidates.extend(
            [
                FionaTag("market_global", "Global Market", TagType.MARKET, telegram_hashtag="#Markets"),
                FionaTag("risk_market", "Market Risk", TagType.RISK, telegram_hashtag="#Risk"),
            ]
        )
    return deduplicate_tags(candidates)[:MAX_TAGS]


def deduplicate_tags(tags: Iterable[FionaTag]) -> list[FionaTag]:
    seen_canonical: set[str] = set()
    seen_hashtags: set[str] = set()
    output: list[FionaTag] = []
    for tag in tags:
        canonical = tag.canonical_id.lower()
        hashtag = tag.telegram_hashtag.lower()
        if canonical in seen_canonical or hashtag in seen_hashtags:
            continue
        seen_canonical.add(canonical)
        seen_hashtags.add(hashtag)
        output.append(tag)
    return output


def assess_data_quality(
    snapshot: dict[str, Any],
    heat_map: list[HeatMapView],
    key_markets: list[KeyMarketView],
) -> DataQualityView:
    missing = [f"heat_map.{item.key}" for item in heat_map if item.score is None]
    missing.extend(f"key_markets.{item.key}" for item in key_markets if item.value == "—")
    errors = tuple(str(item) for item in snapshot.get("errors", []) if str(item).strip())
    if len(missing) >= 4 or len(errors) >= 3:
        status = "Degraded"
    elif missing or errors:
        status = "Partial"
    else:
        status = "Full"
    return DataQualityView(status=status, missing_fields=tuple(missing), source_errors=errors)


def count_data_sources(snapshot: dict[str, Any], events: Iterable[FionaEvent]) -> int:
    identities = {
        str(event.source).strip().lower()
        for event in events
        if str(event.source).strip()
    }
    for item in snapshot.get("sources", []):
        if isinstance(item, dict):
            identity = item.get("source_id") or item.get("id") or item.get("name") or item.get("url")
        else:
            identity = item
        normalized = str(identity or "").strip().lower()
        if normalized:
            identities.add(normalized)
    return len(identities)


def summarize_market_state(heat_map: tuple[HeatMapView, ...]) -> str:
    available = [item for item in heat_map if item.score is not None]
    if not available:
        return "核心市场数据暂未形成有效覆盖，等待下一轮更新。"
    strongest = max(available, key=lambda item: item.score or 0)
    weakest = min(available, key=lambda item: item.score or 0)
    if strongest.key == weakest.key:
        return f"{strongest.label}处于{strongest.direction}状态，跨市场方向仍待确认。"
    return (
        f"{strongest.label}相对更强，{weakest.label}相对偏弱；"
        "市场仍需等待资金流与关键资产形成一致方向。"
    )


def format_narrative_line(narratives: tuple[NarrativeView, ...]) -> str:
    if not narratives:
        return "暂无高置信主叙事，市场仍在等待新的确认信号。"
    return "  |  ".join(
        f"{item.name} · {item.direction} · {item.confidence if item.confidence is not None else '—'}%"
        for item in narratives[:3]
    )


def data_quality_label(data_quality: DataQualityView) -> str:
    labels = {"Full": "DATA COVERAGE: FULL", "Partial": "DATA COVERAGE: PARTIAL", "Degraded": "DATA COVERAGE: DEGRADED"}
    return labels.get(data_quality.status, "DATA COVERAGE: UNKNOWN")


def market_item(
    key: str,
    label: str,
    value: float | None,
    change: float | None,
    *,
    usd: bool = False,
    compact: bool = False,
    suffix: str = "",
) -> KeyMarketView:
    if value is None:
        display = "—"
    elif compact:
        display = format_compact_usd(value)
    elif usd:
        display = f"${value:,.0f}" if value >= 100 else f"${value:,.2f}"
    else:
        display = f"{value:,.2f}{suffix}"
    change_text = "数据暂缺" if change is None else f"{change:+.2f}%"
    return KeyMarketView(key=key, label=label, value=display, change=change_text)


def select_dynamic_market(events: list[FionaEvent], options: dict[str, KeyMarketView]) -> KeyMarketView:
    assets = {
        asset.upper()
        for event in events[:3]
        for asset in event.affected_assets
    }
    if assets & {"RWA", "ONDO", "MKR", "BUIDL"}:
        return options["rwa"]
    if assets & {"HSI", "CSI500", "ASHR", "MCHI", "CNH"}:
        return options["hsi"]
    if "ETH" in assets:
        return options["eth"]
    for key in ("eth", "hsi", "rwa"):
        if options[key].value != "—":
            return options[key]
    return options["eth"]


def infer_heat_key(label: Any) -> str:
    normalized = str(label or "").strip().lower()
    if any(token in normalized for token in ("united states", "us market", "美国")):
        return "us"
    if any(token in normalized for token in ("china", "中国", "a股")):
        return "china"
    if any(token in normalized for token in ("crypto", "加密")):
        return "crypto"
    if any(token in normalized for token in ("rwa", "real world")):
        return "rwa"
    return ""


def find_quote(value: Any, symbols: set[str]) -> dict[str, Any]:
    if not isinstance(value, list):
        return {}
    for item in value:
        if isinstance(item, dict) and str(item.get("symbol", "")).upper() in symbols:
            return item
    return {}


def first_number(mapping: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        value = safe_float(mapping.get(key))
        if value is not None:
            return value
    return None


def safe_float(value: Any) -> float | None:
    if value in (None, "", "N/A", "—"):
        return None
    try:
        return float(str(value).replace(",", "").replace("%", "").replace("$", ""))
    except (TypeError, ValueError):
        return None


def safe_int(value: Any) -> int | None:
    number = safe_float(value)
    if number is None:
        return None
    return max(0, min(100, round(number)))


def normalize_direction(value: Any, score: int | None) -> str:
    text = str(value or "").strip().title()
    if text in {"Bullish", "Neutral", "Bearish"}:
        return text
    if score is None:
        return "Unavailable"
    if score >= 67:
        return "Bullish"
    if score <= 43:
        return "Bearish"
    return "Neutral"


def normalize_generated_at(snapshot: dict[str, Any], generated_at: datetime | None) -> datetime:
    if generated_at is not None:
        return generated_at if generated_at.tzinfo else generated_at.replace(tzinfo=timezone.utc)
    raw = snapshot.get("generated_at")
    if raw:
        try:
            parsed = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    display = snapshot.get("generated_at_display")
    if display:
        try:
            return datetime.strptime(str(display), "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    return datetime.now(timezone.utc)


def dict_or_empty(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def format_compact_usd(value: float) -> str:
    absolute = abs(value)
    if absolute >= 1_000_000_000_000:
        return f"${value / 1_000_000_000_000:.2f}T"
    if absolute >= 1_000_000_000:
        return f"${value / 1_000_000_000:.2f}B"
    if absolute >= 1_000_000:
        return f"${value / 1_000_000:.2f}M"
    return f"${value:,.0f}"


def compact_text(value: str, max_chars: int) -> str:
    text = re.sub(r"\s+", " ", str(value)).strip(" ；。")
    if len(text) <= max_chars:
        return text
    return text[: max(1, max_chars - 1)].rstrip("，；、 ") + "…"


def ensure_sentence(value: str) -> str:
    text = value.strip()
    if not text or text.endswith(("。", "！", "？", "…", ".", "!", "?")):
        return text
    return text + "。"


def contains_keyword(text: str, keyword: str) -> bool:
    if re.fullmatch(r"[a-z0-9]+", keyword) and len(keyword) <= 4:
        return re.search(rf"(?<![a-z0-9]){re.escape(keyword)}(?![a-z0-9])", text) is not None
    return keyword in text


def wrap_text(value: str, max_units: int, max_lines: int) -> list[str]:
    text = re.sub(r"\s+", " ", str(value)).strip()
    if not text:
        return [""]
    lines: list[str] = []
    current = ""
    units = 0
    for char in text:
        char_units = 2 if ord(char) > 127 else 1
        if current and units + char_units > max_units:
            lines.append(current.rstrip())
            current = char.lstrip()
            units = char_units
            if len(lines) == max_lines:
                break
        else:
            current += char
            units += char_units
    if len(lines) < max_lines and current:
        lines.append(current.rstrip())
    consumed = "".join(lines)
    if len(consumed.replace(" ", "")) < len(text.replace(" ", "")) and lines:
        lines[-1] = compact_text(lines[-1], max(2, len(lines[-1]) - 1)) + "…"
    return lines[:max_lines]


def direction_color(value: str) -> str:
    if value.startswith("+"):
        return "#1b8f67"
    if value.startswith("-"):
        return "#c14d54"
    return "#73838e"


def rounded_rect(
    x: int,
    y: int,
    width: int,
    height: int,
    radius: int,
    fill: str,
    stroke: str,
    *,
    shadow: bool = False,
) -> str:
    shadow_attr = ' filter="url(#shadow)"' if shadow else ""
    return (
        f'<rect x="{x}" y="{y}" width="{width}" height="{height}" rx="{radius}" '
        f'fill="{fill}" stroke="{stroke}" stroke-width="1"{shadow_attr}/>'
    )


def svg_text(
    x: int,
    y: int,
    value: str,
    size: int,
    color: str,
    *,
    anchor: str = "start",
    weight: int = 500,
    letter_spacing: int = 0,
) -> str:
    safe = html.escape(str(value))
    return (
        f'<text x="{x}" y="{y}" fill="{color}" font-size="{size}" '
        f'font-family="Arial Unicode MS, PingFang SC, STHeiti, Arial, sans-serif" '
        f'font-weight="{weight}" text-anchor="{anchor}" letter-spacing="{letter_spacing}">{safe}</text>'
    )


def section_label(add: Callable[[str], None], x: int, y: int, label: str, meta: str) -> None:
    add(svg_text(x, y, label, 17, "#dbe4ea", weight=800, letter_spacing=1))
    add(svg_text(1032, y, meta, 13, "#657c8c", anchor="end", weight=700))
