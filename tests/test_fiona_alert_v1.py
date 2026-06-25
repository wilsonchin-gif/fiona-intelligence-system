from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.fiona_alert_runtime import process_alert_events, simulated_alert_events
from app.fiona_classifier import render_alert
from app.fiona_engine import FionaAlertEngine
from app.fiona_types import AlertLevel, EventCategory, FionaEvent, LifecycleStatus, MarketDirection, PushDecision


NOW = datetime(2026, 6, 25, 8, 0, tzinfo=timezone.utc)


class FionaAlertV1Test(unittest.TestCase):
    def test_simulated_events_trigger_expected_alerts_in_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            results = process_alert_events(
                simulated_alert_events(NOW),
                output_dir=Path(tmpdir),
                dry_run=True,
                enabled=True,
                send_func=lambda _: {"ok": True, "result": {"message_id": 1}},
            )

        self.assertEqual(len(results), 6)
        self.assertTrue(all(item.event.push_decision == PushDecision.SEND_NOW for item in results))
        self.assertTrue(all(not item.sent for item in results))
        self.assertTrue(all("Dry run=1" in item.reason for item in results))
        self.assertIn(AlertLevel.S, {item.event.level for item in results})
        self.assertIn(AlertLevel.A, {item.event.level for item in results})

    def test_alert_template_uses_required_sections(self) -> None:
        event = FionaAlertEngine().process(simulated_alert_events(NOW)[0])
        text = render_alert(event)

        for section in (
            "🚨 Fiona Alert",
            "【事件】",
            "【为什么重要】",
            "【影响资产】",
            "直接：",
            "【Fiona 判断】",
            "Direction：",
            "Conviction：",
            "Importance：",
            "【接下来确认】",
            "【Fiona’s View】",
            "Disclaimer：",
        ):
            self.assertIn(section, text)

    def test_forbidden_alert_terms_are_filtered(self) -> None:
        event = FionaAlertEngine().process(
            FionaEvent(
                event_id="bad_words",
                created_at=NOW,
                source="unit_test",
                category=EventCategory.RISK,
                title="Forbidden wording",
                what_happened="不要买入卖出加仓减仓，目标价必涨必跌。",
                why_important="测试过滤。",
                affected_assets=["BTC"],
                watch_next=["等待资金确认"],
                fiona_view="不做投资建议。",
                impact_score=10,
                urgency_score=10,
                confidence_score=9,
                market_direction=MarketDirection.BEARISH,
                raw_data={"major_risk_event": True},
            )
        )
        text = render_alert(event)

        for term in ("买入", "卖出", "加仓", "减仓", "目标价", "必涨", "必跌"):
            self.assertNotIn(term, text)

    def test_price_duplicate_enters_brief_pool_inside_cooldown(self) -> None:
        engine = FionaAlertEngine()
        first = engine.process(simulated_alert_events(NOW)[0])
        duplicate = simulated_alert_events(NOW + timedelta(minutes=20))[0]
        duplicate.event_family_id = first.event_family_id
        duplicate.dedupe_key = first.dedupe_key
        second = engine.process(duplicate)

        self.assertEqual(first.push_decision, PushDecision.SEND_NOW)
        self.assertEqual(second.lifecycle_status, LifecycleStatus.ONGOING)
        self.assertEqual(second.push_decision, PushDecision.BRIEF_POOL)

    def test_low_intelligence_event_is_c_level_and_ignored(self) -> None:
        event = FionaAlertEngine().process(
            FionaEvent(
                event_id="noise",
                created_at=NOW,
                source="unit_test",
                category=EventCategory.OTHER,
                title="Small headline",
                what_happened="普通标题波动。",
                why_important="影响有限。",
                affected_assets=["BTC"],
                watch_next=["等待下一轮确认"],
                fiona_view="低价值信息。",
                impact_score=1,
                urgency_score=1,
                confidence_score=3,
                market_direction=MarketDirection.NEUTRAL,
                raw_data={"novelty": 1, "repetition_penalty": 20},
            )
        )

        self.assertEqual(event.level, AlertLevel.C)
        self.assertEqual(event.push_decision, PushDecision.IGNORE)


if __name__ == "__main__":
    unittest.main()
