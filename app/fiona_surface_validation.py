from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from app.fiona_briefing import (
    build_daily_brief,
    build_evening_brief,
    build_morning_brief,
    build_weekly_brief,
)
from app.fiona_classifier import render_alert
from app.fiona_locale import OutputLocale, compose_safe_en_us_brief_fallback, contains_cjk
from app.fiona_market_news_image import build_market_news_view_model, compose_market_news_caption
from app.fiona_types import (
    AlertLevel,
    EventCategory,
    FionaEvent,
    MarketDirection,
    NarrativeRecord,
    NarrativeStatus,
)


VALIDATION_TIME = datetime(2026, 9, 2, 20, 0, tzinfo=timezone(timedelta(hours=8)))


def en_us_fixture_snapshot(missing: bool = False) -> dict[str, Any]:
    if missing:
        return {}
    return {
        "title": "Wilson's Market News",
        "generated_at_display": "2026-09-02 20:00",
        "timezone": "UTC+8",
        "frequency": "每4小时更新一次",
        "heatmap": [
            {"key": "us", "label": "美国市场", "score": 66, "status": "Neutral", "summary": "风险偏好稳定"},
            {"key": "china", "label": "中国市场", "score": 54, "status": "Neutral", "summary": "政策等待确认"},
            {"key": "crypto", "label": "加密市场", "score": 43, "status": "Bearish", "summary": "BTC波动扩大"},
            {"key": "rwa", "label": "RWA市场", "score": 62, "status": "Neutral", "summary": "机构采用持续"},
        ],
        "us_market": {
            "primary": {"name": "S&P 500", "price": 6488.2, "change_pct": 0.34},
            "indices": [
                {"symbol": "DJI", "name": "Dow Jones", "price": 45420.1, "change_pct": 0.22},
                {"symbol": "IXIC", "name": "Nasdaq", "price": 21985.4, "change_pct": 0.48},
                {"symbol": "GSPC", "name": "S&P 500", "price": 6488.2, "change_pct": 0.34},
            ],
            "top_gainers": [{"symbol": "NVDA", "change_pct": 4.2}],
            "top_losers": [{"symbol": "TSLA", "change_pct": -3.1}],
            "top_traded": [{"symbol": "AAPL", "change_pct": 0.7}],
        },
        "china_market": {
            "primary": {"name": "中证500", "price": 6218.5, "change_pct": -0.16},
            "indices": [{"symbol": "000001", "name": "上证指数", "price": 3892.2, "change_pct": 0.08}],
            "top_gainers": [{"symbol": "600519", "change_pct": 2.3}],
            "top_losers": [{"symbol": "300750", "change_pct": -1.8}],
            "top_traded": [{"symbol": "601318", "change_pct": 0.5}],
        },
        "crypto_market": {
            "btc": {"current_price": 108420, "market_cap": 2_157_000_000_000, "change_pct": -1.8},
            "eth": {"current_price": 4388, "market_cap": 529_000_000_000, "change_pct": -2.4},
            "stablecoin_growth": {"current": 313_870_000_000, "change_1d": 0.05},
            "daily_assets": {
                "SOL": {"price": 208.2, "market_cap": 101_000_000_000, "change_pct": -1.1},
                "BNB": {"price": 842.3, "market_cap": 117_000_000_000, "change_pct": 0.4},
                "HYPE": {"price": 44.1, "market_cap": 14_600_000_000, "change_pct": 2.3},
                "UNI": {"price": 12.8, "market_cap": 8_100_000_000, "change_pct": -0.6},
            },
            "top100_ranking": {
                "gainers": [{"symbol": "FET", "change_pct": 8.2}],
                "losers": [{"symbol": "PEPE", "change_pct": -9.1}],
            },
        },
        "rwa_market": {
            "tvl": {"value": 13_200_000_000},
            "market_cap": {"value": 64_100_000_000},
            "volume": {"value": 1_410_000_000},
            "capital_flow": {"value": 82_000_000},
        },
        "daily_market": {
            "quotes": [
                {"symbol": "HSI", "price": 25118.3, "change_pct": 0.41},
                {"symbol": "GC=F", "price": 3528.4, "change_pct": 0.3},
                {"symbol": "SI=F", "price": 41.2, "change_pct": -0.2},
                {"symbol": "CL=F", "price": 69.4, "change_pct": 0.8},
                {"symbol": "BZ=F", "price": 73.1, "change_pct": 0.6},
            ]
        },
        "wilson_view": "市场需要等待资金流和宏观信号共同确认。",
        "errors": [],
    }


