from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from app.fiona_briefing import BRIEF_SCHEDULES, FionaBriefKind
from app.fiona_contracts import Route, RouteDecision
from app.fiona_runtime import execute_scheduled_occurrence, push_text, run_scheduler, run_scheduler_cycle, scheduler_interval_minutes
from app.fiona_scheduler import (
    ACTION_DEFER,
    ACTION_SEND,
    ACTION_SUPPRESS,
    MAX_ATTEMPTS,
    STATUS_DEFERRED_COLLISION,
    STATUS_FAILED,
    STATUS_PARTIAL_DELIVERY,
    STATUS_RUNNING,
    STATUS_SKIPPED_EXPIRED,
    STATUS_SUCCESS,
    STATUS_SUPPRESSED_COLLISION,
    STATUS_UNKNOWN_DELIVERY_STATE,
    SchedulerLedger,
    ScheduledOccurrence,
    arbitrate_occurrences,
    can_execute_occurrence,
    clear_uncertain_occurrences,
    due_occurrences,
    remember_uncertain_occurrence,
    occurrence_id_for,
    scheduler_interval_minutes as scheduler_interval_minutes_core,
)
from unittest.mock import patch


TZ = ZoneInfo("Asia/Manila")


def dt(value: str) -> datetime:
    return datetime.fromisoformat(value).replace(tzinfo=TZ)


def occurrence(kind: FionaBriefKind, scheduled: str, detected: str | None = None) -> ScheduledOccurrence:
    scheduled_at = dt(scheduled)
    detected_at = dt(detected) if detected else scheduled_at
    return ScheduledOccurrence.create(kind, scheduled_at, detected_at)


class FakeRunner:
    def __init__(self, *, telegram_ok: bool = False, runtime_ok: bool = True) -> None:
        self.telegram_ok = telegram_ok
        self.runtime_ok = runtime_ok
        self.calls: list[str] = []

    def __call__(self, **kwargs):
        self.calls.append(str(kwargs["brief"]))
        status = {"ok": self.runtime_ok, "brief": kwargs["brief"]}
        if kwargs.get("send"):
            if self.telegram_ok:
                status["brief_push"] = {"ok": True, "message_ids": [12345], "errors": []}
            else:
                status["brief_push"] = {"ok": False, "message_ids": [], "errors": ["telegram failed"]}
        return status


