from __future__ import annotations

import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

from app.fiona_briefing import (
    BRIEF_SCHEDULES,
    FionaBriefKind,
    build_daily_brief,
    build_evening_brief,
    build_morning_brief,
    build_weekly_brief,
)
from app.fiona_card_renderer import render_market_news_card_ios
from app.fiona_classifier import render_alert
from app.fiona_locale import (
    OutputLocale,
    SHARED_EN_US_TERMINOLOGY,
    contains_cjk,
    finalize_user_visible_text,
    format_display_timestamp,
)
from app.fiona_market_news_delivery import (
    TelegramMediaMode,
    parse_telegram_media_mode,
    validate_market_news_png,
)
from app.fiona_market_news_image import build_market_news_view_model, compose_market_news_caption
from app.fiona_runtime import run_once
from app.fiona_scheduler import ACTION_DEFER, ACTION_SEND, ACTION_SUPPRESS
from app.fiona_surface_validation import (
    VALIDATION_TIME,
    build_en_us_user_surface_outputs,
    en_us_fixture_events,
    en_us_fixture_narratives,
    en_us_fixture_snapshot,
    validate_en_us_user_surfaces_runtime,
)


def full_outputs() -> dict[str, str]:
    return build_en_us_user_surface_outputs(missing=False)


def missing_outputs() -> dict[str, str]:
    return build_en_us_user_surface_outputs(missing=True)


class MorningSurfaceTest(unittest.TestCase):
    def test_01_en_us_headings(self) -> None:
        text = full_outputs()["morning"]
        for heading in ("[OVERNIGHT MARKET]", "[TODAY'S WATCH]", "[TODAY'S KEY EVENTS]", "[RISK RADAR]"):
            self.assertIn(heading, text)

    def test_02_no_cjk(self) -> None:
        self.assertFalse(contains_cjk(full_outputs()["morning"]))

    def test_03_english_fiona_view(self) -> None:
        text = full_outputs()["morning"]
        self.assertIn("[FIONA'S VIEW]", text)
        self.assertIn("Before markets become active", text)

    def test_04_english_missing_data(self) -> None:
        text = missing_outputs()["morning"]
        self.assertIn("No material change.", text)
        self.assertNotIn("暂无", text)

    def test_05_english_disclaimer(self) -> None:
        self.assertTrue(full_outputs()["morning"].endswith("For informational purposes only. Not investment advice."))


class EveningSurfaceTest(unittest.TestCase):
    def test_06_en_us_headings(self) -> None:
        text = full_outputs()["evening"]
        for heading in ("[TONIGHT'S FOCUS]", "[NIGHT RISK RADAR]", "[ETF / MACRO / CRYPTO]"):
            self.assertIn(heading, text)

    def test_07_no_cjk(self) -> None:
        self.assertFalse(contains_cjk(full_outputs()["evening"]))

    def test_08_english_narrative(self) -> None:
        self.assertIn("Macro Liquidity Repricing", full_outputs()["evening"])

    def test_09_english_disclaimer(self) -> None:
        self.assertIn("[DISCLAIMER]\nFor informational purposes only. Not investment advice.", full_outputs()["evening"])


class DailySurfaceTest(unittest.TestCase):
    def test_10_en_us_headings(self) -> None:
        text = full_outputs()["daily"]
        for heading in ("[TODAY'S MARKET PULSE]", "[IMPORTANT EVENTS]", "[GLOBAL MARKETS]", "[NEXT CONFIRMATION]"):
            self.assertIn(heading, text)

    def test_11_no_cjk(self) -> None:
        self.assertFalse(contains_cjk(full_outputs()["daily"]))

    def test_12_english_fallback(self) -> None:
        text = missing_outputs()["daily"]
        self.assertIn("Some data is temporarily unavailable", text)
        self.assertNotIn("数据", text)


class WeeklySurfaceTest(unittest.TestCase):
    def test_13_en_us_headings(self) -> None:
        text = full_outputs()["weekly"]
        for heading in ("[WEEKLY WINNERS]", "[NARRATIVE RANKING]", "[FALSE NARRATIVE WATCHLIST]"):
            self.assertIn(heading, text)

    def test_14_no_cjk(self) -> None:
        self.assertFalse(contains_cjk(full_outputs()["weekly"]))

    def test_15_english_fiona_view(self) -> None:
        text = full_outputs()["weekly"]
        self.assertIn("This week's leading narrative", text)
        self.assertIn("[FIONA'S VIEW]", text)


