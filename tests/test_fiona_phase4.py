from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from app.fiona_memory import FionaMemory
from app.fiona_runtime import build_payload, due_brief_kinds, resolve_send, run_once, should_push_alerts, snapshot_to_events
from app.fiona_types import FionaEvent, PushDecision


NOW = datetime(2026, 6, 28, 21, 0, tzinfo=timezone.utc)


def sample_snapshot() -> dict[str, object]:
    return {
        "title": "Wilson's Market News",
        "generated_at_display": "2026-06-28 21:00",
        "timezone": "UTC+8",
        "frequency": "每4小时更新一次",
        "heatmap": [
            {"key": "us", "label": "US Market", "score": 61, "status": "Neutral", "summary": "S&P 500 +0.20%"},
            {"key": "china", "label": "China Market", "score": 47, "status": "Neutral", "summary": "中证500 -0.30%"},
            {"key": "crypto", "label": "Crypto Market", "score": 38, "status": "Bearish", "summary": "BTC -1.70%"},
            {"key": "rwa", "label": "RWA Market", "score": 58, "status": "Neutral", "summary": "TVL 小幅流入"},
        ],
        "us_market": {
            "macro_policy": ["Fed speech reprices rate expectations"],
            "market_overview": ["S&P 500 5,450.21 (+0.20%)"],
            "ai_sector": ["NVDA +2.10%"],
            "primary": {"name": "S&P 500", "price": 5450.21, "change_pct": 0.2},
        },
        "china_market": {
            "policy_update": ["央行维持流动性稳定"],
            "market_overview": ["中证500 5,642.31 (-0.30%)"],
            "primary": {"name": "中证500", "price": 5642.31, "change_pct": -0.3},
        },
        "crypto_market": {
            "btc": {"current_price": 62400, "change_pct": -1.7},
            "eth": {"current_price": 3350, "change_pct": -2.2},
            "stablecoin_growth": {"current": 313_870_000_000, "change_1d": 0.05},
            "top100_ranking": {
                "gainers": [{"symbol": "FET", "change_pct": 8.2}],
                "losers": [{"symbol": "PEPE", "change_pct": -9.1}],
            },
        },
        "rwa_market": {
            "major_events": ["BlackRock BUIDL expands tokenized treasury access"],
            "tvl": {"value": 12_850_000_000},
            "market_cap": {"value": 62_330_000_000},
        },
        "wilson_view": "市场信号分散，短线更适合跟踪资金流与关键资产承接。",
        "errors": [],
    }


class FionaPhase4Test(unittest.TestCase):
    def test_due_brief_kinds_schedule_contract(self) -> None:
        self.assertIn("weekly", [item.value for item in due_brief_kinds(NOW)])
        self.assertEqual(due_brief_kinds(datetime(2026, 6, 24, 7, 30, tzinfo=timezone.utc))[0].value, "morning")
        self.assertEqual(due_brief_kinds(datetime(2026, 6, 24, 20, 30, tzinfo=timezone.utc))[0].value, "evening")
        self.assertEqual(due_brief_kinds(datetime(2026, 6, 24, 20, 36, tzinfo=timezone.utc))[0].value, "evening")
        self.assertEqual(due_brief_kinds(datetime(2026, 6, 24, 22, 30, tzinfo=timezone.utc))[0].value, "daily")
        self.assertEqual(due_brief_kinds(datetime(2026, 6, 24, 3, 0, tzinfo=timezone.utc)), [])

    def test_snapshot_to_events_creates_core_market_events(self) -> None:
        events = snapshot_to_events(sample_snapshot(), NOW)

        self.assertGreaterEqual(len(events), 5)
        self.assertTrue(all(isinstance(event, FionaEvent) for event in events))
        self.assertTrue(any(event.raw_data.get("symbol") == "BTC" for event in events))

    def test_rwa_event_ignores_unrelated_major_event_noise(self) -> None:
        snapshot = sample_snapshot()
        snapshot["rwa_market"] = {"major_events": ["Micron earnings preview drives Nasdaq discussion"]}
        events = snapshot_to_events(snapshot, NOW)
        rwa = next(event for event in events if event.category.value == "rwa")

        self.assertNotIn("Micron", rwa.what_happened)

    def test_build_payload_scores_alerts_and_daily_brief(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            payload = build_payload(sample_snapshot(), NOW, Path(tmpdir) / "memory.json", "daily")

        btc = next(event for event in payload.events if event.raw_data.get("symbol") == "BTC")
        self.assertEqual(btc.push_decision, PushDecision.SEND_NOW)
        self.assertTrue(payload.alert_messages)
        self.assertIsNotNone(payload.brief)
        self.assertIn("Fiona Daily", payload.brief.render_text())

    def test_run_once_writes_outputs_without_sending(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir)
            status = run_once(
                output_dir=output,
                brief="daily",
                send=False,
                timezone_name="UTC",
                snapshot_builder=lambda generated_at: sample_snapshot(),
            )

            latest_dir = Path(status["output_dir"])
            self.assertTrue((latest_dir / "fiona_telegram.md").exists())
            self.assertTrue((latest_dir / "fiona_events.json").exists())
            self.assertTrue((output / "fiona_memory.json").exists())
            self.assertTrue(status["ok"])

    def test_memory_can_load_runtime_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir)
            run_once(output_dir=output, brief="daily", send=False, timezone_name="UTC", snapshot_builder=lambda generated_at: sample_snapshot())
            memory = FionaMemory.load(output / "fiona_memory.json")

        self.assertTrue(memory.event_memory)
        self.assertTrue(memory.narrative_memory)
        self.assertTrue(memory.decision_memory)

    def test_alert_push_guard(self) -> None:
        self.assertFalse(should_push_alerts("auto"))
        self.assertTrue(should_push_alerts("alert"))
        self.assertFalse(should_push_alerts("daily"))

    def test_fiona_send_zero_overrides_send_flag(self) -> None:
        previous = __import__("os").environ.get("FIONA_SEND")
        try:
            __import__("os").environ["FIONA_SEND"] = "0"
            self.assertFalse(resolve_send(True))
            __import__("os").environ["FIONA_SEND"] = "1"
            self.assertTrue(resolve_send(False))
        finally:
            if previous is None:
                __import__("os").environ.pop("FIONA_SEND", None)
            else:
                __import__("os").environ["FIONA_SEND"] = previous


if __name__ == "__main__":
    unittest.main()
