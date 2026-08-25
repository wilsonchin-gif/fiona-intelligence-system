from __future__ import annotations

import os
import re
from dataclasses import dataclass, fields
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable, Iterable, Mapping


FIONA_DISPLAY_TIMEZONE = timezone(timedelta(hours=8))
CJK_PATTERN = re.compile(
    r"[\u3000-\u303f\u3040-\u30ff\u31f0-\u31ff"
    r"\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\uff00-\uffef]"
)


class OutputLocale(str, Enum):
    ZH_CN = "zh-CN"
    EN_US = "en-US"


@dataclass(frozen=True)
class FionaLocaleStrings:
    brand_wordmark: str
    brand_descriptor: str
    product_title: str
    interim_badge: str
    market_regime: str
    evidence: str
    sources: str
    fiona_view: str
    today_judgment: str
    driver: str
    next_confirmation: str
    heat_map: str
    heat_map_meta: str
    what_changed: str
    what_changed_meta: str
    key_markets: str
    key_markets_meta: str
    narrative_context: str
    narrative_meta: str
    watch_next: str
    watch_next_meta: str
    historical_context: str
    historical_context_meta: str
    historical_caveat: str
    no_material_change: str
    no_material_change_why: str
    waiting_confirmation: str
    no_high_confidence_narrative: str
    data_unavailable: str
    awaiting: str
    confidence_unavailable: str
    data_coverage_limited: str
    informational_disclaimer: str
    caption_title: str


ZH_CN_STRINGS = FionaLocaleStrings(
    brand_wordmark="FIONA",
    brand_descriptor="MARKET INTELLIGENCE",
    product_title="Fiona Market News",
    interim_badge="04H BRIEF",
    market_regime="MARKET REGIME",
    evidence="EVIDENCE",
    sources="sources",
    fiona_view="FIONA'S VIEW",
    today_judgment="TODAY'S JUDGEMENT",
    driver="DRIVER",
    next_confirmation="NEXT",
    heat_map="MARKET HEAT MAP",
    heat_map_meta="EVIDENCE · FOUR MARKETS",
    what_changed="WHAT CHANGED",
    what_changed_meta="MATERIAL CHANGE ONLY · MAX 2",
    key_markets="KEY MARKETS",
    key_markets_meta="FIVE VERIFICATION ANCHORS",
    narrative_context="NARRATIVE CONTEXT",
    narrative_meta="MARKET STORY · MAX 2",
    watch_next="WATCH NEXT",
    watch_next_meta="OBSERVABLE · NOT A FORECAST",
    historical_context="HISTORICAL CONTEXT",
    historical_context_meta="REFERENCE · NOT ANALOGY",
    historical_caveat="参照不代表情景重演",
    no_material_change="暂无新增高价值变化。",
    no_material_change_why="现有信号尚未形成新的市场结构。",
    waiting_confirmation="等待资金流与关键资产同步确认。",
    no_high_confidence_narrative="暂无高置信主叙事",
    data_unavailable="数据暂缺",
    awaiting="等待确认",
    confidence_unavailable="置信度暂缺",
    data_coverage_limited="数据覆盖有限",
    informational_disclaimer="本内容仅供参考，不构成任何投资建议。投资有风险，入市需谨慎。",
    caption_title="Fiona Market News",
)