class AlertSurfaceTest(unittest.TestCase):
    def test_16_english_severity(self) -> None:
        self.assertIn("Fiona Alert | Critical", full_outputs()["alert_critical"])
        self.assertIn("Fiona Alert | Moderate", full_outputs()["alert_moderate"])

    def test_17_english_event(self) -> None:
        self.assertIn("[EVENT]", full_outputs()["alert_critical"])
        self.assertIn("BTC moved -1.80%", full_outputs()["alert_critical"])

    def test_18_english_why_it_matters(self) -> None:
        self.assertIn("[WHY IT MATTERS]", full_outputs()["alert_critical"])

    def test_19_english_affected_assets(self) -> None:
        text = full_outputs()["alert_critical"]
        self.assertIn("[AFFECTED ASSETS]", text)
        self.assertIn("Direct: BTC", text)

    def test_20_english_fiona_assessment(self) -> None:
        text = full_outputs()["alert_critical"]
        self.assertIn("[FIONA ASSESSMENT]", text)
        self.assertIn("Direction: Bearish", text)

    def test_21_english_next_confirmation(self) -> None:
        self.assertIn("[NEXT CONFIRMATION]", full_outputs()["alert_critical"])

    def test_22_no_cjk(self) -> None:
        self.assertFalse(contains_cjk(full_outputs()["alert_critical"]))

    def test_23_disclaimer(self) -> None:
        self.assertIn("For informational purposes only. Not investment advice.", full_outputs()["alert_critical"])


class SharedLanguageBoundaryTest(unittest.TestCase):
    def test_24_en_us_date_formatting(self) -> None:
        stamp = format_display_timestamp(
            datetime(2026, 9, 2, 7, 30, tzinfo=ZoneInfo("Asia/Hong_Kong")),
            OutputLocale.EN_US,
        )
        self.assertEqual(stamp, "SEP 02 · 07:30 UTC+8")

    def test_25_shared_terminology_consistency(self) -> None:
        combined = "\n".join(full_outputs().values())
        for key in ("what_changed", "fiona_view", "next_confirmation"):
            self.assertIn(SHARED_EN_US_TERMINOLOGY[key].upper(), combined)

    def test_26_source_provenance_preserved(self) -> None:
        events = en_us_fixture_events()
        original = events[0].raw_data["original_title"]
        build_morning_brief(
            events,
            en_us_fixture_narratives(),
            generated_at=VALIDATION_TIME,
            output_locale=OutputLocale.EN_US,
        ).render_text()
        self.assertEqual(events[0].raw_data["original_title"], original)
        self.assertTrue(contains_cjk(events[0].what_happened))

    def test_27_cjk_full_width_punctuation_blocked(self) -> None:
        self.assertTrue(contains_cjk("Market state：Neutral"))

    def test_28_safe_leakage_fallback(self) -> None:
        safe = finalize_user_visible_text(
            "Fiona 简报",
            OutputLocale.EN_US,
            fallback="Fiona Intelligence\nSafe English fallback.",
        )
        self.assertEqual(safe, "Fiona Intelligence\nSafe English fallback.")

    def test_29_no_infinite_repair_loop(self) -> None:
        calls = 0

        def fallback() -> str:
            nonlocal calls
            calls += 1
            return "Safe English fallback."

        self.assertEqual(finalize_user_visible_text("中文", OutputLocale.EN_US, fallback=fallback), "Safe English fallback.")
        self.assertEqual(calls, 1)


