from __future__ import annotations

import unittest
from datetime import datetime, timezone

from app.fiona_briefing import (
    BRIEF_SCHEDULES,
    FionaBriefKind,
    build_daily_brief,
    build_evening_brief,
    build_market_news_brief,
    build_morning_brief,
    build_weekly_brief,
)
from app.fiona_narrative import NarrativeEngine
from app.fiona_types import EventCategory, FionaEvent, MarketDirection


NOW = datetime(2026, 6, 24, 20, 30, tzinfo=timezone.utc)


def event(**overrides) -> FionaEvent:
    base = {
        "event_id": "event_1",
        "created_at": NOW,
        "source": "unit_test",
        "category": EventCategory.ETF,
        "title": "BTC ETF flow weakens",
        "what_happened": "BTC ETF资金流边际走弱",
        "why_important": "ETF资金是本轮风险偏好的关键确认变量。",
        "affected_assets": ["BTC", "ETH", "IBIT"],
        "watch_next": ["ETF净流出是否扩大", "BTC关键支撑是否失守"],
        "fiona_view": "该事件需要和价格、稳定币、链上风险一起判断。",
        "impact_score": 9,
        "urgency_score": 8,
        "confidence_score": 9,
        "intelligence_score": 88,
        "market_direction": MarketDirection.BEARISH,
        "raw_data": {"narratives": ["btc_etf_flow_weakness"], "funds_score": 25, "mention_count": 1},
    }
    base.update(overrides)
    return FionaEvent(**base)


def sample_events() -> list[FionaEvent]:
    return [
        event(event_id="btc_etf", source="etf_feed"),
        event(
            event_id="fed",
            source="macro_feed",
            category=EventCategory.MACRO,
            title="Fed speech reprices rate expectations",
            what_happened="美联储讲话压低降息预期",
            why_important="利率路径会影响美股估值和加密风险偏好。",
            affected_assets=["DXY", "US10Y", "SPY", "QQQ", "BTC"],
            watch_next=["美元和美债收益率是否继续上行"],
            intelligence_score=94,
            market_direction=MarketDirection.BEARISH,
            raw_data={"narratives": ["macro_liquidity_repricing"], "funds_score": 45},
        ),
        event(
            event_id="meme",
            source="social_feed",
            category=EventCategory.PRICE,
            title="Meme heat spikes without flow confirmation",
            what_happened="Meme短线热度上升但资金确认不足",
            why_important="热度高但持续性差，容易制造误导性风险偏好。",
            affected_assets=["PEPE", "MEME"],
            watch_next=["热度是否转化为真实成交和资金流"],
            intelligence_score=45,
            market_direction=MarketDirection.BULLISH,
            raw_data={"narratives": ["meme_short_term_hype"], "funds_score": 20, "meme_or_hype": True, "mention_count": 3},
        ),
    ]


def sample_snapshot() -> dict[str, object]:
    return {
        "heatmap": [
            {"label": "US Market", "score": 62, "status": "Neutral", "summary": "S&P 500 +0.30%"},
            {"label": "China Market", "score": 48, "status": "Neutral", "summary": "中证500 -0.20%"},
            {"label": "Crypto Market", "score": 41, "status": "Bearish", "summary": "BTC -1.60%"},
            {"label": "RWA Market", "score": 57, "status": "Neutral", "summary": "TVL 小幅流入"},
        ],
        "us_market": {
            "primary": {"name": "S&P 500", "price": 5450.21, "change_pct": 0.3},
            "indices": [
                {"symbol": "DJI", "name": "Dow Jones", "price": 38834.86, "change_pct": 0.74},
                {"symbol": "IXIC", "name": "Nasdaq", "price": 17689.66, "change_pct": 1.8},
                {"symbol": "GSPC", "name": "S&P 500", "price": 5450.21, "change_pct": 0.3},
            ],
            "top_gainers": [{"symbol": "NVDA", "change_pct": 2.1}],
            "top_losers": [{"symbol": "CRM", "change_pct": -3.4}],
            "top_traded": [{"symbol": "AAPL", "change_pct": 0.4}],
        },
        "china_market": {
            "primary": {"name": "中证500", "price": 5642.31, "change_pct": -0.2},
            "indices": [{"symbol": "000001", "name": "上证指数", "price": 4110.81, "change_pct": 0.11}],
            "top_gainers": [{"symbol": "000566", "change_pct": 10.05}],
            "top_losers": [{"symbol": "002535", "change_pct": -10.12}],
            "top_traded": [{"symbol": "600519", "change_pct": 1.1}],
        },
        "crypto_market": {
            "btc": {"current_price": 62400, "market_cap": 1_250_000_000_000, "price_change_percentage_24h": -1.6},
            "eth": {"current_price": 3350, "market_cap": 201_000_000_000, "price_change_percentage_24h": -2.1},
            "stablecoin_growth": {"current": 313_870_000_000, "change_1d": 0.05},
            "daily_assets": {
                "UNI": {"symbol": "UNI", "market_cap": 4_500_000_000, "change_pct": 0.8, "price": 5.2},
            },
            "top100": [
                {"symbol": "BNB", "market_cap": 77_800_000_000, "change_pct": -0.7},
                {"symbol": "SOL", "market_cap": 68_500_000_000, "change_pct": 1.2},
                {"symbol": "HYPE", "market_cap": 12_300_000_000, "change_pct": -3.4},
            ],
            "top100_ranking": {
                "gainers": [{"symbol": "FET", "price_change_percentage_24h": 8.2}],
                "losers": [{"symbol": "PEPE", "price_change_percentage_24h": -9.1}],
            },
        },
        "rwa_market": {
            "tvl": {"value": 12_850_000_000, "change_1d": -0.2},
            "market_cap": {"value": 62_330_000_000, "change_24h": -1.1},
        },
        "daily_market": {
            "quotes": [
                {"symbol": "HSI", "name": "HSI", "price": 23890.12, "change_pct": 0.5},
                {"symbol": "GC=F", "name": "GOLD", "price": 2450.5, "change_pct": 1.2},
                {"symbol": "SI=F", "name": "SILVER", "price": 31.2, "change_pct": -0.4},
                {"symbol": "CL=F", "name": "USOIL", "price": 79.5, "change_pct": 0.8},
                {"symbol": "BZ=F", "name": "UKOIL", "price": 83.4, "change_pct": 0.9},
            ]
        },
        "wilson_view": "市场信号分散，短线更适合跟踪资金流与关键资产承接。",
    }