def en_us_fixture_events(missing: bool = False) -> list[FionaEvent]:
    if missing:
        return []
    return [
        FionaEvent(
            event_id="fixture_macro_001",
            created_at=VALIDATION_TIME,
            source="fixture_primary",
            category=EventCategory.MACRO,
            title="U.S. yields and technology breadth diverge",
            what_happened="美债收益率走高，但科技股宽度仍保持稳定。",
            why_important="利率与科技股的分化会影响全球风险偏好。",
            affected_assets=["US10Y", "DXY", "SPX", "QQQ", "BTC"],
            watch_next=["美元与美债收益率是否继续同向", "科技股宽度是否减弱"],
            fiona_view="宏观信号尚未形成一致方向。",
            impact_score=8,
            urgency_score=7,
            confidence_score=8,
            intelligence_score=78,
            conviction_score=76,
            market_direction=MarketDirection.NEUTRAL,
            level=AlertLevel.A,
            raw_data={
                "original_title": "美债收益率上行，科技股维持韧性",
                "original_text": "市场等待新的宏观确认。",
                "source_url": "https://example.com/macro",
                "source_language": "zh",
                "narratives": ["macro_liquidity_repricing"],
            },
        ),
        FionaEvent(
            event_id="fixture_btc_001",
            created_at=VALIDATION_TIME,
            source="fixture_market_data",
            category=EventCategory.PRICE,
            title="BTC one-hour volatility exceeds its monitoring threshold",
            what_happened="BTC一小时下跌1.8%。",
            why_important="短周期波动可能反映风险偏好重新定价。",
            affected_assets=["BTC", "ETH", "SOL"],
            watch_next=["成交量是否确认", "ETF资金流是否同步"],
            fiona_view="价格变化需要资金确认。",
            impact_score=8,
            urgency_score=9,
            confidence_score=9,
            intelligence_score=82,
            conviction_score=84,
            market_direction=MarketDirection.BEARISH,
            level=AlertLevel.S,
            raw_data={
                "symbol": "BTC",
                "change_pct": -1.8,
                "original_title": "BTC一小时下跌1.8%",
                "source_language": "zh",
                "narratives": ["btc_etf_flow_weakness"],
            },
        ),
        FionaEvent(
            event_id="fixture_rwa_001",
            created_at=VALIDATION_TIME,
            source="fixture_official",
            category=EventCategory.RWA,
            title="Institutional tokenization activity expands",
            what_happened="机构代币化产品继续扩大覆盖。",
            why_important="真实采用与持续资金流决定RWA叙事质量。",
            affected_assets=["RWA", "ONDO", "MKR"],
            watch_next=["TVL是否持续增长", "产品使用量是否确认"],
            fiona_view="机构采用需要真实资金与使用场景确认。",
            impact_score=7,
            urgency_score=5,
            confidence_score=8,
            intelligence_score=72,
            conviction_score=79,
            market_direction=MarketDirection.BULLISH,
            level=AlertLevel.A,
            raw_data={
                "original_title": "机构代币化产品更新",
                "source_language": "zh",
                "narratives": ["rwa_institutional_adoption"],
            },
        ),
    ]


def en_us_fixture_narratives(missing: bool = False) -> list[NarrativeRecord]:
    if missing:
        return []
    return [
        NarrativeRecord(
            narrative_id="macro_liquidity_repricing",
            name="宏观流动性重定价",
            category="macro",
            assets=["US10Y", "DXY", "SPX", "BTC"],
            keywords=["rates", "dollar"],
            first_seen_at=VALIDATION_TIME,
            last_seen_at=VALIDATION_TIME,
            mention_count=5,
            source_count=3,
            event_count=2,
            confidence_score=82,
            narrative_score=84,
            funds_score=61,
            persistence_score=76,
            cross_market_score=80,
            direction=MarketDirection.NEUTRAL,
            status=NarrativeStatus.CURRENT,
        ),
        NarrativeRecord(
            narrative_id="rwa_institutional_adoption",
            name="RWA机构采用",
            category="rwa",
            assets=["RWA", "ONDO"],
            keywords=["tokenization"],
            first_seen_at=VALIDATION_TIME,
            last_seen_at=VALIDATION_TIME,
            mention_count=3,
            source_count=2,
            event_count=1,
            confidence_score=74,
            narrative_score=70,
            funds_score=67,
            persistence_score=72,
            cross_market_score=58,
            direction=MarketDirection.BULLISH,
            status=NarrativeStatus.EMERGING,
        ),
        NarrativeRecord(
            narrative_id="meme_short_term_hype",
            name="短期Meme炒作",
            category="meme",
            assets=["MEME"],
            keywords=["meme"],
            first_seen_at=VALIDATION_TIME,
            last_seen_at=VALIDATION_TIME,
            mention_count=12,
            source_count=1,
            event_count=2,
            confidence_score=81,
            narrative_score=38,
            funds_score=22,
            persistence_score=18,
            cross_market_score=12,
            direction=MarketDirection.NEUTRAL,
            status=NarrativeStatus.FALSE,
            false_reasons=["热度高", "资金确认不足", "持续性偏弱"],
        ),
    ]


