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
class FionaBriefLocaleStrings:
    market_news_intro: str
    morning_intro: str
    evening_intro: str
    daily_intro: str
    weekly_intro: str
    disclaimer_heading: str
    disclaimer: str
    missing_summary: str
    no_material_change: str
    no_current_narrative: str
    no_emerging_narrative: str
    no_false_narrative: str
    no_key_event: str
    no_concentrated_risk: str
    no_high_value_signal: str
    waiting_confirmation: str


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


EN_US_BRIEF_STRINGS = FionaBriefLocaleStrings(
    market_news_intro="Hi, I'm Fiona. Here is your current market snapshot.",
    morning_intro="Good morning, I'm Fiona. Here is what matters before markets get active.",
    evening_intro="Good evening, I'm Fiona. Here is your night-session risk briefing.",
    daily_intro=(
        "Hi, investors. I'm Fiona, your market intelligence assistant.\n"
        "Here is today's evidence, organized around what matters and what requires confirmation."
    ),
    weekly_intro="Hi, I'm Fiona. Here is your weekly market intelligence summary.",
    disclaimer_heading="DISCLAIMER",
    disclaimer="For informational purposes only. Not investment advice.",
    missing_summary="Some data is temporarily unavailable. Waiting for the next update.",
    no_material_change="No material change.",
    no_current_narrative="No high-confidence current narrative.",
    no_emerging_narrative="No high-confidence emerging narrative.",
    no_false_narrative="No high-confidence false narrative.",
    no_key_event="No material event is currently scheduled or confirmed.",
    no_concentrated_risk="No concentrated risk signal. Continue to verify flows and cross-market stress.",
    no_high_value_signal="No new high-value signal.",
    waiting_confirmation="Waiting for confirmation from flows, macro data, or market structure.",
)


SHARED_EN_US_TERMINOLOGY: dict[str, str] = {
    "intelligence_value": "Intelligence Value",
    "confidence": "Confidence",
    "market_regime": "Market Regime",
    "evidence": "Evidence",
    "overnight_market": "Overnight Market",
    "todays_watch": "Today's Watch",
    "todays_key_events": "Today's Key Events",
    "tonights_focus": "Tonight's Focus",
    "night_risk_radar": "Night Risk Radar",
    "key_events": "Key Events",
    "what_changed": "What Changed",
    "risk_radar": "Risk Radar",
    "fiona_view": "Fiona's View",
    "next_confirmation": "Next Confirmation",
    "current_narrative": "Current Narrative",
    "emerging_narrative": "Emerging Narrative",
    "market_movers": "Market Movers",
    "global_markets": "Global Markets",
    "historical_context": "Historical Context",
    "data_unavailable": "Data Unavailable",
    "no_material_change": "No Material Change",
    "waiting_confirmation": "Waiting for Confirmation",
    "market_heat_map": "Market Heat Map",
    "key_markets": "Key Markets",
    "market_temperature": "Market Temperature",
    "todays_market_pulse": "Today's Market Pulse",
    "important_events": "Important Events",
    "crypto_dashboard": "Crypto Dashboard",
    "weekly_winners": "Weekly Winners",
    "weekly_losers": "Weekly Losers",
    "narrative_ranking": "Narrative Ranking",
    "capital_flow": "Capital Flow",
    "false_narrative_watchlist": "False Narrative Watchlist",
    "next_week_scenario": "Next Week Scenario",
    "what_could_change_tonight": "What Could Change Tonight",
    "etf_macro_crypto": "ETF / Macro / Crypto",
    "event": "Event",
    "why_it_matters": "Why It Matters",
    "affected_assets": "Affected Assets",
    "fiona_assessment": "Fiona Assessment",
}


ALERT_SEVERITY_EN_US = {
    "S": "Critical",
    "A": "High",
    "B": "Moderate",
    "C": "Low",
}


KNOWN_EN_US_REPAIRS = {
    "更新时间": "Updated",
    "为什么重要": "Why It Matters",
    "影响资产": "Affected Assets",
    "接下来确认": "Next Confirmation",
    "Fiona 判断": "Fiona Assessment",
    "数据暂未返回": "Data unavailable",
    "暂无新增高价值变化": "No material change",
    "：": ":",
    "，": ", ",
    "；": "; ",
    "。": ".",
    "【": "[",
    "】": "]",
}


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


