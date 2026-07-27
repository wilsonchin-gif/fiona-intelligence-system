from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from PIL import Image

from app.fiona_card_renderer import EvidenceLevel, render_market_news_card
from app.fiona_market_news_delivery import (
    DELIVERY_PARTIAL,
    ImageValidationError,
    MarketNewsDeliveryCoordinator,
    MarketNewsMode,
    market_news_mode_from_env,
    parse_market_news_mode,
    safe_error,
    validate_market_news_png,
)
from app.fiona_market_news_image import (
    build_market_news_view_model,
    compose_market_news_caption,
)
from app.fiona_narrative import NarrativeEngine
from app.fiona_scheduler import delivery_status
from app.telegram_service import (
    TelegramRequestError,
    TelegramUnknownDeliveryError,
)
from scripts.generate_fiona_market_news_prototypes import (
    NOW,
    full_snapshot,
    prototype_events,
)


def sample_view_model():
    events = prototype_events()
    narratives = NarrativeEngine().build(events, now=NOW)
    return build_market_news_view_model(full_snapshot(), events, narratives, generated_at=NOW)


def text_success(text: str) -> dict:
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


def document_success(path: str | Path, caption: str) -> dict:
    return {"ok": True, "result": {"message_id": 202}}


class MarketNewsModeTest(unittest.TestCase):
    def test_unset_defaults_to_text(self) -> None:
        self.assertEqual(parse_market_news_mode(None), MarketNewsMode.TEXT)
        self.assertEqual(market_news_mode_from_env({}), MarketNewsMode.TEXT)

    def test_legal_modes(self) -> None:
        self.assertEqual(parse_market_news_mode("text"), MarketNewsMode.TEXT)
        self.assertEqual(parse_market_news_mode("shadow"), MarketNewsMode.SHADOW)
        self.assertEqual(parse_market_news_mode("image"), MarketNewsMode.IMAGE)

    def test_mode_is_case_and_space_insensitive(self) -> None:
        self.assertEqual(parse_market_news_mode("  ImAgE  "), MarketNewsMode.IMAGE)

    def test_invalid_mode_warns_and_falls_back_to_text(self) -> None:
        logs: list[dict] = []
        self.assertEqual(parse_market_news_mode("video", logs.append), MarketNewsMode.TEXT)
        self.assertEqual(logs[0]["fallback_mode"], "text")
        self.assertNotIn("token", str(logs).lower())

    def test_error_sanitization_redacts_telegram_token_shapes(self) -> None:
        error = RuntimeError(
            "https://api.telegram.org/bot1234567890:UnitTestSecret/sendDocument failed"
        )
        sanitized = safe_error(error)
        self.assertNotIn("UnitTestSecret", sanitized)
        self.assertNotIn("1234567890", sanitized)