class FionaSchedulerReliabilityTest(unittest.TestCase):
    def tearDown(self) -> None:
        clear_uncertain_occurrences()

    def test_normal_due_for_all_five_tasks(self) -> None:
        samples = [
            (FionaBriefKind.MARKET_NEWS, "2026-07-06T23:55:00", "2026-07-07T00:00:00"),
            (FionaBriefKind.MORNING, "2026-07-07T07:25:00", "2026-07-07T07:30:00"),
            (FionaBriefKind.EVENING, "2026-07-07T20:25:00", "2026-07-07T20:30:00"),
            (FionaBriefKind.DAILY, "2026-07-07T22:25:00", "2026-07-07T22:30:00"),
            (FionaBriefKind.WEEKLY, "2026-07-05T20:55:00", "2026-07-05T21:00:00"),
        ]
        for expected, previous, current in samples:
            with self.subTest(expected=expected.value):
                due = due_occurrences(dt(current), dt(previous), "Asia/Manila")
                self.assertEqual([item.brief_name for item in due], [expected.value])

    def test_first_startup_0602_has_no_expired_ledger_flood(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = FakeRunner()
            status = run_scheduler_cycle(output_dir=Path(tmpdir), send=False, timezone_name="Asia/Manila", now=dt("2026-07-07T06:02:00"), runner=runner)
        self.assertEqual(runner.calls, [])
        self.assertEqual(status["occurrence_results"], [])

    def test_first_startup_0740_catches_morning(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = FakeRunner()
            run_scheduler_cycle(output_dir=Path(tmpdir), send=False, timezone_name="Asia/Manila", now=dt("2026-07-07T07:40:00"), runner=runner)
        self.assertIn("morning", runner.calls)

    def test_first_startup_1400_does_not_send_expired_morning(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = FakeRunner()
            status = run_scheduler_cycle(output_dir=Path(tmpdir), send=False, timezone_name="Asia/Manila", now=dt("2026-07-07T14:00:00"), runner=runner)
        self.assertNotIn("morning", runner.calls)
        self.assertEqual(status["occurrence_results"], [])

    def test_first_startup_2035_catches_evening(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = FakeRunner()
            run_scheduler_cycle(output_dir=Path(tmpdir), send=False, timezone_name="Asia/Manila", now=dt("2026-07-07T20:35:00"), runner=runner)
        self.assertIn("evening", runner.calls)

    def test_restart_0745_recovers_morning(self) -> None:
        self.assertEqual([item.brief_name for item in due_occurrences(dt("2026-07-07T07:45:00"), dt("2026-07-07T07:20:00"), "Asia/Manila")], ["morning"])

    def test_restart_2050_recovers_evening(self) -> None:
        self.assertEqual([item.brief_name for item in due_occurrences(dt("2026-07-07T20:50:00"), dt("2026-07-07T20:25:00"), "Asia/Manila")], ["evening"])

    def test_restart_2310_recovers_daily(self) -> None:
        self.assertEqual([item.brief_name for item in due_occurrences(dt("2026-07-07T23:10:00"), dt("2026-07-07T22:20:00"), "Asia/Manila")], ["daily"])

    def test_sunday_restart_2120_recovers_weekly(self) -> None:
        self.assertEqual([item.brief_name for item in due_occurrences(dt("2026-07-05T21:20:00"), dt("2026-07-05T20:50:00"), "Asia/Manila")], ["weekly"])

    def test_monday_0200_weekly_is_expired(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = FakeRunner()
            status = run_scheduler_cycle(output_dir=Path(tmpdir), send=False, timezone_name="Asia/Manila", now=dt("2026-07-06T02:00:00"), runner=runner)
        self.assertNotIn("weekly", runner.calls)
        self.assertEqual(status["occurrence_results"], [])

    def test_midnight_boundary_detects_market_news(self) -> None:
        due = due_occurrences(dt("2026-07-08T00:05:00"), dt("2026-07-07T23:55:00"), "Asia/Manila")
        self.assertEqual([item.brief_name for item in due], ["market_news"])

    def test_sunday_boundary_detects_weekly(self) -> None:
        due = due_occurrences(dt("2026-07-05T21:05:00"), dt("2026-07-05T20:55:00"), "Asia/Manila")
        self.assertEqual([item.brief_name for item in due], ["weekly"])

    def test_existing_success_prevents_duplicate_resend(self) -> None:
        occ = occurrence(FionaBriefKind.MORNING, "2026-07-07T07:30:00", "2026-07-07T07:40:00")
        ledger = SchedulerLedger(Path("unused.json"))
        ledger.ensure_entry(occ)
        ledger.mark_success(occ, dt("2026-07-07T07:41:00"))
        self.assertEqual(can_execute_occurrence(ledger, occ, dt("2026-07-07T07:45:00")), (False, "duplicate_success"))

    def test_failed_allows_bounded_retry(self) -> None:
        occ = occurrence(FionaBriefKind.MORNING, "2026-07-07T07:30:00", "2026-07-07T07:40:00")
        ledger = SchedulerLedger(Path("unused.json"))
        ledger.mark_running(occ, dt("2026-07-07T07:40:00"))
        ledger.mark_failed(occ, dt("2026-07-07T07:41:00"), "telegram failed")
        self.assertEqual(can_execute_occurrence(ledger, occ, dt("2026-07-07T07:45:00")), (True, "failed_retry"))

    def test_retry_max_attempts_blocks_resend(self) -> None:
        occ = occurrence(FionaBriefKind.MORNING, "2026-07-07T07:30:00", "2026-07-07T07:40:00")
        ledger = SchedulerLedger(Path("unused.json"))
        ledger.ensure_entry(occ)["attempt_count"] = MAX_ATTEMPTS
        ledger.ensure_entry(occ)["status"] = STATUS_FAILED
        self.assertEqual(can_execute_occurrence(ledger, occ, dt("2026-07-07T07:45:00")), (False, "retry_limit_reached"))

    def test_retry_expired_is_skipped(self) -> None:
        occ = occurrence(FionaBriefKind.MORNING, "2026-07-07T07:30:00", "2026-07-07T14:00:00")
        ledger = SchedulerLedger(Path("unused.json"))
        ledger.ensure_entry(occ)["attempt_count"] = 1
        ledger.ensure_entry(occ)["status"] = STATUS_FAILED
        self.assertEqual(can_execute_occurrence(ledger, occ, dt("2026-07-07T14:00:00")), (False, STATUS_SKIPPED_EXPIRED))

    def test_suppressed_occurrence_is_not_retried(self) -> None:
        occ = occurrence(FionaBriefKind.EVENING, "2026-07-07T20:30:00", "2026-07-07T22:35:00")
        winner = occurrence(FionaBriefKind.DAILY, "2026-07-07T22:30:00", "2026-07-07T22:35:00")
        ledger = SchedulerLedger(Path("unused.json"))
        ledger.mark_suppressed_collision(occ, winner.occurrence_id, "daily collision", dt("2026-07-07T22:35:00"))
        self.assertEqual(can_execute_occurrence(ledger, occ, dt("2026-07-07T22:40:00")), (False, STATUS_SUPPRESSED_COLLISION))

    def test_stale_running_can_retry(self) -> None:
        occ = occurrence(FionaBriefKind.MORNING, "2026-07-07T07:30:00", "2026-07-07T08:10:00")
        ledger = SchedulerLedger(Path("unused.json"))
        ledger.mark_running(occ, dt("2026-07-07T07:31:00"))
        self.assertEqual(can_execute_occurrence(ledger, occ, dt("2026-07-07T08:10:00")), (True, "stale_running_retry"))

    def test_stale_running_uncertain_does_not_retry(self) -> None:
        occ = occurrence(FionaBriefKind.MORNING, "2026-07-07T07:30:00", "2026-07-07T08:10:00")
        ledger = SchedulerLedger(Path("unused.json"))
        ledger.mark_running(occ, dt("2026-07-07T07:31:00"))
        remember_uncertain_occurrence(occ.occurrence_id)
        self.assertEqual(can_execute_occurrence(ledger, occ, dt("2026-07-07T08:10:00")), (False, STATUS_UNKNOWN_DELIVERY_STATE))

    def test_stale_running_partial_does_not_retry(self) -> None:
        occ = occurrence(FionaBriefKind.MORNING, "2026-07-07T07:30:00", "2026-07-07T08:10:00")
        ledger = SchedulerLedger(Path("unused.json"))
        ledger.mark_partial_delivery(occ, dt("2026-07-07T07:45:00"), "chunk failed")
        self.assertEqual(can_execute_occurrence(ledger, occ, dt("2026-07-07T08:10:00")), (False, STATUS_PARTIAL_DELIVERY))

    def test_non_stale_running_blocks_retry(self) -> None:
        occ = occurrence(FionaBriefKind.MORNING, "2026-07-07T07:30:00", "2026-07-07T07:40:00")
        ledger = SchedulerLedger(Path("unused.json"))
        ledger.mark_running(occ, dt("2026-07-07T07:35:00"))
        self.assertEqual(can_execute_occurrence(ledger, occ, dt("2026-07-07T07:40:00")), (False, "running_not_stale"))

    def test_malformed_ledger_loads_with_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "ledger.json"
            path.write_text("{bad", encoding="utf-8")
            ledger = SchedulerLedger.load(path)
        self.assertIsNotNone(ledger.load_error)
        self.assertEqual(ledger.entries, {})

    def test_missing_ledger_loads_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            ledger = SchedulerLedger.load(Path(tmpdir) / "missing.json")
        self.assertIsNone(ledger.load_error)
        self.assertEqual(ledger.entries, {})

    def test_ledger_write_failure_after_telegram_success_marks_unknown(self) -> None:
        occ = occurrence(FionaBriefKind.DAILY, "2026-07-07T22:30:00", "2026-07-07T22:35:00")
        ledger = SchedulerLedger(Path("unused.json"))
        save_calls = {"count": 0}

        def flaky_save() -> None:
            save_calls["count"] += 1
            if save_calls["count"] >= 2:
                raise OSError("disk unavailable")

        ledger.save = flaky_save  # type: ignore[method-assign]
        result = execute_scheduled_occurrence(occ, ledger, Path("."), True, "Asia/Manila", FakeRunner(telegram_ok=True))
        self.assertEqual(result["status"], STATUS_UNKNOWN_DELIVERY_STATE)
        self.assertEqual(ledger.entry_for(occ)["status"], STATUS_UNKNOWN_DELIVERY_STATE)

    def test_telegram_failure_records_failed(self) -> None:
        occ = occurrence(FionaBriefKind.DAILY, "2026-07-07T22:30:00", "2026-07-07T22:35:00")
        ledger = SchedulerLedger(Path("unused.json"))
        ledger.save = lambda: None  # type: ignore[method-assign]
        result = execute_scheduled_occurrence(occ, ledger, Path("."), True, "Asia/Manila", FakeRunner(telegram_ok=False))
        self.assertEqual(result["status"], "failed")
        self.assertEqual(ledger.entry_for(occ)["status"], STATUS_FAILED)

    def test_telegram_success_records_success(self) -> None:
        occ = occurrence(FionaBriefKind.DAILY, "2026-07-07T22:30:00", "2026-07-07T22:35:00")
        ledger = SchedulerLedger(Path("unused.json"))
        ledger.save = lambda: None  # type: ignore[method-assign]
        result = execute_scheduled_occurrence(occ, ledger, Path("."), True, "Asia/Manila", FakeRunner(telegram_ok=True))
        self.assertEqual(result["status"], STATUS_SUCCESS)
        self.assertEqual(ledger.entry_for(occ)["status"], STATUS_SUCCESS)

    def test_partial_telegram_delivery_records_partial_and_no_retry(self) -> None:
        occ = occurrence(FionaBriefKind.DAILY, "2026-07-07T22:30:00", "2026-07-07T22:35:00")
        ledger = SchedulerLedger(Path("unused.json"))
        ledger.save = lambda: None  # type: ignore[method-assign]

        def runner(**kwargs):
            return {
                "ok": True,
                "brief_push": {
                    "ok": False,
                    "delivery_status": STATUS_PARTIAL_DELIVERY,
                    "message_ids": [1, 2],
                    "successful_chunks": [1, 2],
                    "failed_chunks": [3],
                    "errors": ["chunk 3 failed"],
                },
            }

        result = execute_scheduled_occurrence(occ, ledger, Path("."), True, "Asia/Manila", runner)
        self.assertEqual(result["status"], STATUS_PARTIAL_DELIVERY)
        self.assertEqual(ledger.entry_for(occ)["status"], STATUS_PARTIAL_DELIVERY)
        self.assertEqual(can_execute_occurrence(ledger, occ, dt("2026-07-07T22:40:00")), (False, STATUS_PARTIAL_DELIVERY))

    def test_secondary_uncertain_journal_written_after_success_write_failure(self) -> None:
        occ = occurrence(FionaBriefKind.DAILY, "2026-07-07T22:30:00", "2026-07-07T22:35:00")
        ledger = SchedulerLedger(Path("unused.json"))
        save_calls = {"count": 0}

        def flaky_save() -> None:
            save_calls["count"] += 1
            if save_calls["count"] >= 2:
                raise OSError("disk unavailable")

        with tempfile.TemporaryDirectory() as tmpdir:
            ledger.save = flaky_save  # type: ignore[method-assign]
            result = execute_scheduled_occurrence(occ, ledger, Path(tmpdir), True, "Asia/Manila", FakeRunner(telegram_ok=True))
            journal = Path(tmpdir) / "fiona_scheduler_delivery_uncertain.log"
            self.assertTrue(journal.exists())
        self.assertEqual(result["status"], STATUS_UNKNOWN_DELIVERY_STATE)
        self.assertEqual(can_execute_occurrence(ledger, occ, dt("2026-07-07T22:40:00")), (False, STATUS_UNKNOWN_DELIVERY_STATE))

    def test_secondary_journal_failure_still_marks_uncertain_in_memory(self) -> None:
        occ = occurrence(FionaBriefKind.DAILY, "2026-07-07T22:30:00", "2026-07-07T22:35:00")
        ledger = SchedulerLedger(Path("unused.json"))
        save_calls = {"count": 0}

        def flaky_save() -> None:
            save_calls["count"] += 1
            if save_calls["count"] >= 2:
                raise OSError("disk unavailable")

        ledger.save = flaky_save  # type: ignore[method-assign]
        with patch("app.fiona_runtime.write_uncertain_delivery_journal", side_effect=OSError("journal failed")):
            result = execute_scheduled_occurrence(occ, ledger, Path("."), True, "Asia/Manila", FakeRunner(telegram_ok=True))
        self.assertEqual(result["status"], STATUS_UNKNOWN_DELIVERY_STATE)
        self.assertEqual(can_execute_occurrence(ledger, occ, dt("2026-07-07T22:40:00")), (False, STATUS_UNKNOWN_DELIVERY_STATE))

    def test_invalid_interval_values_fallback_to_default(self) -> None:
        self.assertEqual(scheduler_interval_minutes_core(0), 5)
        self.assertEqual(scheduler_interval_minutes_core(-1), 5)
        self.assertEqual(scheduler_interval_minutes_core("not-a-number"), 5)
        self.assertEqual(scheduler_interval_minutes(0), 5)

    def test_interval_ignores_alert_interval(self) -> None:
        env = {"FIONA_ALERT_INTERVAL_MINUTES": "1"}
        self.assertEqual(scheduler_interval_minutes_core(env=env), 5)

    def test_railway_env_240_override_resolution(self) -> None:
        self.assertEqual(scheduler_interval_minutes_core(env={"WILSON_INTERVAL_MINUTES": "240"}), 240)

    def test_recommended_env_5_resolution(self) -> None:
        self.assertEqual(scheduler_interval_minutes_core(env={"WILSON_INTERVAL_MINUTES": "5"}), 5)

    def test_timezone_aware_occurrence_id(self) -> None:
        occ_id = occurrence_id_for(FionaBriefKind.MORNING, dt("2026-07-07T07:30:00"))
        self.assertEqual(occ_id, "morning:2026-07-07T07:30:00+08:00")

    def test_7_day_continuous_simulation(self) -> None:
        start = dt("2026-07-06T00:00:00")
        current = start
        last_check = start - timedelta(minutes=5)
        end = start + timedelta(days=7)
        counts: dict[str, int] = {}
        while current <= end:
            for occ in due_occurrences(current, last_check, "Asia/Manila"):
                counts[occ.brief_name] = counts.get(occ.brief_name, 0) + 1
            last_check = current
            current += timedelta(minutes=5)
        self.assertEqual(counts["market_news"], 8)
        self.assertEqual(counts["morning"], 7)
        self.assertEqual(counts["evening"], 7)
        self.assertEqual(counts["daily"], 7)
        self.assertEqual(counts["weekly"], 1)

    def test_restart_simulation_persists_last_check(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir)
            first_runner = FakeRunner()
            run_scheduler_cycle(output_dir=output, send=False, timezone_name="Asia/Manila", now=dt("2026-07-07T07:20:00"), runner=first_runner)
            second_runner = FakeRunner()
            run_scheduler_cycle(output_dir=output, send=False, timezone_name="Asia/Manila", now=dt("2026-07-07T07:45:00"), runner=second_runner)
        self.assertEqual(first_runner.calls, [])
        self.assertEqual(second_runner.calls, ["morning"])

    def test_restart_without_ledger_limitation(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            first_runner = FakeRunner()
            run_scheduler_cycle(output_dir=Path(tmpdir) / "a", send=False, timezone_name="Asia/Manila", now=dt("2026-07-07T07:40:00"), runner=first_runner)
            second_runner = FakeRunner()
            run_scheduler_cycle(output_dir=Path(tmpdir) / "b", send=False, timezone_name="Asia/Manila", now=dt("2026-07-07T07:45:00"), runner=second_runner)
        self.assertEqual(first_runner.calls, ["morning"])
        self.assertEqual(second_runner.calls, ["morning"])

    def test_first_startup_uses_bounded_lookback(self) -> None:
        morning = [item for item in due_occurrences(dt("2026-07-07T07:40:00"), None, "Asia/Manila") if item.brief_name == "morning"]
        stale_morning = [item for item in due_occurrences(dt("2026-07-07T14:00:00"), None, "Asia/Manila") if item.brief_name == "morning"]
        self.assertEqual(len(morning), 1)
        self.assertEqual(len(stale_morning), 0)

    def test_evening_catchup_daily_normal_collision(self) -> None:
        due = [
            occurrence(FionaBriefKind.EVENING, "2026-07-07T20:30:00", "2026-07-07T22:35:00"),
            occurrence(FionaBriefKind.DAILY, "2026-07-07T22:30:00", "2026-07-07T22:35:00"),
        ]
        decisions = {item.occurrence.brief_name: item.action for item in arbitrate_occurrences(due, dt("2026-07-07T22:35:00"))}
        self.assertEqual(decisions["daily"], ACTION_SEND)
        self.assertEqual(decisions["evening"], ACTION_SUPPRESS)

    def test_evening_before_daily_due_sends_evening(self) -> None:
        due = [occurrence(FionaBriefKind.EVENING, "2026-07-07T20:30:00", "2026-07-07T22:20:00")]
        decisions = arbitrate_occurrences(due, dt("2026-07-07T22:20:00"))
        self.assertEqual(decisions[0].action, ACTION_SEND)

    def test_evening_daily_catchup_collision_single_send(self) -> None:
        due = [
            occurrence(FionaBriefKind.EVENING, "2026-07-07T20:30:00", "2026-07-07T23:10:00"),
            occurrence(FionaBriefKind.DAILY, "2026-07-07T22:30:00", "2026-07-07T23:10:00"),
        ]
        decisions = arbitrate_occurrences(due, dt("2026-07-07T23:10:00"))
        self.assertEqual(sum(1 for item in decisions if item.action == ACTION_SEND), 1)
        self.assertEqual([item.occurrence.brief_name for item in decisions if item.action == ACTION_SEND], ["daily"])

    def test_weekly_daily_market_triple_collision_no_triple_push(self) -> None:
        due = [
            occurrence(FionaBriefKind.WEEKLY, "2026-07-05T21:00:00", "2026-07-06T01:00:00"),
            occurrence(FionaBriefKind.DAILY, "2026-07-05T22:30:00", "2026-07-06T01:00:00"),
            occurrence(FionaBriefKind.MARKET_NEWS, "2026-07-06T00:00:00", "2026-07-06T01:00:00"),
        ]
        decisions = arbitrate_occurrences(due, dt("2026-07-06T01:00:00"))
        self.assertEqual(sum(1 for item in decisions if item.action == ACTION_SEND), 1)
        self.assertEqual([item.occurrence.brief_name for item in decisions if item.action == ACTION_SEND], ["weekly"])

    def test_multiple_due_independent_tasks_both_send(self) -> None:
        due = [
            occurrence(FionaBriefKind.MARKET_NEWS, "2026-07-07T00:00:00", "2026-07-07T07:30:00"),
            occurrence(FionaBriefKind.MORNING, "2026-07-07T07:30:00", "2026-07-07T07:30:00"),
        ]
        decisions = arbitrate_occurrences(due, dt("2026-07-07T07:30:00"))
        self.assertEqual([item.action for item in decisions], [ACTION_SEND, ACTION_SEND])

    def test_market_news_defer_when_weekly_has_higher_value(self) -> None:
        due = [
            occurrence(FionaBriefKind.WEEKLY, "2026-07-05T21:00:00", "2026-07-06T00:05:00"),
            occurrence(FionaBriefKind.MARKET_NEWS, "2026-07-06T00:00:00", "2026-07-06T00:05:00"),
        ]
        decisions = {item.occurrence.brief_name: item.action for item in arbitrate_occurrences(due, dt("2026-07-06T00:05:00"))}
        self.assertEqual(decisions["weekly"], ACTION_SEND)
        self.assertEqual(decisions["market_news"], ACTION_DEFER)

    def test_suppression_ledger_audit(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = FakeRunner()
            status = run_scheduler_cycle(output_dir=Path(tmpdir), send=False, timezone_name="Asia/Manila", now=dt("2026-07-07T22:35:00"), runner=runner)
            ledger = SchedulerLedger.load(Path(tmpdir) / "fiona_scheduler_ledger.json")
        self.assertEqual(runner.calls, ["daily"])
        suppressed = [entry for entry in ledger.entries.values() if entry.get("status") == STATUS_SUPPRESSED_COLLISION]
        self.assertTrue(suppressed)
        self.assertTrue(suppressed[0].get("suppressed_by_occurrence_id"))
        self.assertTrue(suppressed[0].get("suppression_reason"))

    def test_first_startup_required_times_no_expired_flood(self) -> None:
        cases = {
            "2026-07-07T00:05:00": ["market_news"],
            "2026-07-07T07:40:00": ["morning"],
            "2026-07-07T14:00:00": [],
            "2026-07-07T20:35:00": ["evening"],
            "2026-07-07T23:10:00": ["daily"],
            "2026-07-06T01:00:00": ["weekly"],
        }
        for timestamp, expected in cases.items():
            with self.subTest(timestamp=timestamp):
                with tempfile.TemporaryDirectory() as tmpdir:
                    runner = FakeRunner()
                    status = run_scheduler_cycle(output_dir=Path(tmpdir), send=False, timezone_name="Asia/Manila", now=dt(timestamp), runner=runner)
                self.assertEqual(runner.calls, expected)
                self.assertFalse(any(result["status"] == STATUS_SKIPPED_EXPIRED for result in status["occurrence_results"]))

    def test_task_exception_isolation(self) -> None:
        calls: list[str] = []

        def runner(**kwargs):
            calls.append(str(kwargs["brief"]))
            if kwargs["brief"] == "evening":
                raise RuntimeError("render failed")
            return {"ok": True}

        with tempfile.TemporaryDirectory() as tmpdir:
            status = run_scheduler_cycle(output_dir=Path(tmpdir), send=False, timezone_name="Asia/Manila", now=dt("2026-07-07T22:35:00"), runner=runner)
        self.assertIn("daily", calls)
        self.assertTrue(any(result["brief_name"] == "daily" for result in status["occurrence_results"]))

    def test_top_level_scheduler_exception_continues(self) -> None:
        calls = {"count": 0}
        sleeps: list[float] = []

        def cycle_runner(**kwargs):
            calls["count"] += 1
            if calls["count"] == 1:
                raise RuntimeError("cycle exploded")
            return {"ok": True}

        run_scheduler(max_cycles=2, interval_minutes=5, cycle_runner=cycle_runner, sleep_fn=sleeps.append)
        self.assertEqual(calls["count"], 2)
        self.assertEqual(sleeps, [60])

    def test_push_text_full_chunk_success(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("app.fiona_runtime.split_message", return_value=["a", "b"]):
                with patch("app.fiona_runtime.telegram_send_message", side_effect=[{"result": {"message_id": 1}}, {"result": {"message_id": 2}}]):
                    result = push_text("body", Path(tmpdir) / "tg.log", "scope")
        self.assertTrue(result["ok"])
        self.assertEqual(result["delivery_status"], "success")
        self.assertEqual(result["message_ids"], [1, 2])

    def test_push_text_first_chunk_fail(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("app.fiona_runtime.split_message", return_value=["a", "b"]):
                with patch("app.fiona_runtime.telegram_send_message", side_effect=[RuntimeError("fail"), {"result": {"message_id": 2}}]):
                    result = push_text("body", Path(tmpdir) / "tg.log", "scope")
        self.assertFalse(result["ok"])
        self.assertEqual(result["delivery_status"], STATUS_PARTIAL_DELIVERY)
        self.assertEqual(result["successful_chunks"], [2])
        self.assertEqual(result["failed_chunks"], [1])

    def test_push_text_middle_chunk_fail(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("app.fiona_runtime.split_message", return_value=["a", "b", "c"]):
                with patch("app.fiona_runtime.telegram_send_message", side_effect=[{"result": {"message_id": 1}}, RuntimeError("fail"), {"result": {"message_id": 3}}]):
                    result = push_text("body", Path(tmpdir) / "tg.log", "scope")
        self.assertEqual(result["delivery_status"], STATUS_PARTIAL_DELIVERY)
        self.assertEqual(result["successful_chunks"], [1, 3])
        self.assertEqual(result["failed_chunks"], [2])

    def test_push_text_final_chunk_fail(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("app.fiona_runtime.split_message", return_value=["a", "b", "c"]):
                with patch("app.fiona_runtime.telegram_send_message", side_effect=[{"result": {"message_id": 1}}, {"result": {"message_id": 2}}, RuntimeError("fail")]):
                    result = push_text("body", Path(tmpdir) / "tg.log", "scope")
        self.assertEqual(result["delivery_status"], STATUS_PARTIAL_DELIVERY)
        self.assertEqual(result["successful_chunks"], [1, 2])
        self.assertEqual(result["failed_chunks"], [3])

    def test_push_text_all_chunks_fail(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("app.fiona_runtime.split_message", return_value=["a"]):
                with patch("app.fiona_runtime.telegram_send_message", side_effect=RuntimeError("fail")):
                    result = push_text("body", Path(tmpdir) / "tg.log", "scope")
        self.assertFalse(result["ok"])
        self.assertEqual(result["delivery_status"], "failed")

    def test_multi_route_contract_unaffected(self) -> None:
        decisions = [
            RouteDecision(route=Route.MORNING, reason="startup catch-up", confidence=0.8, decided_at=dt("2026-07-07T07:40:00")),
            RouteDecision(route=Route.DAILY, reason="brief pool", confidence=0.7, decided_at=dt("2026-07-07T07:40:00")),
        ]
        self.assertEqual([decision.route for decision in decisions], [Route.MORNING, Route.DAILY])

    def test_existing_five_task_times_unchanged(self) -> None:
        self.assertEqual(BRIEF_SCHEDULES[FionaBriefKind.MARKET_NEWS].send_time.isoformat(timespec="minutes"), "00:00")
        self.assertEqual(BRIEF_SCHEDULES[FionaBriefKind.MORNING].send_time.isoformat(timespec="minutes"), "07:30")
        self.assertEqual(BRIEF_SCHEDULES[FionaBriefKind.EVENING].send_time.isoformat(timespec="minutes"), "20:30")
        self.assertEqual(BRIEF_SCHEDULES[FionaBriefKind.DAILY].send_time.isoformat(timespec="minutes"), "22:30")
        self.assertEqual(BRIEF_SCHEDULES[FionaBriefKind.WEEKLY].send_time.isoformat(timespec="minutes"), "21:00")


if __name__ == "__main__":
    unittest.main()
