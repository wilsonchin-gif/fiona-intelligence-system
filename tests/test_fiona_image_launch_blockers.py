from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch
from zoneinfo import ZoneInfo

from app.fiona_briefing import BRIEF_SCHEDULES, FionaBriefKind
from app.fiona_runtime import run_scheduler_cycle, validate_market_news_image_runtime
from app.fiona_scheduler import (
    ACTION_SEND,
    ACTION_SUPPRESS,
    STATUS_SKIPPED_EXPIRED,
    STATUS_SUPPRESSED_COLLISION,
    SchedulerLedger,
    ScheduledOccurrence,
    arbitrate_occurrences,
    occurrence_expired,
)


TZ = ZoneInfo("Asia/Hong_Kong")


def dt(value: str) -> datetime:
    return datetime.fromisoformat(value).replace(tzinfo=TZ)


def occurrence(
    kind: FionaBriefKind,
    scheduled: str,
    detected: str,
) -> ScheduledOccurrence:
    return ScheduledOccurrence.create(kind, dt(scheduled), dt(detected))


def decisions_for(
    occurrences: list[ScheduledOccurrence],
    now: str,
) -> dict[str, str]:
    return {
        decision.occurrence.brief_name: decision.action
        for decision in arbitrate_occurrences(occurrences, dt(now))
    }


def production_snapshot(_generated_at: datetime) -> dict[str, object]:
    return {
        "generated_at": "2026-08-04T16:00:00+08:00",
        "heatmap": [
            {"key": "us", "label": "US Market", "score": 54, "status": "Neutral", "summary": "S&P 500 -0.34%"},
            {"key": "china", "label": "China Market", "score": 58, "status": "Neutral", "summary": "中证500 +0.42%"},
            {"key": "crypto", "label": "Crypto Market", "score": 47, "status": "Neutral", "summary": "BTC +0.28%"},
            {"key": "rwa", "label": "RWA Market", "score": 66, "status": "Neutral", "summary": "TVL +0.31%"},
        ],
        "us_market": {
            "primary": {"name": "S&P 500", "price": 6376.21, "change_pct": -0.34},
            "macro_policy": ["美债收益率抬升，风险偏好边际降温。"],
        },
        "china_market": {"policy_update": ["政策与资金承接仍待确认。"]},
        "crypto_market": {
            "btc": {"current_price": 118420, "change_pct": 0.28},
            "eth": {"current_price": 3728.4, "change_pct": -0.61},
        },
        "rwa_market": {
            "tvl": {"value": 13_420_000_000, "change_1d": 0.31},
            "major_events": ["RWA机构采用继续推进。"],
        },
        "daily_market": {
            "quotes": [
                {"symbol": "^TNX", "price": 4.32, "change_pct": 0.06},
                {"symbol": "GC=F", "price": 2450.5, "change_pct": 1.2},
            ]
        },
        "wilson_view": (
            "当前市场处于中性震荡，宏观利率仍影响风险偏好，BTC价格修复尚未获得资金流确认。"
            "下一轮重点等待美元、美债与ETF流向是否形成一致信号。"
        ),
        "errors": [],
    }


class RecordingRunner:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def __call__(self, **kwargs):
        self.calls.append(str(kwargs["brief"]))
        return {"ok": True, "brief": kwargs["brief"]}


