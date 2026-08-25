from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch
from zoneinfo import ZoneInfo

from PIL import Image

from app.design_tokens import FIONA_IOS_TOKENS, FIONA_TOKENS
from app.fiona_briefing import BRIEF_SCHEDULES, FionaBriefKind
from app.fiona_card_renderer import render_market_news_card_ios
from app.fiona_locale import (
    OutputLocale,
    contains_cjk,
    format_display_timestamp,
    output_locale_from_env,
    parse_output_locale,
    strings_for_locale,
)
from app.fiona_market_news_delivery import (
    DELIVERY_PARTIAL,
    MarketNewsDeliveryCoordinator,
    MarketNewsMode,
    TelegramMediaMode,
    parse_telegram_media_mode,
    render_for_media,
    telegram_media_mode_from_env,
    validate_market_news_png,
)
from app.fiona_market_news_image import (
    ChangedEventView,
    PHOTO_CAPTION_MAX_CHARS,
    PHOTO_CAPTION_MIN_CHARS,
    build_market_news_view_model,
    compose_market_news_caption,
    market_news_visible_strings,
)
from app.fiona_narrative import NarrativeEngine
from app.fiona_runtime import run_once
from app.telegram_service import TelegramRequestError, TelegramUnknownDeliveryError
from scripts.generate_fiona_market_news_prototypes import NOW, full_snapshot, prototype_events


def view_model(locale: OutputLocale = OutputLocale.EN_US):
    events = prototype_events()
    narratives = NarrativeEngine().build(events, now=NOW)
    return build_market_news_view_model(
        full_snapshot(),
        events,
        narratives,
        generated_at=NOW,
        output_locale=locale,
    )


def text_success(_: str) -> dict:
    return {
        "scope": "Fiona Market News",
        "ok": True,
        "delivery_status": "success",
        "message_ids": [101],
        "successful_chunks": [1],
        "failed_chunks": [],
        "errors": [],
        "total_chunks": 1,
    }


def media_success(_: str | Path, __: str) -> dict:
    return {"ok": True, "result": {"message_id": 202}}


class Gate1FeatureFlagTest(unittest.TestCase):
    def test_media_mode_defaults_to_document(self) -> None:
        self.assertEqual(parse_telegram_media_mode(None), TelegramMediaMode.DOCUMENT)
        self.assertEqual(telegram_media_mode_from_env({}), TelegramMediaMode.DOCUMENT)

    def test_media_mode_accepts_document_photo_and_normalizes_case(self) -> None:
        self.assertEqual(parse_telegram_media_mode("document"), TelegramMediaMode.DOCUMENT)
        self.assertEqual(parse_telegram_media_mode("  PhOtO "), TelegramMediaMode.PHOTO)

    def test_invalid_media_mode_warns_and_uses_document(self) -> None:
        logs: list[dict] = []
        self.assertEqual(parse_telegram_media_mode("video", logs.append), TelegramMediaMode.DOCUMENT)
        self.assertEqual(logs[0]["fallback_mode"], "document")

    def test_locale_defaults_to_zh_cn_and_normalizes_en_us(self) -> None:
        self.assertEqual(parse_output_locale(None), OutputLocale.ZH_CN)
        self.assertEqual(output_locale_from_env({}), OutputLocale.ZH_CN)
        self.assertEqual(parse_output_locale("  EN-us "), OutputLocale.EN_US)

    def test_invalid_locale_warns_and_uses_zh_cn(self) -> None:
        logs: list[dict] = []
        self.assertEqual(parse_output_locale("fr-FR", logs.append), OutputLocale.ZH_CN)
        self.assertEqual(logs[0]["fallback_locale"], "zh-CN")