EN_US_STRINGS = FionaLocaleStrings(
    brand_wordmark="FIONA",
    brand_descriptor="MARKET INTELLIGENCE",
    product_title="Fiona Global Intelligence",
    interim_badge="MARKET BRIEF",
    market_regime="MARKET REGIME",
    evidence="EVIDENCE",
    sources="sources",
    fiona_view="FIONA'S VIEW",
    today_judgment="TODAY'S JUDGMENT",
    driver="DRIVER",
    next_confirmation="NEXT",
    heat_map="MARKET HEAT MAP",
    heat_map_meta="EVIDENCE · FOUR MARKETS",
    what_changed="WHAT CHANGED",
    what_changed_meta="MATERIAL CHANGE ONLY · MAX 2",
    key_markets="KEY MARKETS",
    key_markets_meta="FIVE VERIFICATION ANCHORS",
    narrative_context="NARRATIVE CONTEXT",
    narrative_meta="MARKET STORY · MAX 2",
    watch_next="WATCH NEXT",
    watch_next_meta="OBSERVABLE · NOT A FORECAST",
    historical_context="HISTORICAL CONTEXT",
    historical_context_meta="REFERENCE · NOT ANALOGY",
    historical_caveat="Context is not a forecast",
    no_material_change="No material change.",
    no_material_change_why="Current evidence has not formed a new market structure.",
    waiting_confirmation="Waiting for confirmation across flows and key assets.",
    no_high_confidence_narrative="No high-confidence narrative",
    data_unavailable="Data unavailable",
    awaiting="Awaiting confirmation",
    confidence_unavailable="Confidence unavailable",
    data_coverage_limited="Data coverage limited",
    informational_disclaimer="For informational purposes only. Not investment advice.",
    caption_title="Fiona Global Intelligence",
)


def output_locale_from_env(
    environ: Mapping[str, str] | None = None,
    warning_logger: Callable[[dict[str, Any]], None] | None = None,
) -> OutputLocale:
    source = os.environ if environ is None else environ
    return parse_output_locale(source.get("FIONA_OUTPUT_LOCALE"), warning_logger)


def parse_output_locale(
    raw_value: str | None,
    warning_logger: Callable[[dict[str, Any]], None] | None = None,
) -> OutputLocale:
    normalized = str(raw_value or OutputLocale.ZH_CN.value).strip().lower()
    aliases = {item.value.lower(): item for item in OutputLocale}
    if normalized in aliases:
        return aliases[normalized]
    if warning_logger is not None:
        warning_logger(
            {
                "event": "fionaOutputLocaleWarning",
                "invalid_locale": normalized,
                "fallback_locale": OutputLocale.ZH_CN.value,
            }
        )
    return OutputLocale.ZH_CN


def strings_for_locale(locale: OutputLocale | str) -> FionaLocaleStrings:
    selected = locale if isinstance(locale, OutputLocale) else parse_output_locale(locale)
    return EN_US_STRINGS if selected == OutputLocale.EN_US else ZH_CN_STRINGS


def format_display_timestamp(value: datetime, locale: OutputLocale | str) -> str:
    selected = locale if isinstance(locale, OutputLocale) else parse_output_locale(locale)
    aware = value if value.tzinfo is not None else value.replace(tzinfo=FIONA_DISPLAY_TIMEZONE)
    local = aware.astimezone(FIONA_DISPLAY_TIMEZONE)
    if selected == OutputLocale.EN_US:
        return local.strftime("%b %d · %H:%M UTC+8").upper()
    return local.strftime("%Y-%m-%d  %H:%M  UTC+8")


def contains_cjk(value: str) -> bool:
    return bool(CJK_PATTERN.search(str(value or "")))


def cjk_fragments(value: str) -> tuple[str, ...]:
    return tuple(CJK_PATTERN.findall(str(value or "")))


def infer_source_language(value: str) -> str:
    if contains_cjk(value):
        return "zh"
    return "en" if re.search(r"[A-Za-z]", str(value or "")) else "unknown"


def visible_locale_strings(locale: OutputLocale | str) -> tuple[str, ...]:
    resource = strings_for_locale(locale)
    return tuple(str(getattr(resource, item.name)) for item in fields(resource))


def unexpected_cjk(values: Iterable[str], *, allowlist: Iterable[str] = ()) -> tuple[str, ...]:
    allowed = {str(item).strip() for item in allowlist if str(item).strip()}
    leaks: list[str] = []
    for raw in values:
        value = str(raw or "")
        if not contains_cjk(value) or value in allowed:
            continue
        leaks.append(value)
    return tuple(dict.fromkeys(leaks))