class FionaImageLaunchArbitrationTest(unittest.TestCase):
    def test_normal_market_news_beats_previous_daily_catch_up(self) -> None:
        decisions = decisions_for(
            [
                occurrence(FionaBriefKind.DAILY, "2026-08-03T22:30:00", "2026-08-04T00:05:00"),
                occurrence(FionaBriefKind.MARKET_NEWS, "2026-08-04T00:00:00", "2026-08-04T00:05:00"),
            ],
            "2026-08-04T00:05:00",
        )
        self.assertEqual(decisions, {"daily": ACTION_SUPPRESS, "market_news": ACTION_SEND})

    def test_normal_daily_beats_market_news_catch_up(self) -> None:
        decisions = decisions_for(
            [
                occurrence(FionaBriefKind.MARKET_NEWS, "2026-08-04T20:30:00", "2026-08-04T22:35:00"),
                occurrence(FionaBriefKind.DAILY, "2026-08-04T22:30:00", "2026-08-04T22:35:00"),
            ],
            "2026-08-04T22:35:00",
        )
        self.assertEqual(decisions["daily"], ACTION_SEND)
        self.assertEqual(decisions["market_news"], ACTION_SUPPRESS)

    def test_current_day_candidate_beats_previous_day_catch_up(self) -> None:
        decisions = decisions_for(
            [
                occurrence(FionaBriefKind.WEEKLY, "2026-08-02T21:00:00", "2026-08-03T01:00:00"),
                occurrence(FionaBriefKind.MARKET_NEWS, "2026-08-03T00:00:00", "2026-08-03T01:00:00"),
            ],
            "2026-08-03T01:00:00",
        )
        self.assertEqual(decisions["market_news"], ACTION_SEND)

    def test_two_normal_occurrences_use_semantic_priority(self) -> None:
        decisions = decisions_for(
            [
                occurrence(FionaBriefKind.EVENING, "2026-08-04T22:30:00", "2026-08-04T22:35:00"),
                occurrence(FionaBriefKind.DAILY, "2026-08-04T22:30:00", "2026-08-04T22:35:00"),
            ],
            "2026-08-04T22:35:00",
        )
        self.assertEqual(decisions["daily"], ACTION_SEND)

    def test_two_catch_ups_use_freshness_before_static_priority(self) -> None:
        decisions = decisions_for(
            [
                occurrence(FionaBriefKind.DAILY, "2026-08-04T20:30:00", "2026-08-04T22:41:00"),
                occurrence(FionaBriefKind.MARKET_NEWS, "2026-08-04T22:00:00", "2026-08-04T22:41:00"),
            ],
            "2026-08-04T22:41:00",
        )
        self.assertEqual(decisions["market_news"], ACTION_SEND)
        self.assertEqual(decisions["daily"], ACTION_SUPPRESS)

    def test_daily_catch_up_valid_before_cutoff_and_expired_after(self) -> None:
        valid = occurrence(FionaBriefKind.DAILY, "2026-08-04T22:30:00", "2026-08-04T23:45:00")
        expired = occurrence(FionaBriefKind.DAILY, "2026-08-04T22:30:00", "2026-08-05T00:31:00")
        self.assertFalse(occurrence_expired(valid, dt("2026-08-04T23:45:00")))
        self.assertTrue(occurrence_expired(expired, dt("2026-08-05T00:31:00")))

    def test_0048_runtime_expires_daily_before_arbitration(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir)
            ledger = SchedulerLedger(output / "fiona_scheduler_ledger.json")
            ledger.last_check_at = dt("2026-08-04T22:20:00")
            ledger.save()
            runner = RecordingRunner()
            status = run_scheduler_cycle(
                output_dir=output,
                send=False,
                timezone_name="Asia/Hong_Kong",
                now=dt("2026-08-05T00:48:00"),
                runner=runner,
            )
            saved = SchedulerLedger.load(output / "fiona_scheduler_ledger.json")
        self.assertEqual(runner.calls, ["market_news"])
        daily_entries = [entry for entry in saved.entries.values() if entry.get("brief_name") == "daily"]
        self.assertEqual(daily_entries[0]["status"], STATUS_SKIPPED_EXPIRED)
        self.assertEqual(sum(1 for item in status["arbitration"] if item["action"] == ACTION_SEND), 1)

    def test_monday_triple_collision_has_one_market_news_send(self) -> None:
        decisions = arbitrate_occurrences(
            [
                occurrence(FionaBriefKind.WEEKLY, "2026-08-02T21:00:00", "2026-08-03T01:00:00"),
                occurrence(FionaBriefKind.DAILY, "2026-08-02T22:30:00", "2026-08-03T01:00:00"),
                occurrence(FionaBriefKind.MARKET_NEWS, "2026-08-03T00:00:00", "2026-08-03T01:00:00"),
            ],
            dt("2026-08-03T01:00:00"),
        )
        sends = [item.occurrence.brief_name for item in decisions if item.action == ACTION_SEND]
        self.assertEqual(sends, ["market_news"])
        self.assertNotIn("defer", [item.action for item in decisions])

    def test_suppressed_occurrence_is_terminal_and_does_not_run_or_render(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = RecordingRunner()
            output = Path(tmpdir)
            first = run_scheduler_cycle(
                output_dir=output,
                send=False,
                timezone_name="Asia/Hong_Kong",
                now=dt("2026-08-04T22:35:00"),
                runner=runner,
            )
            second = run_scheduler_cycle(
                output_dir=output,
                send=False,
                timezone_name="Asia/Hong_Kong",
                now=dt("2026-08-04T22:40:00"),
                runner=runner,
            )
            ledger = SchedulerLedger.load(output / "fiona_scheduler_ledger.json")
        self.assertEqual(runner.calls, ["daily"])
        self.assertEqual(second["occurrence_results"], [])
        suppressed = [entry for entry in ledger.entries.values() if entry.get("status") == STATUS_SUPPRESSED_COLLISION]
        self.assertEqual(len(suppressed), 1)
        self.assertEqual(len([item for item in first["arbitration"] if item["action"] == ACTION_SEND]), 1)
        self.assertFalse(any(output.glob("fiona-market-news-*")))

    def test_seven_day_scheduler_simulation_delivers_each_fixed_occurrence_once(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir)
            runner = RecordingRunner()
            current = dt("2026-08-03T00:00:00")
            ledger = SchedulerLedger(output / "fiona_scheduler_ledger.json")
            ledger.last_check_at = current - timedelta(minutes=5)
            ledger.save()
            end = current + timedelta(days=7)
            while current <= end:
                run_scheduler_cycle(
                    output_dir=output,
                    send=False,
                    timezone_name="Asia/Hong_Kong",
                    now=current,
                    runner=runner,
                )
                current += timedelta(minutes=5)
        self.assertEqual(runner.calls.count("market_news"), 8)
        self.assertEqual(runner.calls.count("morning"), 7)
        self.assertEqual(runner.calls.count("evening"), 7)
        self.assertEqual(runner.calls.count("daily"), 7)
        self.assertEqual(runner.calls.count("weekly"), 1)

    def test_fixed_schedule_times_remain_unchanged(self) -> None:
        self.assertEqual(BRIEF_SCHEDULES[FionaBriefKind.MARKET_NEWS].send_time.isoformat(), "00:00:00")
        self.assertEqual(BRIEF_SCHEDULES[FionaBriefKind.MORNING].send_time.isoformat(), "07:30:00")
        self.assertEqual(BRIEF_SCHEDULES[FionaBriefKind.EVENING].send_time.isoformat(), "20:30:00")
        self.assertEqual(BRIEF_SCHEDULES[FionaBriefKind.DAILY].send_time.isoformat(), "22:30:00")
        self.assertEqual(BRIEF_SCHEDULES[FionaBriefKind.WEEKLY].send_time.isoformat(), "21:00:00")


class FionaProductionImageValidationTest(unittest.TestCase):
    def run_validation(self, output: Path) -> dict[str, object]:
        with patch("app.fiona_runtime.telegram_send_message") as text_sender:
            with patch("app.fiona_runtime.telegram_send_document") as document_sender:
                result = validate_market_news_image_runtime(
                    output_dir=output,
                    timezone_name="Asia/Hong_Kong",
                    snapshot_builder=production_snapshot,
                )
        text_sender.assert_not_called()
        document_sender.assert_not_called()
        return result

    def test_validation_uses_caption_rc_and_valid_png_without_telegram(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self.run_validation(Path(tmpdir))
        self.assertTrue(result["ok"], result)
        self.assertTrue(result["caption_success"])
        self.assertTrue(all(result["section_presence"].values()))
        self.assertEqual((result["png_width"], result["png_height"]), (1080, 1350))
        self.assertLess(result["png_size_bytes"], 1_500_000)
        self.assertEqual(result["cleanup_state"], "success")
        self.assertEqual(result["telegram_api_calls"], 0)
        self.assertFalse(result["temporary_path_exists_after_cleanup"])

    def test_validation_does_not_mutate_scheduler_ledger(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir)
            ledger_path = output / "fiona_scheduler_ledger.json"
            original = {"schema_version": "1.0", "last_check_at": None, "entries": {}}
            ledger_path.write_text(json.dumps(original), encoding="utf-8")
            before = ledger_path.read_bytes()
            result = self.run_validation(output)
            after = ledger_path.read_bytes()
        self.assertTrue(result["ok"], result)
        self.assertEqual(before, after)
        self.assertEqual(result["scheduler_ledger_mutations"], 0)


if __name__ == "__main__":
    unittest.main()
