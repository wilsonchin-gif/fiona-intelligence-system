from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from app.fiona_engine import FionaAlertEngine
from app.fiona_types import EventCategory, FionaEvent, LifecycleStatus, MarketDirection, PushDecision


def event(**overrides):
    base = {
        "event_id": "event_1",
        "created_at": datetime(2026, 6, 24, 1, 0, tzinfo=timezone.utc),
        "source": "unit_test",
        "category": EventCategory.PRICE,
        "title": "BTC 1h move",
        "what_happened": "BTC 1小时下跌1.8%",
        "why_important": "跌破过去24小时关键支撑位，短线杠杆资金可能继续被动减仓。",
        "affected_assets": ["BTC", "ETH", "SOL"],
        "watch_next": ["62000是否失守", "ETF资金流是否同步恶化"],
        "fiona_view": "这是风险偏好变化信号，不是单纯价格噪音。",
        "impact_score": 8,
        "urgency_score": 9,
        "confidence_score": 9,
        "market_direction": MarketDirection.BEARISH,
        "raw_data": {
            "symbol": "BTC",
            "change_pct": -1.8,
            "support_break": True,
            "signals": {
                "price": "bearish",
                "funds": "outflow",
                "risk": "stress",
            },
            "narrative_strength": 8,
            "novelty": 7,
        },
        "evidence": ["support_break"],
        "cooldown_minutes": 60,
    }
    base.update(overrides)
    return FionaEvent(**base)


class FionaPhase1Test(unittest.TestCase):
    def test_macro_event_has_higher_intelligence_than_price_move(self) -> None:
        engine = FionaAlertEngine()
        price = engine.process(event(event_id="price_1"))
        macro = engine.process(
            event(
                event_id="macro_1",
                category=EventCategory.MACRO,
                title="Fed pauses rate cuts",
                what_happened="美联储主席暗示年内暂停降息。",
                why_important="利率路径可能被重新定价，影响美股估值、美元和加密风险偏好。",
                affected_assets=["SPY", "QQQ", "DXY", "BTC", "ETH"],
                watch_next=["美元和美债收益率反应", "风险资产是否继续降估值"],
                impact_score=10,
                urgency_score=6,
                confidence_score=10,
                raw_data={
                    "fed_rate_related": True,
                    "major_macro_data": True,
                    "narrative_strength": 20,
                    "novelty": 10,
                    "signals": {"macro": "bearish", "funds": "risk_off", "narrative": "bearish"},
                },
            )
        )

        self.assertGreater(macro.intelligence_score, price.intelligence_score)
        self.assertGreaterEqual(macro.intelligence_score, 90)

    def test_btc_price_hard_trigger_is_s_level_and_send_now(self) -> None:
        processed = FionaAlertEngine().process(event())

        self.assertEqual(processed.level.value, "S")
        self.assertEqual(processed.lifecycle_status, LifecycleStatus.NEW)
        self.assertEqual(processed.push_decision, PushDecision.SEND_NOW)
        self.assertGreaterEqual(processed.conviction_score, 80)

    def test_ongoing_duplicate_enters_brief_pool(self) -> None:
        engine = FionaAlertEngine()
        first = engine.process(event(event_id="btc_0900"))
        second = engine.process(
            event(
                event_id="btc_0930",
                created_at=first.created_at + timedelta(minutes=30),
                raw_data={**first.raw_data, "change_pct": -2.1},
            )
        )

        self.assertEqual(first.push_decision, PushDecision.SEND_NOW)
        self.assertEqual(second.lifecycle_status, LifecycleStatus.ONGOING)
        self.assertEqual(second.push_decision, PushDecision.BRIEF_POOL)

    def test_resolved_event_can_send_summary(self) -> None:
        engine = FionaAlertEngine()
        first = engine.process(event(event_id="btc_0900"))
        resolved = engine.process(
            event(
                event_id="btc_1200",
                created_at=first.created_at + timedelta(hours=3),
                what_happened="BTC重新站上关键支撑。",
                why_important="短线风险扩散暂时缓和，杠杆清算压力下降。",
                raw_data={**first.raw_data, "resolved": True, "change_pct": 0.6},
                evidence=["support_reclaimed"],
            )
        )

        self.assertEqual(resolved.lifecycle_status, LifecycleStatus.RESOLVED)
        self.assertEqual(resolved.push_decision, PushDecision.SEND_NOW)

    def test_low_conviction_when_only_price_signal_aligns(self) -> None:
        processed = FionaAlertEngine().process(
            event(
                raw_data={
                    "symbol": "BTC",
                    "change_pct": 1.6,
                    "support_break": False,
                    "signals": {"price": "bullish", "funds": "outflow", "macro": "risk_off"},
                    "narrative_strength": 3,
                    "novelty": 5,
                },
                market_direction=MarketDirection.BULLISH,
            )
        )

        self.assertLess(processed.conviction_score, 75)


if __name__ == "__main__":
    unittest.main()