class Gate11RegressionTest(unittest.TestCase):
    def test_30_market_news_still_passes(self) -> None:
        self.assertFalse(contains_cjk(full_outputs()["market_news"]))

    def test_31_native_photo_still_passes(self) -> None:
        model = build_market_news_view_model(
            en_us_fixture_snapshot(),
            en_us_fixture_events(),
            en_us_fixture_narratives(),
            generated_at=VALIDATION_TIME,
            output_locale=OutputLocale.EN_US,
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            output = render_market_news_card_ios(model, Path(tmpdir) / "gate11.png")
            validation = validate_market_news_png(output, expected_size=(1440, 1800))
        self.assertEqual((validation.width, validation.height), (1440, 1800))

    def test_32_document_legacy_path_still_passes(self) -> None:
        self.assertEqual(parse_telegram_media_mode(None), TelegramMediaMode.DOCUMENT)

    def test_33_zh_cn_legacy_mode_is_preserved(self) -> None:
        text = build_morning_brief(
            en_us_fixture_events(),
            en_us_fixture_narratives(),
            generated_at=VALIDATION_TIME,
        ).render_text()
        self.assertIn("更新时间", text)
        self.assertTrue(contains_cjk(text))

    def test_34_scheduler_is_unchanged(self) -> None:
        expected = {
            FionaBriefKind.MARKET_NEWS: "00:00:00",
            FionaBriefKind.MORNING: "07:30:00",
            FionaBriefKind.EVENING: "20:30:00",
            FionaBriefKind.DAILY: "22:30:00",
            FionaBriefKind.WEEKLY: "21:00:00",
        }
        self.assertEqual({kind: item.send_time.isoformat() for kind, item in BRIEF_SCHEDULES.items()}, expected)

    def test_35_ledger_is_not_mutated(self) -> None:
        self.assertEqual(validate_en_us_user_surfaces_runtime()["ledger_mutations"], 0)

    def test_36_arbitration_contract_is_unchanged(self) -> None:
        self.assertEqual((ACTION_SEND, ACTION_DEFER, ACTION_SUPPRESS), ("send", "defer", "suppress"))

    def test_37_coverage_flag_is_not_mutated(self) -> None:
        with patch.dict("os.environ", {"FIONA_COVERAGE_PROFILE": "legacy"}, clear=False):
            validate_en_us_user_surfaces_runtime()
            self.assertEqual(__import__("os").environ["FIONA_COVERAGE_PROFILE"], "legacy")

    def test_38_cadence_flag_is_not_mutated(self) -> None:
        with patch.dict("os.environ", {"FIONA_CADENCE_MODE": "legacy"}, clear=False):
            validate_en_us_user_surfaces_runtime()
            self.assertEqual(__import__("os").environ["FIONA_CADENCE_MODE"], "legacy")

    def test_39_delta_flag_remains_off(self) -> None:
        with patch.dict("os.environ", {"FIONA_4H_DELTA_MODE": "off"}, clear=False):
            validate_en_us_user_surfaces_runtime()
            self.assertEqual(__import__("os").environ["FIONA_4H_DELTA_MODE"], "off")

    def test_40_production_safe_validation_passes(self) -> None:
        result = validate_en_us_user_surfaces_runtime()
        self.assertTrue(result["all_user_surfaces_en_us"], result)
        self.assertEqual(result["telegram_api_calls"], 0)
        self.assertEqual(result["scheduler_mutations"], 0)
        self.assertEqual(result["formal_occurrences_created"], 0)

    def test_runtime_propagates_en_us_to_daily_and_alert(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, patch.dict(
            "os.environ",
            {"FIONA_OUTPUT_LOCALE": "en-US", "FIONA_ALERT_ENABLED": "0"},
            clear=False,
        ):
            result = run_once(
                output_dir=Path(tmpdir),
                brief="daily",
                send=False,
                timezone_name="Asia/Hong_Kong",
                snapshot_builder=lambda _: en_us_fixture_snapshot(),
            )
            text = (Path(result["output_dir"]) / "fiona_telegram.md").read_text(encoding="utf-8")
            alerts = (Path(result["output_dir"]) / "fiona_alerts.md").read_text(encoding="utf-8")
        self.assertEqual(result["output_locale"], "en-US")
        self.assertFalse(contains_cjk(text))
        self.assertFalse(contains_cjk(alerts))

    def test_market_news_caption_regression(self) -> None:
        model = build_market_news_view_model(
            en_us_fixture_snapshot(),
            en_us_fixture_events(),
            en_us_fixture_narratives(),
            generated_at=VALIDATION_TIME,
            output_locale=OutputLocale.EN_US,
        )
        caption = compose_market_news_caption(model)
        self.assertIn("Fiona Global Intelligence", caption)
        self.assertFalse(contains_cjk(caption))

    def test_en_us_snapshot_failure_writes_safe_english_fallback(self) -> None:
        def fail_snapshot(_: datetime) -> dict:
            raise RuntimeError("fixture source unavailable")

        with tempfile.TemporaryDirectory() as tmpdir, patch.dict(
            "os.environ",
            {"FIONA_OUTPUT_LOCALE": "en-US"},
            clear=False,
        ):
            result = run_once(
                output_dir=Path(tmpdir),
                brief="morning",
                send=False,
                timezone_name="Asia/Hong_Kong",
                snapshot_builder=fail_snapshot,
            )
            fallback = (Path(result["output_dir"]) / "fiona_fallback_telegram.md").read_text(encoding="utf-8")
        self.assertTrue(result["fallback"]["used"])
        self.assertFalse(contains_cjk(fallback))


if __name__ == "__main__":
    unittest.main()