def brief_strings_for_locale(locale: OutputLocale | str) -> FionaBriefLocaleStrings:
    selected = locale if isinstance(locale, OutputLocale) else parse_output_locale(locale)
    if selected == OutputLocale.EN_US:
        return EN_US_BRIEF_STRINGS
    return FionaBriefLocaleStrings(
        market_news_intro="Hi, I'm Fiona. Here is your 4-hour market snapshot.",
        morning_intro="Good morning, I'm Fiona. Here is what matters before the market gets active.",
        evening_intro="Good evening, I'm Fiona. Here is your night-session risk briefing.",
        daily_intro=(
            "Hi, investors, I'm your assistant Fiona.\n"
            "The following is the market information I just collected. I'll sort it out for you."
        ),
        weekly_intro="Hi, I'm Fiona. Here is your weekly market intelligence summary.",
        disclaimer_heading="Disclaimer",
        disclaimer="本内容仅供参考，不构成任何投资建议。投资有风险，入市需谨慎。",
        missing_summary="部分数据暂缺，等待下一轮更新。",
        no_material_change="暂无新增高价值变化。",
        no_current_narrative="暂无高置信主叙事",
        no_emerging_narrative="暂无高置信新兴叙事",
        no_false_narrative="暂无高置信伪叙事。",
        no_key_event="暂无重大事件。",
        no_concentrated_risk="暂无集中风险，但需观察是否出现资金流异常。",
        no_high_value_signal="暂无高价值新信号",
        waiting_confirmation="等待新的资金、宏观或监管信号。",
    )


def en_us_term(key: str) -> str:
    if key not in SHARED_EN_US_TERMINOLOGY:
        raise KeyError(f"Unknown Fiona en-US terminology key: {key}")
    return SHARED_EN_US_TERMINOLOGY[key]


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


def repair_known_en_us_output(value: str) -> str:
    repaired = str(value or "")
    for source, replacement in KNOWN_EN_US_REPAIRS.items():
        repaired = repaired.replace(source, replacement)
    return repaired


def finalize_user_visible_text(
    value: str,
    locale: OutputLocale | str,
    *,
    fallback: str | Callable[[], str],
) -> str:
    selected = locale if isinstance(locale, OutputLocale) else parse_output_locale(locale)
    if selected != OutputLocale.EN_US:
        return str(value or "")
    repaired = repair_known_en_us_output(value)
    if not contains_cjk(repaired):
        return repaired
    safe = fallback() if callable(fallback) else fallback
    safe = repair_known_en_us_output(safe)
    require_en_us_output((safe,))
    return safe


def compose_safe_en_us_brief_fallback(kind: str, generated_at: datetime) -> str:
    normalized = str(getattr(kind, "value", kind) or "intelligence").strip().lower().replace("-", "_")
    titles = {
        "market_news": "Fiona Global Intelligence",
        "morning": "Fiona Morning",
        "evening": "Fiona Evening",
        "daily": "Fiona Daily",
        "weekly": "Fiona Weekly",
        "alert": "Fiona Alert",
    }
    title = titles.get(normalized, "Fiona Intelligence")
    return "\n".join(
        [
            title,
            format_display_timestamp(generated_at, OutputLocale.EN_US),
            "",
            "[STATUS]",
            "A complete English brief could not be generated safely from the available evidence.",
            "",
            "[NEXT CONFIRMATION]",
            "Waiting for verified data and cross-market confirmation.",
            "",
            "[FIONA'S VIEW]",
            "Fiona is withholding mixed-language output until a reliable English summary is available.",
            "",
            "[DISCLAIMER]",
            EN_US_BRIEF_STRINGS.disclaimer,
        ]
    )


def compose_safe_en_us_alert_fallback(event: Any) -> str:
    assets = english_asset_names(getattr(event, "affected_assets", []))
    return "\n".join(
        [
            "Fiona Alert",
            "",
            "[EVENT]",
            "A material market event was detected, but its source-language details are still being normalized.",
            "",
            "[WHY IT MATTERS]",
            "The event may affect risk appetite, but the available evidence is not yet sufficient for a detailed English assessment.",
            "",
            "[AFFECTED ASSETS]",
            ", ".join(assets[:5]) if assets else "Market",
            "",
            "[NEXT CONFIRMATION]",
            "Waiting for verified evidence and cross-market confirmation.",
            "",
            "[FIONA'S VIEW]",
            "The signal remains under review. Fiona is not assigning an unsupported cause or price path.",
            "",
            "[DISCLAIMER]",
            EN_US_BRIEF_STRINGS.disclaimer,
        ]
    )


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
    elif category == "institution":
        what = sentence_or_default(title, "A major institution updated its market exposure or product activity.")
        why = "Institutional actions matter when they change durable capital flows, access, or market structure."
        watch = "Official confirmation, capital flows, and affected market activity."
    elif category == "onchain":
        what = sentence_or_default(title, "A material on-chain flow was detected.")
        why = "Large transfers become meaningful when exchange flows, liquidity, or leverage confirm them."
        watch = "Exchange flows, liquidity, and related price action."
    elif category == "narrative":
        what = sentence_or_default(title, "A market narrative changed materially.")
        why = "Narrative shifts matter only when capital flows and cross-market behavior support them."
        watch = "Narrative persistence, capital flows, and cross-market confirmation."
    else:
        what = sentence_or_default(title, "A market intelligence item was updated.")
        why = "Its importance depends on independent confirmation and cross-market transmission."
        watch = "Independent evidence and cross-market impact."
    return what, why, watch


