from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.fiona_memory import DecisionMemoryRecord, FionaMemory
from app.fiona_narrative import NarrativeEngine, daily_narrative_brief, weekly_narrative_brief
from app.fiona_types import EventCategory, FionaEvent, MarketDirection, NarrativeStatus


NOW = datetime(2026, 6, 24, 12, 0, tzinfo=timezone.utc)


def event(**overrides) -> FionaEvent:
    base = {
        "event_id": "event_1",
        "created_at": NOW,
        "source": "unit_test",
        "category": EventCategory.OTHER,
        "title": "Market intelligence event",
        "what_happened": "市场出现新的情报信号。",
        "why_important": "该信号可能影响未来24小时的市场理解。",
        "affected_assets": ["BTC"],
        "watch_next": ["资金流是否确认", "关键资产是否同步反应"],
        "fiona_view": "该事件需要放入叙事框架中观察。",
        "impact_score": 8,
        "urgency_score": 6,
        "confidence_score": 9,
        "intelligence_score": 85,
        "market_direction": MarketDirection.NEUTRAL,
        "raw_data": {"mention_count": 1, "funds_score": 55},
    }
    base.update(overrides)
    return FionaEvent(**base)


class FionaPhase2Test(unittest.TestCase):
    def test_strong_ai_story_becomes_current_narrative(self) -> None:
        events = [
            event(
                event_id="ai_1",
                created_at=NOW - timedelta(hours=2),
                source="equity_feed",
                category=EventCategory.PRICE,
                title="NVDA and AMD lead AI valuation reset",
                what_happened="AI龙头估值出现同步修正。",
                affected_assets=["NVDA", "AMD", "QQQ"],
                intelligence_score=91,
                market_direction=MarketDirection.BEARISH,
                raw_data={"narratives": ["ai_valuation_reset"], "funds_score": 62},
            ),
            event(
                event_id="ai_2",
                created_at=NOW - timedelta(hours=8),
                source="macro_feed",
                category=EventCategory.MACRO,
                title="Higher yields pressure AI duration assets",
                what_happened="美债收益率上行压制AI久期资产估值。",
                affected_assets=["US10Y", "QQQ", "NVDA"],
                intelligence_score=93,
                market_direction=MarketDirection.BEARISH,
                raw_data={"narratives": ["ai_valuation_reset"], "funds_score": 58},
            ),
            event(
                event_id="ai_3",
                created_at=NOW - timedelta(days=1),
                source="sector_feed",
                category=EventCategory.OTHER,
                title="AI capex debate intensifies",
                what_happened="AI资本开支回报周期成为市场争论焦点。",
                affected_assets=["NVDA", "TSM", "AMD"],
                intelligence_score=88,
                market_direction=MarketDirection.BEARISH,
                raw_data={"narratives": ["ai_valuation_reset"], "funds_score": 60},
            ),
            event(
                event_id="ai_4",
                created_at=NOW - timedelta(days=2),
                source="earnings_feed",
                category=EventCategory.OTHER,
                title="Semiconductor earnings dispersion widens",
                what_happened="半导体财报分化加大，AI链估值开始重估。",
                affected_assets=["TSM", "AMD", "QQQ"],
                intelligence_score=89,
                market_direction=MarketDirection.BEARISH,
                raw_data={"narratives": ["ai_valuation_reset"], "funds_score": 65},
            ),
            event(
                event_id="ai_5",
                created_at=NOW - timedelta(days=2, hours=3),
                source="flow_feed",
                category=EventCategory.ETF,
                title="QQQ flow softens around AI leaders",
                what_happened="科技ETF资金围绕AI龙头出现降温。",
                affected_assets=["QQQ", "NVDA", "AMD"],
                intelligence_score=90,
                market_direction=MarketDirection.BEARISH,
                raw_data={"narratives": ["ai_valuation_reset"], "funds_score": 57},
            ),
        ]

        records = NarrativeEngine().build(events, now=NOW)
        ai_record = next(record for record in records if record.narrative_id == "ai_valuation_reset")

        self.assertEqual(ai_record.status, NarrativeStatus.CURRENT)
        self.assertGreaterEqual(ai_record.narrative_score, 80)
        self.assertEqual(ai_record.direction, MarketDirection.BEARISH)

    def test_meme_heat_with_weak_funds_is_false_narrative(self) -> None:
        events = [
            event(
                event_id=f"meme_{index}",
                created_at=NOW - timedelta(hours=index),
                source="social_feed" if index % 2 else "price_feed",
                category=EventCategory.PRICE,
                title="Short-term meme token heat accelerates",
                what_happened="Meme短线热度快速上升。",
                affected_assets=["PEPE", "MEME"],
                intelligence_score=48,
                market_direction=MarketDirection.BULLISH,
                raw_data={
                    "narratives": ["meme_short_term_hype"],
                    "funds_score": 22,
                    "meme_or_hype": True,
                    "mention_count": 1,
                },
            )
            for index in range(4)
        ]

        records = NarrativeEngine().build(events, now=NOW)
        meme_record = next(record for record in records if record.narrative_id == "meme_short_term_hype")
        weekly = weekly_narrative_brief(records)

        self.assertEqual(meme_record.status, NarrativeStatus.FALSE)
        self.assertIn("热度高但资金确认弱", "；".join(meme_record.false_reasons))
        self.assertIn("False Narrative Watchlist", weekly)
        self.assertIn("短期Meme热点", weekly)

    def test_old_story_inside_window_is_fading(self) -> None:
        records = NarrativeEngine().build(
            [
                event(
                    event_id="old_rwa",
                    created_at=NOW - timedelta(days=3),
                    source="rwa_feed",
                    category=EventCategory.RWA,
                    title="RWA project update",
                    what_happened="RWA项目更新后缺少后续资金确认。",
                    affected_assets=["RWA", "ONDO"],
                    intelligence_score=70,
                    raw_data={"narratives": ["rwa_institutional_adoption"], "funds_score": 52},
                )
            ],
            now=NOW,
        )

        self.assertEqual(records[0].status, NarrativeStatus.FADING)

    def test_daily_brief_uses_current_and_emerging_narratives(self) -> None:
        records = [
            event(
                event_id=f"ai_brief_{index}",
                created_at=NOW - timedelta(hours=index),
                source=f"source_{index}",
                category=EventCategory.MACRO if index == 0 else EventCategory.OTHER,
                title="AI valuation reset keeps driving market discussion",
                affected_assets=["NVDA", "QQQ", "BTC"],
                intelligence_score=92,
                market_direction=MarketDirection.BEARISH,
                raw_data={"narratives": ["ai_valuation_reset"], "funds_score": 63},
            )
            for index in range(4)
        ]
        narrative_records = NarrativeEngine().build(records, now=NOW)
        brief = daily_narrative_brief(narrative_records)

        self.assertIn("Current Narrative", brief)
        self.assertIn("Emerging Narrative", brief)
        self.assertIn("AI估值修正", brief)

    def test_memory_stores_narratives_and_decisions(self) -> None:
        memory = FionaMemory()
        records = memory.update_narratives(
            [
                event(
                    event_id="btc_etf",
                    source="etf_feed",
                    category=EventCategory.ETF,
                    title="BTC ETF outflow weakens risk appetite",
                    what_happened="BTC ETF资金流边际走弱。",
                    affected_assets=["BTC", "IBIT", "FBTC"],
                    intelligence_score=86,
                    market_direction=MarketDirection.BEARISH,
                    raw_data={"narratives": ["btc_etf_flow_weakness"], "funds_score": 28},
                )
            ],
            now=NOW,
        )
        memory.remember_decision(
            DecisionMemoryRecord(
                created_at=NOW,
                scope="Daily",
                direction=MarketDirection.BEARISH,
                conviction_score=72,
                reasoning="ETF资金流减弱，风险偏好缺少资金确认。",
                linked_event_ids=["btc_etf"],
                linked_narrative_ids=[records[0].narrative_id],
            )
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "fiona_memory.json"
            memory.save(path)
            saved = path.read_text(encoding="utf-8")

        self.assertIn("btc_etf_flow_weakness", memory.narrative_memory)
        self.assertEqual(len(memory.decision_memory), 1)
        self.assertIn("decision_memory", saved)


if __name__ == "__main__":
    unittest.main()