class MarketNewsDeliveryCoordinatorTest(unittest.TestCase):
    def coordinator(self, **overrides):
        values = {
            "text_sender": Mock(side_effect=text_success),
            "document_sender": Mock(side_effect=document_success),
            "renderer": Mock(side_effect=render_market_news_card),
            "caption_builder": Mock(side_effect=compose_market_news_caption),
            "logger": Mock(),
        }
        values.update(overrides)
        return MarketNewsDeliveryCoordinator(**values), values

    def test_text_mode_only_sends_original_text(self) -> None:
        coordinator, deps = self.coordinator()
        factory = Mock(side_effect=sample_view_model)
        result = coordinator.deliver(
            mode=MarketNewsMode.TEXT,
            legacy_text="legacy market news",
            view_model_factory=factory,
        )
        self.assertTrue(result.text_sent)
        self.assertEqual(result.push_result["message_ids"], [101])
        factory.assert_not_called()
        deps["renderer"].assert_not_called()
        deps["document_sender"].assert_not_called()
        deps["text_sender"].assert_called_once_with("legacy market news")

    def test_shadow_sends_text_renders_and_never_sends_document(self) -> None:
        coordinator, deps = self.coordinator()
        result = coordinator.deliver(
            mode=MarketNewsMode.SHADOW,
            legacy_text="legacy",
            view_model_factory=sample_view_model,
        )
        self.assertTrue(result.text_sent)
        self.assertTrue(result.image_generated)
        self.assertTrue(result.image_validation)
        self.assertFalse(result.image_sent)
        self.assertTrue(result.cleanup_success)
        deps["text_sender"].assert_called_once()
        deps["renderer"].assert_called_once()
        deps["document_sender"].assert_not_called()

    def test_shadow_renderer_failure_does_not_change_text_success(self) -> None:
        coordinator, deps = self.coordinator(renderer=Mock(side_effect=RuntimeError("renderer failed")))
        result = coordinator.deliver(
            mode=MarketNewsMode.SHADOW,
            legacy_text="legacy",
            view_model_factory=sample_view_model,
        )
        self.assertTrue(result.text_sent)
        self.assertEqual(result.push_result["delivery_status"], "success")
        self.assertEqual(result.error_category, "renderer_failed")
        self.assertFalse(result.fallback_used)
        deps["document_sender"].assert_not_called()

    def test_shadow_invalid_png_does_not_change_text_success(self) -> None:
        def invalid_renderer(model, path):
            Path(path).write_bytes(b"not-png")
            return Path(path)

        coordinator, _ = self.coordinator(renderer=invalid_renderer)
        result = coordinator.deliver(
            mode=MarketNewsMode.SHADOW,
            legacy_text="legacy",
            view_model_factory=sample_view_model,
        )
        self.assertTrue(result.text_sent)
        self.assertFalse(result.image_validation)
        self.assertEqual(result.error_category, "image_validation_failed")
        self.assertTrue(result.cleanup_success)

    def test_image_success_uses_one_view_model_and_one_document(self) -> None:
        model = sample_view_model()
        factory = Mock(return_value=model)
        seen: dict[str, object] = {}

        def caption_builder(value):
            seen["caption_model"] = value
            return compose_market_news_caption(value)

        def renderer(value, path):
            seen["renderer_model"] = value
            return render_market_news_card(value, path)

        def document_sender(path, caption):
            seen["document_path"] = Path(path)
            seen["caption"] = caption
            self.assertTrue(Path(path).exists())
            return document_success(path, caption)

        text_sender = Mock(side_effect=text_success)
        coordinator = MarketNewsDeliveryCoordinator(
            text_sender=text_sender,
            document_sender=document_sender,
            renderer=renderer,
            caption_builder=caption_builder,
        )
        result = coordinator.deliver(
            mode=MarketNewsMode.IMAGE,
            legacy_text="legacy",
            view_model_factory=factory,
        )
        factory.assert_called_once()
        self.assertIs(seen["caption_model"], model)
        self.assertIs(seen["renderer_model"], model)
        self.assertTrue(result.image_sent)
        self.assertFalse(result.fallback_used)
        self.assertFalse(result.text_sent)
        self.assertEqual(result.message_ids, [202])
        self.assertEqual(result.push_result["delivery_status"], "success")
        self.assertEqual(result.final_delivery_channel, "document")
        self.assertTrue(result.cleanup_success)
        self.assertFalse(seen["document_path"].exists())
        text_sender.assert_not_called()

    def test_caption_failure_falls_back_once(self) -> None:
        coordinator, deps = self.coordinator(caption_builder=Mock(side_effect=ValueError("caption failed")))
        result = coordinator.deliver(
            mode=MarketNewsMode.IMAGE,
            legacy_text="legacy",
            view_model_factory=sample_view_model,
        )
        self.assertTrue(result.fallback_used)
        self.assertEqual(result.fallback_reason, "caption_failed")
        self.assertTrue(result.text_sent)
        deps["text_sender"].assert_called_once()
        deps["document_sender"].assert_not_called()

    def test_view_model_failure_falls_back_once(self) -> None:
        coordinator, deps = self.coordinator()
        result = coordinator.deliver(
            mode=MarketNewsMode.IMAGE,
            legacy_text="legacy",
            view_model_factory=Mock(side_effect=RuntimeError("view model failed")),
        )
        self.assertEqual(result.fallback_reason, "view_model_failed")
        deps["text_sender"].assert_called_once()
        deps["renderer"].assert_not_called()

    def test_renderer_and_font_failures_fall_back(self) -> None:
        for message in ("renderer failed", "Missing fixed Fiona font asset"):
            coordinator, deps = self.coordinator(renderer=Mock(side_effect=RuntimeError(message)))
            result = coordinator.deliver(
                mode=MarketNewsMode.IMAGE,
                legacy_text="legacy",
                view_model_factory=sample_view_model,
            )
            self.assertEqual(result.fallback_reason, "renderer_failed")
            self.assertTrue(result.text_sent)
            deps["text_sender"].assert_called_once()

    def test_invalid_dimensions_empty_and_oversize_fall_back(self) -> None:
        def wrong_size(model, path):
            Image.new("RGB", (100, 100), "black").save(path, "PNG")
            return Path(path)

        def empty(model, path):
            Path(path).write_bytes(b"")
            return Path(path)

        def oversized(model, path):
            Path(path).write_bytes(b"x" * 1_500_001)
            return Path(path)

        for renderer in (wrong_size, empty, oversized):
            coordinator, deps = self.coordinator(renderer=renderer)
            result = coordinator.deliver(
                mode=MarketNewsMode.IMAGE,
                legacy_text="legacy",
                view_model_factory=sample_view_model,
            )
            self.assertTrue(result.fallback_used)
            self.assertEqual(result.fallback_reason, "image_validation_failed")
            deps["text_sender"].assert_called_once()
            deps["document_sender"].assert_not_called()
            self.assertTrue(result.cleanup_success)

    def test_temporary_directory_failure_falls_back(self) -> None:
        coordinator, deps = self.coordinator()
        with patch(
            "app.fiona_market_news_delivery.tempfile.TemporaryDirectory",
            side_effect=OSError("temp unavailable"),
        ):
            result = coordinator.deliver(
                mode=MarketNewsMode.IMAGE,
                legacy_text="legacy",
                view_model_factory=sample_view_model,
            )
        self.assertEqual(result.fallback_reason, "temporary_file_failed")
        deps["text_sender"].assert_called_once()

    def test_explicit_document_failure_falls_back_once(self) -> None:
        failure = TelegramRequestError(
            "Bad Request",
            category="telegram_api_rejected",
            delivery_state="failed",
            status_code=400,
        )
        coordinator, deps = self.coordinator(document_sender=Mock(side_effect=failure))
        result = coordinator.deliver(
            mode=MarketNewsMode.IMAGE,
            legacy_text="legacy",
            view_model_factory=sample_view_model,
        )
        self.assertTrue(result.fallback_used)
        self.assertEqual(result.error_category, "telegram_api_rejected")
        deps["text_sender"].assert_called_once()
        self.assertTrue(result.text_sent)
        self.assertTrue(result.cleanup_success)

    def test_unknown_document_state_never_falls_back_or_retries(self) -> None:
        unknown = TelegramUnknownDeliveryError(
            "timeout; delivery unknown",
            category="telegram_timeout",
        )
        coordinator, deps = self.coordinator(document_sender=Mock(side_effect=unknown))
        result = coordinator.deliver(
            mode=MarketNewsMode.IMAGE,
            legacy_text="legacy",
            view_model_factory=sample_view_model,
        )
        self.assertTrue(result.unknown_delivery_state)
        self.assertFalse(result.fallback_used)
        self.assertFalse(result.text_sent)
        self.assertEqual(result.push_result["delivery_status"], DELIVERY_PARTIAL)
        self.assertEqual(
            delivery_status({"ok": True, "brief_push": result.push_result}, send=True),
            DELIVERY_PARTIAL,
        )
        deps["text_sender"].assert_not_called()
        deps["document_sender"].assert_called_once()

    def test_missing_document_message_id_falls_back(self) -> None:
        coordinator, deps = self.coordinator(document_sender=Mock(return_value={"ok": True, "result": {}}))
        result = coordinator.deliver(
            mode=MarketNewsMode.IMAGE,
            legacy_text="legacy",
            view_model_factory=sample_view_model,
        )
        self.assertTrue(result.fallback_used)
        self.assertEqual(result.error_category, "telegram_missing_message_id")
        deps["text_sender"].assert_called_once()

    def test_fallback_text_failure_is_scheduler_visible(self) -> None:
        failed_text = Mock(
            return_value={
                "ok": False,
                "delivery_status": "failed",
                "message_ids": [],
                "errors": ["sendMessage failed"],
            }
        )
        coordinator, _ = self.coordinator(
            text_sender=failed_text,
            renderer=Mock(side_effect=RuntimeError("renderer failed")),
        )
        result = coordinator.deliver(
            mode=MarketNewsMode.IMAGE,
            legacy_text="legacy",
            view_model_factory=sample_view_model,
        )
        self.assertTrue(result.fallback_used)
        self.assertFalse(result.text_sent)
        self.assertFalse(result.push_result["ok"])
        self.assertIn("sendMessage failed", result.errors)
        failed_text.assert_called_once()

    def test_logs_contain_metrics_but_not_caption_or_credentials(self) -> None:
        logs: list[dict] = []
        coordinator = MarketNewsDeliveryCoordinator(
            text_sender=text_success,
            document_sender=document_success,
            logger=logs.append,
        )
        result = coordinator.deliver(
            mode=MarketNewsMode.IMAGE,
            legacy_text="legacy",
            view_model_factory=sample_view_model,
            occurrence_id="market_news:test",
        )
        payload = logs[-1]
        self.assertEqual(payload["occurrence_id"], "market_news:test")
        self.assertEqual(payload["image_width"], 1080)
        self.assertEqual(payload["image_height"], 1350)
        self.assertEqual(payload["market_regime"], result.market_regime)
        self.assertEqual(payload["evidence_level"], EvidenceLevel.VERIFIED.value)
        self.assertNotIn("caption", payload)
        self.assertNotIn("bot_token", payload)


class MarketNewsImageValidationTest(unittest.TestCase):
    def test_valid_png_returns_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "valid.png"
            Image.new("RGB", (1080, 1350), "black").save(path, "PNG")
            result = validate_market_news_png(path)
        self.assertEqual((result.width, result.height), (1080, 1350))
        self.assertEqual(result.mode, "RGB")

    def test_non_png_extension_and_invalid_mime_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            wrong_extension = Path(tmpdir) / "card.jpg"
            Image.new("RGB", (1080, 1350), "black").save(wrong_extension, "PNG")
            with self.assertRaises(ImageValidationError):
                validate_market_news_png(wrong_extension)

            invalid = Path(tmpdir) / "card.png"
            invalid.write_text("not an image", encoding="utf-8")
            with self.assertRaises(ImageValidationError):
                validate_market_news_png(invalid)


if __name__ == "__main__":
    unittest.main()