class FionaPhase3Test(unittest.TestCase):
    def test_schedule_contract(self) -> None:
        self.assertEqual(BRIEF_SCHEDULES[FionaBriefKind.MORNING].send_time.hour, 7)
        self.assertEqual(BRIEF_SCHEDULES[FionaBriefKind.EVENING].send_time.minute, 30)
        self.assertEqual(BRIEF_SCHEDULES[FionaBriefKind.MARKET_NEWS].send_time.hour, 0)
        self.assertEqual(BRIEF_SCHEDULES[FionaBriefKind.DAILY].send_time.hour, 22)
        self.assertEqual(BRIEF_SCHEDULES[FionaBriefKind.WEEKLY].send_time.hour, 21)

    def test_morning_and_evening_are_compact(self) -> None:
        events = sample_events()
        narratives = NarrativeEngine().build(events, now=NOW)
        morning = build_morning_brief(events, narratives, generated_at=NOW)
        evening = build_evening_brief(events, narratives, generated_at=NOW)

        self.assertLessEqual(len(morning.body_text()), 300)
        self.assertLessEqual(len(evening.body_text()), 300)
        self.assertIn("昨夜市场", morning.body_text())
        self.assertIn("今晚重点", evening.body_text())

    def test_market_news_uses_snapshot_heatmap_and_narratives(self) -> None:
        events = sample_events()
        narratives = NarrativeEngine().build(events, now=NOW)
        text = build_market_news_brief(events, narratives, snapshot=sample_snapshot(), generated_at=NOW).render_text()

        self.assertIn("Heat Map", text)
        self.assertIn("US Market：62/100", text)
        self.assertIn("Current Narrative", text)
        self.assertIn("Fiona's View", text)

    def test_daily_brief_contains_top_events_and_next_watch(self) -> None:
        events = sample_events()
        narratives = NarrativeEngine().build(events, now=NOW)
        text = build_daily_brief(events, narratives, snapshot=sample_snapshot(), generated_at=NOW).render_text()

        self.assertIn("Hi, investors, I'm your assistant fiona", text)
        self.assertIn("Important events", text)
        self.assertIn("Future note", text)
        self.assertIn("Crypto market", text)
        self.assertIn("Stock market", text)
        self.assertIn("BTC ETF资金流边际走弱", text)
        self.assertIn("wish you achieve your great ambition~", text)

    def test_daily_flow_section_has_complete_market_lines(self) -> None:
        events = sample_events()
        narratives = NarrativeEngine().build(events, now=NOW)
        text = build_daily_brief(events, narratives, snapshot=sample_snapshot(), generated_at=NOW).render_text()

        self.assertIn("RWA：$62.33B，24h -1.10%", text)
        self.assertIn("BTC：$1.25T，24h -1.60% 当前价格 $62,400.00，24h -1.60%", text)
        self.assertIn("BNB：$77.80B，24h -0.70% 当前价格 数据暂未返回，24h -0.70%", text)
        self.assertIn("SOL：$68.50B，24h +1.20% 当前价格 数据暂未返回，24h +1.20%", text)
        self.assertIn("HYPE：$12.30B，24h -3.40% 当前价格 数据暂未返回，24h -3.40%", text)
        self.assertIn("UNI：$4.50B，24h +0.80% 当前价格 $5.20，24h +0.80%", text)
        self.assertIn("DJI：38,834.86，24h +0.74%", text)
        self.assertIn("SPX：5,450.21，24h +0.30%", text)
        self.assertIn("HSI：23,890.12，24h +0.50%", text)
        self.assertIn("000001：4,110.81，24h +0.11%", text)
        self.assertIn("GOLD：2,450.50，24h +1.20%", text)
        self.assertIn("SILVER：31.20，24h -0.40%", text)
        self.assertIn("USOIL：79.50，24h +0.80%", text)
        self.assertIn("UKOIL：83.40，24h +0.90%", text)
        self.assertIn("US 成交榜：AAPL +0.40%", text)
        self.assertIn("CN 成交榜：600519 +1.10%", text)
        self.assertNotIn("$ B，24h  %", text)

    def test_weekly_brief_contains_false_narrative_watchlist(self) -> None:
        events = sample_events()
        narratives = NarrativeEngine().build(events, now=NOW)
        text = build_weekly_brief(events, narratives, snapshot=sample_snapshot(), generated_at=NOW).render_text()

        self.assertIn("False Narrative Watchlist", text)
        self.assertIn("短期Meme热点", text)

    def test_brief_builders_accept_event_generators(self) -> None:
        events = sample_events()
        narratives = NarrativeEngine().build(events, now=NOW)
        brief = build_daily_brief((item for item in events), narratives, generated_at=None)

        self.assertIn("BTC ETF资金流边际走弱", brief.render_text())


if __name__ == "__main__":
    unittest.main()