class Gate1LocaleAndCaptionTest(unittest.TestCase):
    def test_en_us_strings_date_missing_data_and_disclaimer(self) -> None:
        strings = strings_for_locale(OutputLocale.EN_US)
        stamp = format_display_timestamp(
            datetime(2026, 8, 25, 20, 0, tzinfo=ZoneInfo("Asia/Hong_Kong")),
            OutputLocale.EN_US,
        )
        self.assertEqual(stamp, "AUG 25 · 20:00 UTC+8")
        self.assertEqual(strings.data_unavailable, "Data unavailable")
        self.assertIn("Not investment advice", strings.informational_disclaimer)
        self.assertEqual(strings.today_judgment, "TODAY'S JUDGMENT")

    def test_en_us_market_news_has_no_cjk_leakage(self) -> None:
        model = view_model()
        self.assertFalse(any(contains_cjk(value) for value in market_news_visible_strings(model)))
        self.assertFalse(contains_cjk(compose_market_news_caption(model)))

    def test_cjk_leakage_detection_includes_full_width_punctuation(self) -> None:
        self.assertTrue(contains_cjk("Market state：Neutral"))
        self.assertTrue(contains_cjk("データ"))
        self.assertFalse(contains_cjk("Market state: Neutral"))

    def test_native_photo_caption_is_short_plain_english_editorial_copy(self) -> None:
        caption = compose_market_news_caption(view_model())
        self.assertGreaterEqual(len(caption), PHOTO_CAPTION_MIN_CHARS)
        self.assertLessEqual(len(caption), PHOTO_CAPTION_MAX_CHARS)
        self.assertIn("Fiona Global Intelligence", caption)
        self.assertIn("Market state:", caption)
        self.assertIn("Fiona's view:", caption)
        self.assertIn("Watch next:", caption)
        self.assertNotIn("WHAT CHANGED", caption)
        self.assertNotIn("KEY MARKETS", caption)
        self.assertNotIn("04H", caption)
        self.assertNotRegex(caption, r"<[^>]+>")

    def test_source_language_provenance_is_preserved_outside_primary_output(self) -> None:
        model = view_model()
        self.assertTrue(model.source_provenance)
        self.assertTrue(any(item.original_text for item in model.source_provenance))
        self.assertTrue(any(item.source_language == "zh" for item in model.source_provenance))
        self.assertFalse(contains_cjk(model.what_changed[0].event))

    def test_missing_en_us_model_uses_honest_english_states(self) -> None:
        model = build_market_news_view_model({}, [], [], generated_at=NOW, output_locale="en-US")
        self.assertIn("limited", model.fiona_view.lower())
        self.assertTrue(all(not contains_cjk(value) for value in market_news_visible_strings(model)))