def require_en_us_output(values: Iterable[str], *, allowlist: Iterable[str] = ()) -> None:
    leaks = unexpected_cjk(values, allowlist=allowlist)
    if leaks:
        raise ValueError(f"Unexpected CJK in en-US user output ({len(leaks)} field(s)).")


def english_narrative_name(narrative_id: str, name: str, category: str = "") -> str:
    known = {
        "ai_valuation_reset": "AI Valuation Reset",
        "btc_etf_flow_weakness": "BTC ETF Flow Weakness",
        "rwa_institutional_adoption": "RWA Institutional Adoption",
        "meme_short_term_hype": "Short-Term Meme Speculation",
        "macro_liquidity_repricing": "Macro Liquidity Repricing",
        "china_policy_flow_watch": "China Policy and Flow Confirmation",
    }
    if narrative_id in known:
        return known[narrative_id]
    if name and not contains_cjk(name):
        return clean_english_text(name)
    fallback = re.sub(r"[_-]+", " ", str(category or narrative_id or "market narrative"))
    return clean_english_text(fallback).title() or "Market Narrative"


def english_event_projection(event: Any) -> tuple[str, str, str]:
    category = str(getattr(getattr(event, "category", None), "value", "other") or "other").lower()
    title = clean_english_text(str(getattr(event, "title", "") or ""))
    raw_data = getattr(event, "raw_data", {}) if isinstance(getattr(event, "raw_data", {}), dict) else {}
    assets = [str(item).upper() for item in getattr(event, "affected_assets", []) if str(item).strip()]
    primary_asset = str(raw_data.get("symbol") or (assets[0] if assets else "the market"))

    if category == "price":
        change = safe_float(raw_data.get("change_pct"))
        what = (
            f"{primary_asset} moved {change:+.2f}% in the current observation window."
            if change is not None
            else f"{primary_asset} price conditions were updated in the current observation window."
        )
        why = "The move matters only if market flows and related risk assets confirm it."
        watch = f"{primary_asset} price, volume, and market flows."
    elif category == "macro":
        what = sentence_or_default(title, "U.S. macro and technology signals were updated.")
        why = "Rates, the dollar, and large technology assets can transmit risk appetite across markets."
        watch = "US10Y, DXY, and technology breadth."
    elif category in {"regulation", "policy"}:
        what = sentence_or_default(title, "China policy and market-flow signals were updated.")
        why = "Policy signals become material when liquidity, trading activity, and core assets respond together."
        watch = "Turnover, core assets, and the renminbi."
    elif category == "rwa":
        what = sentence_or_default(title, "RWA institutional adoption signals were updated.")
        why = "RWA intelligence is stronger when institutional activity is matched by durable capital and usage."
        watch = "RWA TVL, activity, and institutional adoption."
    elif category == "etf":
        what = sentence_or_default(title, "ETF flow conditions were updated.")
        why = "Persistent ETF flows can confirm or challenge price-led risk appetite."
        watch = "ETF flow persistence and spot liquidity."
    elif category == "risk":
        what = sentence_or_default(title, "A market risk condition was updated.")
        why = "Risk events matter when stress spreads across liquidity, leverage, or market infrastructure."
        watch = "Cross-asset stress or resolution."
    else:
        what = sentence_or_default(title, "A market intelligence item was updated.")
        why = "Its importance depends on independent confirmation and cross-market transmission."
        watch = "Independent evidence and cross-market impact."
    return what, why, watch


def clean_english_text(value: str) -> str:
    clean = re.sub(r"\s+", " ", str(value or "")).strip()
    return "" if contains_cjk(clean) else clean


def sentence_or_default(value: str, fallback: str) -> str:
    clean = clean_english_text(value) or fallback
    return clean if clean.endswith((".", "!", "?")) else clean + "."


def safe_float(value: Any) -> float | None:
    try:
        if value in (None, "", "-"):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None