def english_watch_points(event: Any, limit: int = 3) -> tuple[str, ...]:
    category = str(getattr(getattr(event, "category", None), "value", "other") or "other").lower()
    raw_data = getattr(event, "raw_data", {}) if isinstance(getattr(event, "raw_data", {}), dict) else {}
    assets = english_asset_names(getattr(event, "affected_assets", []))
    primary = str(raw_data.get("symbol") or (assets[0] if assets else "the primary asset")).upper()
    candidates = {
        "price": (
            f"Whether {primary} price action is confirmed by volume.",
            "Whether fund flows move in the same direction.",
            "Whether volatility spreads to related risk assets.",
        ),
        "etf": (
            "Whether ETF flows persist into the next reporting period.",
            "Whether spot liquidity confirms the flow signal.",
            "Whether crypto beta responds across major assets.",
        ),
        "macro": (
            "Whether US10Y and DXY move in the same direction.",
            "Whether equity breadth confirms the macro signal.",
            "Whether crypto risk appetite responds to the same evidence.",
        ),
        "regulation": (
            "Whether official guidance changes market participation.",
            "Whether turnover and core assets confirm the policy signal.",
            "Whether the renminbi reflects the same direction.",
        ),
        "institution": (
            "Whether an official filing or announcement confirms the action.",
            "Whether durable capital follows the announcement.",
            "Whether affected products show sustained activity.",
        ),
        "risk": (
            "Whether stress spreads across liquidity or leverage.",
            "Whether market infrastructure remains operational.",
            "Whether the event moves toward resolution.",
        ),
        "onchain": (
            "Whether the transfer reaches an exchange or custody venue.",
            "Whether liquidity and transaction volume confirm the move.",
            "Whether related assets show the same stress signal.",
        ),
        "rwa": (
            "Whether RWA TVL and activity continue to expand.",
            "Whether institutional adoption produces durable capital flows.",
            "Whether usage confirms the announcement.",
        ),
        "narrative": (
            "Whether capital flows confirm the narrative.",
            "Whether the theme persists across reporting cycles.",
            "Whether related assets move together.",
        ),
    }.get(
        category,
        (
            "Whether independent evidence confirms the event.",
            "Whether cross-market impact becomes measurable.",
            "Whether the signal persists into the next cycle.",
        ),
    )
    return tuple(candidates[: max(1, limit)])


def english_event_view(event: Any) -> str:
    category = str(getattr(getattr(event, "category", None), "value", "other") or "other").lower()
    direction = str(getattr(getattr(event, "market_direction", None), "value", "Neutral") or "Neutral")
    views = {
        "price": "This is a price anomaly, not a confirmed trend. Flow, volume, and cross-asset behavior still need to agree.",
        "etf": "The flow signal is material because it measures capital behavior. Persistence and spot-market confirmation remain decisive.",
        "macro": "The macro signal can transmit across yields, the dollar, equities, and crypto. Fiona is waiting for those markets to confirm one another.",
        "regulation": "The policy signal matters only if liquidity, participation, and core assets respond consistently.",
        "institution": "Institutional activity can alter market structure, but the announcement still requires evidence of durable capital or use.",
        "risk": "This is a material risk condition. Fiona is tracking whether stress broadens or moves toward resolution.",
        "onchain": "The transfer is observable, but intent is not. Exchange flows and liquidity will determine its market relevance.",
        "rwa": "RWA progress is strongest when institutional adoption is matched by persistent capital and real activity.",
        "narrative": "The narrative has changed, but attention alone is not confirmation. Capital and persistence remain the test.",
    }
    base = views.get(category, "The event is relevant, but independent evidence and cross-market confirmation remain necessary.")
    return f"Current direction is {direction}. {base}"


def english_alert_severity(level: Any) -> str:
    value = str(getattr(level, "value", level) or "C").upper()
    return ALERT_SEVERITY_EN_US.get(value, "Low")


def english_asset_names(values: Iterable[Any]) -> list[str]:
    output: list[str] = []
    for raw in values:
        clean = clean_english_text(str(raw or "")).strip()
        if not clean:
            continue
        normalized = clean.upper() if re.fullmatch(r"[A-Za-z0-9._/-]{1,16}", clean) else clean
        if normalized not in output:
            output.append(normalized)
    return output


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