class Gate1RendererTest(unittest.TestCase):
    def test_ios_tokens_define_native_canvas_and_safe_areas(self) -> None:
        self.assertEqual((FIONA_IOS_TOKENS.canvas.width, FIONA_IOS_TOKENS.canvas.height), (1440, 1800))
        self.assertEqual(FIONA_IOS_TOKENS.canvas.width * 5, FIONA_IOS_TOKENS.canvas.height * 4)
        self.assertGreaterEqual(FIONA_IOS_TOKENS.spacing.outer_margin, 72)
        self.assertGreaterEqual(FIONA_IOS_TOKENS.canvas.safe_top, 48)
        self.assertGreaterEqual(FIONA_IOS_TOKENS.canvas.safe_bottom, 48)
        self.assertGreaterEqual(FIONA_IOS_TOKENS.canvas.minimum_text_size, 17)

    def test_renderer_produces_native_1440_without_resize(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, patch.object(
            Image.Image,
            "resize",
            side_effect=AssertionError("upscale path is forbidden"),
        ):
            output = render_market_news_card_ios(view_model(), Path(tmpdir) / "native.png")
            validation = validate_market_news_png(output, expected_size=(1440, 1800))
        self.assertEqual((validation.width, validation.height), (1440, 1800))
        self.assertEqual(validation.mode, "RGB")

    def test_full_missing_and_stress_render_at_1440(self) -> None:
        full = view_model()
        missing = build_market_news_view_model({}, [], [], generated_at=NOW, output_locale="en-US")
        stress = replace(
            full,
            fiona_view=(
                "Cross-market evidence remains fragmented while liquidity, rates, and risk assets "
                "continue to require independent confirmation. " * 12
            ),
            what_changed=(
                ChangedEventView("A long but bounded market development " * 8, "Evidence context " * 12, "Confirm flows " * 10),
            ),
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            for name, model in (("full", full), ("missing", missing), ("stress", stress)):
                output = render_market_news_card_ios(model, Path(tmpdir) / f"{name}.png")
                validation = validate_market_news_png(output, expected_size=(1440, 1800))
                self.assertEqual((validation.width, validation.height), (1440, 1800))
                self.assertGreater(validation.size_bytes, 0)

    def test_four_feature_flag_combinations_keep_transport_profiles_separate(self) -> None:
        combinations = (
            (TelegramMediaMode.DOCUMENT, OutputLocale.ZH_CN, (1080, 1350)),
            (TelegramMediaMode.DOCUMENT, OutputLocale.EN_US, (1080, 1350)),
            (TelegramMediaMode.PHOTO, OutputLocale.ZH_CN, (1440, 1800)),
            (TelegramMediaMode.PHOTO, OutputLocale.EN_US, (1440, 1800)),
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            for media_mode, locale, expected in combinations:
                target = Path(tmpdir) / f"{media_mode.value}-{locale.value}.png"
                output = render_for_media(view_model(locale), target, media_mode)
                with Image.open(output) as rendered:
                    self.assertEqual(rendered.size, expected)


class Gate1DeliveryCoordinatorTest(unittest.TestCase):
    def coordinator(self, **overrides):
        values = {
            "text_sender": Mock(side_effect=text_success),
            "document_sender": Mock(side_effect=media_success),
            "photo_sender": Mock(side_effect=media_success),
            "logger": Mock(),
        }
        values.update(overrides)
        return MarketNewsDeliveryCoordinator(**values), values

    def deliver_photo(self, coordinator: MarketNewsDeliveryCoordinator):
        return coordinator.deliver(
            mode=MarketNewsMode.IMAGE,
            media_mode=TelegramMediaMode.PHOTO,
            output_locale="en-US",
            legacy_text=compose_market_news_caption(view_model()),
            view_model_factory=view_model,
        )

    def test_photo_success_sends_one_photo_and_no_text(self) -> None:
        coordinator, deps = self.coordinator()
        result = self.deliver_photo(coordinator)
        self.assertTrue(result.image_sent)
        self.assertFalse(result.text_sent)
        self.assertEqual(result.final_delivery_channel, "photo")
        self.assertEqual(result.photo_send_status, "success")
        self.assertEqual((result.image_width, result.image_height), (1440, 1800))
        deps["photo_sender"].assert_called_once()
        deps["document_sender"].assert_not_called()
        deps["text_sender"].assert_not_called()

    def test_photo_explicit_failure_falls_back_to_text_exactly_once(self) -> None:
        failure = TelegramRequestError("rejected", category="telegram_api_rejected", delivery_state="failed")
        coordinator, deps = self.coordinator(photo_sender=Mock(side_effect=failure))
        result = self.deliver_photo(coordinator)
        self.assertTrue(result.fallback_used)
        self.assertTrue(result.text_sent)
        self.assertEqual(result.photo_send_status, "failed")
        self.assertEqual(result.final_delivery_channel, "text")
        deps["photo_sender"].assert_called_once()
        deps["text_sender"].assert_called_once()
        deps["document_sender"].assert_not_called()

    def test_photo_unknown_suppresses_text_and_document(self) -> None:
        failure = TelegramUnknownDeliveryError("timeout", category="telegram_timeout")
        coordinator, deps = self.coordinator(photo_sender=Mock(side_effect=failure))
        result = self.deliver_photo(coordinator)
        self.assertTrue(result.unknown_delivery_state)
        self.assertFalse(result.fallback_used)
        self.assertFalse(result.text_sent)
        self.assertEqual(result.push_result["delivery_status"], DELIVERY_PARTIAL)
        self.assertEqual(result.final_delivery_channel, "photo_unknown")
        deps["photo_sender"].assert_called_once()
        deps["text_sender"].assert_not_called()
        deps["document_sender"].assert_not_called()

    def test_renderer_caption_and_png_failures_each_use_one_text_fallback(self) -> None:
        def invalid_png(_: object, path: str | Path) -> Path:
            Path(path).write_bytes(b"invalid")
            return Path(path)

        cases = (
            {"renderer": Mock(side_effect=RuntimeError("render failed"))},
            {"renderer": invalid_png},
            {"caption_builder": Mock(side_effect=RuntimeError("caption failed"))},
        )
        for overrides in cases:
            coordinator, deps = self.coordinator(**overrides)
            result = self.deliver_photo(coordinator)
            self.assertTrue(result.fallback_used)
            self.assertTrue(result.text_sent)
            deps["text_sender"].assert_called_once()
            deps["photo_sender"].assert_not_called()
            deps["document_sender"].assert_not_called()

    def test_observability_contains_media_locale_delivery_and_cleanup(self) -> None:
        logs: list[dict] = []
        coordinator, _ = self.coordinator(logger=logs.append)
        result = self.deliver_photo(coordinator)
        event = logs[-1]
        self.assertEqual(event["telegram_media_mode"], "photo")
        self.assertEqual(event["output_locale"], "en-US")
        self.assertEqual(event["photo_send_status"], "success")
        self.assertEqual(event["final_delivery_channel"], "photo")
        self.assertEqual(event["cleanup_state"], "success")
        self.assertEqual(result.observability_fields()["delivery_state"], "success")


class Gate1RegressionBoundaryTest(unittest.TestCase):
    def test_runtime_photo_en_us_uses_native_photo_without_document_or_text(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, patch.dict(
            "os.environ",
            {
                "FIONA_MARKET_NEWS_MODE": "image",
                "FIONA_TELEGRAM_MEDIA_MODE": "photo",
                "FIONA_OUTPUT_LOCALE": "en-US",
            },
            clear=False,
        ), patch(
            "app.fiona_runtime.telegram_send_photo",
            return_value={"ok": True, "result": {"message_id": 909}},
        ) as photo_sender, patch(
            "app.fiona_runtime.telegram_send_document"
        ) as document_sender, patch(
            "app.fiona_runtime.telegram_send_message"
        ) as text_sender:
            output = Path(tmpdir)
            status = run_once(
                output_dir=output,
                brief="market-news",
                send=True,
                timezone_name="Asia/Hong_Kong",
                snapshot_builder=lambda _: full_snapshot(),
            )

            preview = (output / "latest" / "fiona_telegram.md").read_text(encoding="utf-8")

        self.assertTrue(status["brief_push"]["ok"], status)
        self.assertEqual(status["brief_push"]["channel"], "photo")
        self.assertEqual(status["telegram_media_mode"], "photo")
        self.assertEqual(status["output_locale"], "en-US")
        self.assertEqual(status["market_news_delivery"]["final_delivery_channel"], "photo")
        self.assertEqual(
            (status["market_news_delivery"]["image_width"], status["market_news_delivery"]["image_height"]),
            (1440, 1800),
        )
        self.assertFalse(contains_cjk(preview))
        photo_sender.assert_called_once()
        document_sender.assert_not_called()
        text_sender.assert_not_called()

    def test_legacy_tokens_and_fixed_cadence_remain_unchanged(self) -> None:
        self.assertEqual((FIONA_TOKENS.canvas.width, FIONA_TOKENS.canvas.height), (1080, 1350))
        self.assertEqual(BRIEF_SCHEDULES[FionaBriefKind.MARKET_NEWS].send_time.isoformat(), "00:00:00")
        self.assertEqual(BRIEF_SCHEDULES[FionaBriefKind.MORNING].send_time.isoformat(), "07:30:00")
        self.assertEqual(BRIEF_SCHEDULES[FionaBriefKind.EVENING].send_time.isoformat(), "20:30:00")
        self.assertEqual(BRIEF_SCHEDULES[FionaBriefKind.DAILY].send_time.isoformat(), "22:30:00")
        self.assertEqual(BRIEF_SCHEDULES[FionaBriefKind.WEEKLY].send_time.isoformat(), "21:00:00")


if __name__ == "__main__":
    unittest.main()
