from __future__ import annotations

import subprocess
import sys
import tempfile
import textwrap
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

from app.fiona_runtime import push_text, run_once, run_scheduler_cycle
from tests.test_fiona_phase4 import sample_snapshot


TZ = ZoneInfo("Asia/Hong_Kong")


def hk_time(value: str) -> datetime:
    return datetime.fromisoformat(value).replace(tzinfo=TZ)


class FionaProductionPipelineTest(unittest.TestCase):
    def test_runtime_and_text_mode_import_without_pillow(self) -> None:
        root = Path(__file__).resolve().parent.parent
        script = textwrap.dedent(
            """
            import builtins
            import os

            real_import = builtins.__import__

            def guarded_import(name, *args, **kwargs):
                if name == "PIL" or name.startswith("PIL."):
                    raise AssertionError("text mode imported Pillow")
                return real_import(name, *args, **kwargs)

            builtins.__import__ = guarded_import
            os.environ["FIONA_MARKET_NEWS_MODE"] = "text"

            import app.fiona_runtime
            from app.fiona_market_news_delivery import (
                MarketNewsDeliveryCoordinator,
                MarketNewsMode,
            )

            coordinator = MarketNewsDeliveryCoordinator(
                text_sender=lambda text: {
                    "ok": True,
                    "message_ids": [1],
                    "errors": [],
                }
            )
            result = coordinator.deliver(
                mode=MarketNewsMode.TEXT,
                legacy_text="legacy",
                view_model_factory=lambda: (_ for _ in ()).throw(
                    AssertionError("text mode built image model")
                ),
            )
            assert result.text_sent
            """
        )
        result = subprocess.run(
            [sys.executable, "-c", script],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_scheduler_due_occurrence_invokes_runtime_and_generates_brief(self) -> None:
        generated_statuses = []

        def runner(**kwargs):
            status = run_once(
                snapshot_builder=lambda generated_at: sample_snapshot(),
                **kwargs,
            )
            generated_statuses.append(status)
            return status

        with tempfile.TemporaryDirectory() as tmpdir:
            status = run_scheduler_cycle(
                output_dir=Path(tmpdir),
                send=False,
                timezone_name="Asia/Hong_Kong",
                now=hk_time("2026-07-24T07:40:00"),
                runner=runner,
            )

            latest_markdown = Path(generated_statuses[0]["output_dir"]) / "fiona_telegram.md"
            text = latest_markdown.read_text(encoding="utf-8")

        self.assertTrue(status["ok"])
        self.assertEqual([item["brief_name"] for item in status["occurrence_results"]], ["morning"])
        self.assertTrue(generated_statuses[0]["scheduled_briefs"])
        self.assertIn("Fiona Morning", text)
        self.assertIn("Today’s Watch", text)

    def test_runtime_returns_content_payload_without_real_telegram(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            status = run_once(
                output_dir=Path(tmpdir),
                brief="daily",
                send=False,
                timezone_name="Asia/Hong_Kong",
                snapshot_builder=lambda generated_at: sample_snapshot(),
            )
            latest_markdown = Path(status["output_dir"]) / "fiona_telegram.md"
            text = latest_markdown.read_text(encoding="utf-8")

        self.assertTrue(status["ok"])
        self.assertFalse(status["send"])
        self.assertTrue(status["scheduled_briefs"])
        self.assertIn("Fiona Daily", text)
        self.assertIn("Important Events", text)
        self.assertIn("Fiona’s View", text)
        self.assertNotIn("brief_push", status)

    def test_telegram_payload_generation_is_mockable_and_text_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("app.fiona_runtime.split_message", return_value=["chunk one", "chunk two"]):
                with patch(
                    "app.fiona_runtime.telegram_send_message",
                    side_effect=[
                        {"ok": True, "result": {"message_id": 101}},
                        {"ok": True, "result": {"message_id": 102}},
                    ],
                ):
                    result = push_text("Fiona payload", Path(tmpdir) / "telegram.log", "Fiona Pipeline Test")

        self.assertTrue(result["ok"])
        self.assertEqual(result["delivery_status"], "success")
        self.assertEqual(result["message_ids"], [101, 102])
        self.assertEqual(result["total_chunks"], 2)

    def test_market_news_text_mode_preserves_legacy_sender_and_skips_image(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict("os.environ", {"FIONA_MARKET_NEWS_MODE": "text"}, clear=False), patch(
                "app.fiona_runtime.telegram_send_message",
                return_value={"ok": True, "result": {"message_id": 301}},
            ) as text_sender, patch(
                "app.fiona_runtime.telegram_send_document"
            ) as document_sender, patch(
                "app.fiona_runtime.build_market_news_view_model",
                side_effect=AssertionError("text mode must not build an image ViewModel"),
            ):
                status = run_once(
                    output_dir=Path(tmpdir),
                    brief="market-news",
                    send=True,
                    timezone_name="Asia/Hong_Kong",
                    snapshot_builder=lambda generated_at: sample_snapshot(),
                )

        self.assertTrue(status["brief_push"]["ok"])
        self.assertEqual(status["market_news_mode"], "text")
        self.assertNotIn("market_news_delivery", status)
        self.assertEqual(text_sender.call_count, 1)
        document_sender.assert_not_called()

    def test_market_news_shadow_mode_sends_text_but_not_document(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict("os.environ", {"FIONA_MARKET_NEWS_MODE": "shadow"}, clear=False), patch(
                "app.fiona_runtime.telegram_send_message",
                return_value={"ok": True, "result": {"message_id": 302}},
            ) as text_sender, patch(
                "app.fiona_runtime.telegram_send_document"
            ) as document_sender:
                status = run_once(
                    output_dir=Path(tmpdir),
                    brief="market-news",
                    send=True,
                    timezone_name="Asia/Hong_Kong",
                    snapshot_builder=lambda generated_at: sample_snapshot(),
                )

        self.assertTrue(status["brief_push"]["ok"])
        self.assertEqual(status["market_news_mode"], "shadow")
        self.assertTrue(status["market_news_delivery"]["image_generated"])
        self.assertTrue(status["market_news_delivery"]["image_validation"])
        self.assertTrue(status["market_news_delivery"]["cleanup_success"])
        self.assertEqual(text_sender.call_count, 1)
        document_sender.assert_not_called()

    def test_market_news_image_mode_sends_document_without_text(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict("os.environ", {"FIONA_MARKET_NEWS_MODE": "image"}, clear=False), patch(
                "app.fiona_runtime.telegram_send_message"
            ) as text_sender, patch(
                "app.fiona_runtime.telegram_send_document",
                return_value={"ok": True, "result": {"message_id": 303}},
            ) as document_sender:
                status = run_once(
                    output_dir=Path(tmpdir),
                    brief="market-news",
                    send=True,
                    timezone_name="Asia/Hong_Kong",
                    snapshot_builder=lambda generated_at: sample_snapshot(),
                )

        self.assertTrue(status["brief_push"]["ok"])
        self.assertEqual(status["brief_push"]["channel"], "document")
        self.assertEqual(status["market_news_delivery"]["final_delivery_channel"], "document")
        self.assertFalse(status["market_news_delivery"]["fallback_used"])
        text_sender.assert_not_called()
        document_sender.assert_called_once()

    def test_send_false_never_enters_market_news_delivery(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict("os.environ", {"FIONA_MARKET_NEWS_MODE": "image"}, clear=False), patch(
                "app.fiona_runtime.telegram_send_message"
            ) as text_sender, patch(
                "app.fiona_runtime.telegram_send_document"
            ) as document_sender:
                status = run_once(
                    output_dir=Path(tmpdir),
                    brief="market-news",
                    send=False,
                    timezone_name="Asia/Hong_Kong",
                    snapshot_builder=lambda generated_at: sample_snapshot(),
                )

        self.assertTrue(status["ok"])
        self.assertEqual(status["market_news_mode"], "image")
        self.assertNotIn("brief_push", status)
        text_sender.assert_not_called()
        document_sender.assert_not_called()


if __name__ == "__main__":
    unittest.main()