def build_en_us_user_surface_outputs(missing: bool = False) -> dict[str, str]:
    events = en_us_fixture_events(missing)
    narratives = en_us_fixture_narratives(missing)
    snapshot = en_us_fixture_snapshot(missing)
    market_model = build_market_news_view_model(
        snapshot,
        events,
        narratives,
        generated_at=VALIDATION_TIME,
        output_locale=OutputLocale.EN_US,
    )
    outputs = {
        "market_news": compose_market_news_caption(market_model),
        "morning": build_morning_brief(
            events,
            narratives,
            generated_at=VALIDATION_TIME,
            output_locale=OutputLocale.EN_US,
        ).render_text(),
        "evening": build_evening_brief(
            events,
            narratives,
            generated_at=VALIDATION_TIME,
            output_locale=OutputLocale.EN_US,
        ).render_text(),
        "daily": build_daily_brief(
            events,
            narratives,
            snapshot=snapshot,
            generated_at=VALIDATION_TIME,
            output_locale=OutputLocale.EN_US,
        ).render_text(),
        "weekly": build_weekly_brief(
            events,
            narratives,
            snapshot=snapshot,
            generated_at=VALIDATION_TIME,
            output_locale=OutputLocale.EN_US,
        ).render_text(),
        "fallback": compose_safe_en_us_brief_fallback("daily", VALIDATION_TIME),
    }
    if events:
        outputs["alert_critical"] = render_alert(events[1], output_locale=OutputLocale.EN_US)
        outputs["alert_moderate"] = render_alert(
            replace(events[2], level=AlertLevel.B, intelligence_score=58),
            output_locale=OutputLocale.EN_US,
        )
    else:
        missing_alert = FionaEvent(
            event_id="fixture_missing_alert",
            created_at=VALIDATION_TIME,
            source="fixture",
            category=EventCategory.OTHER,
            title="Market event under verification",
            what_happened="",
            why_important="",
            affected_assets=[],
            watch_next=[],
            fiona_view="",
            level=AlertLevel.B,
        )
        outputs["alert_moderate"] = render_alert(missing_alert, output_locale=OutputLocale.EN_US)
    return outputs


def validate_en_us_user_surfaces_runtime() -> dict[str, Any]:
    outputs = build_en_us_user_surface_outputs(missing=False)
    checks = {
        "market_news_cjk": contains_cjk(outputs["market_news"]),
        "morning_cjk": contains_cjk(outputs["morning"]),
        "evening_cjk": contains_cjk(outputs["evening"]),
        "daily_cjk": contains_cjk(outputs["daily"]),
        "weekly_cjk": contains_cjk(outputs["weekly"]),
        "alert_cjk": contains_cjk(outputs["alert_critical"]),
    }
    return {
        "output_locale": OutputLocale.EN_US.value,
        **checks,
        "all_user_surfaces_en_us": not any(checks.values()),
        "telegram_api_calls": 0,
        "ledger_mutations": 0,
        "scheduler_mutations": 0,
        "formal_occurrences_created": 0,
    }


def write_en_us_surface_fixtures(output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for suffix, missing in (("full", False), ("missing", True)):
        outputs = build_en_us_user_surface_outputs(missing=missing)
        for surface in ("morning", "evening", "daily", "weekly"):
            target = output_dir / f"{surface}_{suffix}.md"
            target.write_text(outputs[surface], encoding="utf-8")
            written.append(target)
        if missing:
            continue
        for surface in ("alert_critical", "alert_moderate", "fallback"):
            target = output_dir / f"{surface}.md"
            target.write_text(outputs[surface], encoding="utf-8")
            written.append(target)
    return written
