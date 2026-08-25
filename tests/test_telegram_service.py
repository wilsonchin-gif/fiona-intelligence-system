from __future__ import annotations

import io
import json
import os
import socket
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

from app.telegram_service import (
    TelegramRequestError,
    TelegramUnknownDeliveryError,
    multipart_form_data,
    normalize_caption,
    send_document_with_caption,
    send_photo_with_caption,
    telegram_config,
    telegram_document_request,
    telegram_photo_request,
)


class TelegramServiceTest(unittest.TestCase):
    def test_send_photo_multipart_contains_caption_parse_mode_chat_and_png(self) -> None:
        captured = {}

        def fake_request(token, method, data, content_type):
            captured.update(token=token, method=method, data=data, content_type=content_type)
            return {"ok": True, "result": {"message_id": 87}}

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "card.png"
            path.write_bytes(b"png-bytes")
            with patch(
                "app.telegram_service.telegram_config",
                return_value={"bot_token": "secret-test-token", "chat_id": "-100-group"},
            ), patch("app.telegram_service.telegram_photo_request", side_effect=fake_request):
                response = send_photo_with_caption(path, "Fiona caption", parse_mode="MarkdownV2")

        self.assertEqual(response["result"]["message_id"], 87)
        self.assertEqual(captured["method"], "sendPhoto")
        self.assertIn(b'name="chat_id"', captured["data"])
        self.assertIn(b'name="caption"', captured["data"])
        self.assertIn(b'name="parse_mode"', captured["data"])
        self.assertIn(b"MarkdownV2", captured["data"])
        self.assertIn(b'name="photo"; filename="card.png"', captured["data"])
        self.assertIn(b"Content-Type: image/png", captured["data"])

    def test_group_id_is_primary_chat_target(self) -> None:
        previous = {name: os.environ.get(name) for name in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_GROUP_ID", "TELEGRAM_CHAT_ID", "TELEGRAM_CHANNEL_ID")}
        try:
            os.environ["TELEGRAM_BOT_TOKEN"] = "test-token"
            os.environ["TELEGRAM_GROUP_ID"] = "-100-group"
            os.environ["TELEGRAM_CHAT_ID"] = "-100-chat"
            os.environ["TELEGRAM_CHANNEL_ID"] = "@channel"

            config = telegram_config()

            self.assertEqual(config["bot_token"], "test-token")
            self.assertEqual(config["chat_id"], "-100-group")
        finally:
            for name, value in previous.items():
                if value is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = value

    def test_chat_id_is_supported_as_fallback(self) -> None:
        previous = {name: os.environ.get(name) for name in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_GROUP_ID", "TELEGRAM_CHAT_ID", "TELEGRAM_CHANNEL_ID")}
        try:
            os.environ["TELEGRAM_BOT_TOKEN"] = "test-token"
            os.environ.pop("TELEGRAM_GROUP_ID", None)
            os.environ["TELEGRAM_CHAT_ID"] = "-100-chat"
            os.environ["TELEGRAM_CHANNEL_ID"] = "@channel"

            config = telegram_config()

            self.assertEqual(config["chat_id"], "-100-chat")
        finally:
            for name, value in previous.items():
                if value is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = value

    def test_send_document_multipart_contains_caption_chat_and_png(self) -> None:
        captured = {}

        def fake_request(token, method, data, content_type):
            captured.update(
                token=token,
                method=method,
                data=data,
                content_type=content_type,
            )
            return {"ok": True, "result": {"message_id": 88}}

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "card.png"
            path.write_bytes(b"png-bytes")
            with patch(
                "app.telegram_service.telegram_config",
                return_value={"bot_token": "secret-test-token", "chat_id": "-100-group"},
            ), patch("app.telegram_service.telegram_document_request", side_effect=fake_request):
                response = send_document_with_caption(path, "Fiona caption")

        self.assertEqual(response["result"]["message_id"], 88)
        self.assertEqual(captured["method"], "sendDocument")
        self.assertIn(b'name="chat_id"', captured["data"])
        self.assertIn(b"-100-group", captured["data"])
        self.assertIn(b'name="caption"', captured["data"])
        self.assertIn("Fiona caption".encode(), captured["data"])
        self.assertIn(b'name="document"; filename="card.png"', captured["data"])
        self.assertIn(b"Content-Type: image/png", captured["data"])
        self.assertIn("multipart/form-data", captured["content_type"])

    def test_multipart_closes_file_handle(self) -> None:
        opener = mock_open(read_data=b"file-content")
        with patch.object(Path, "open", opener):
            multipart_form_data({"chat_id": "1"}, {"document": Path("card.png")})
        opener.return_value.__enter__.assert_called_once()
        opener.return_value.__exit__.assert_called_once()

    def test_photo_multipart_closes_file_handle(self) -> None:
        opener = mock_open(read_data=b"photo-content")
        with patch.object(Path, "open", opener):
            multipart_form_data({"chat_id": "1"}, {"photo": Path("card.png")})
        opener.return_value.__enter__.assert_called_once()
        opener.return_value.__exit__.assert_called_once()

    def test_caption_normalization_is_safe_plain_text(self) -> None:
        caption = "Fiona <b>plain</b>\n" + "市场状态。" * 600
        normalized = normalize_caption(caption)
        self.assertLessEqual(len(normalized), 1024)
        self.assertIn("<b>plain</b>", normalized)
        self.assertFalse(normalized.endswith("<"))

    def test_timeout_and_network_errors_are_unknown_delivery(self) -> None:
        for error in (
            socket.timeout("timeout"),
            urllib.error.URLError("offline"),
        ):
            with patch("app.telegram_service.urllib.request.urlopen", side_effect=error):
                with self.assertRaises(TelegramUnknownDeliveryError) as context:
                    telegram_document_request("secret-token", "sendDocument", b"x", "multipart/form-data")
            self.assertEqual(context.exception.delivery_state, "unknown")
            self.assertNotIn("secret-token", str(context.exception))

    def test_photo_timeout_and_server_error_are_unknown_delivery(self) -> None:
        server_error = urllib.error.HTTPError(
            "https://api.telegram.org/botsecret-token/sendPhoto",
            502,
            "Bad Gateway",
            {},
            io.BytesIO(b"bad"),
        )
        for error in (socket.timeout("timeout"), server_error):
            with patch("app.telegram_service.urllib.request.urlopen", side_effect=error):
                with self.assertRaises(TelegramUnknownDeliveryError) as context:
                    telegram_photo_request("secret-token", "sendPhoto", b"x", "multipart/form-data")
            self.assertEqual(context.exception.delivery_state, "unknown")
            self.assertNotIn("secret-token", str(context.exception))

    def test_photo_http_4xx_is_definite_failure(self) -> None:
        error = urllib.error.HTTPError(
            "https://api.telegram.org/botsecret-token/sendPhoto",
            400,
            "Bad Request",
            {},
            io.BytesIO(b"bad"),
        )
        with patch("app.telegram_service.urllib.request.urlopen", side_effect=error):
            with self.assertRaises(TelegramRequestError) as context:
                telegram_photo_request("secret-token", "sendPhoto", b"x", "multipart/form-data")
        self.assertEqual(context.exception.delivery_state, "failed")
        self.assertEqual(context.exception.status_code, 400)

    def test_photo_api_rejection_is_definite_failure(self) -> None:
        response = MagicMock()
        response.__enter__.return_value = response
        response.read.return_value = json.dumps(
            {"ok": False, "error_code": 400, "description": "Bad Request"}
        ).encode()
        with patch("app.telegram_service.urllib.request.urlopen", return_value=response):
            with self.assertRaises(TelegramRequestError) as context:
                telegram_photo_request("secret-token", "sendPhoto", b"x", "multipart/form-data")
        self.assertEqual(context.exception.category, "telegram_api_rejected")
        self.assertNotIn("secret-token", str(context.exception))

    def test_photo_malformed_json_is_unknown_delivery(self) -> None:
        response = MagicMock()
        response.__enter__.return_value = response
        response.read.return_value = b"not-json"
        with patch("app.telegram_service.urllib.request.urlopen", return_value=response):
            with self.assertRaises(TelegramUnknownDeliveryError) as context:
                telegram_photo_request("secret-token", "sendPhoto", b"x", "multipart/form-data")
        self.assertEqual(context.exception.category, "telegram_response_parse_error")

    def test_http_error_is_definite_and_sanitized(self) -> None:
        error = urllib.error.HTTPError(
            "https://api.telegram.org/botsecret-token/sendDocument",
            400,
            "Bad Request",
            {},
            io.BytesIO(b"bad"),
        )
        with patch("app.telegram_service.urllib.request.urlopen", side_effect=error):
            with self.assertRaises(TelegramRequestError) as context:
                telegram_document_request("secret-token", "sendDocument", b"x", "multipart/form-data")
        self.assertEqual(context.exception.delivery_state, "failed")
        self.assertEqual(context.exception.status_code, 400)
        self.assertNotIn("secret-token", str(context.exception))

    def test_invalid_json_response_is_unknown_delivery(self) -> None:
        response = MagicMock()
        response.__enter__.return_value = response
        response.read.return_value = b"not-json"
        with patch("app.telegram_service.urllib.request.urlopen", return_value=response):
            with self.assertRaises(TelegramUnknownDeliveryError) as context:
                telegram_document_request("secret-token", "sendDocument", b"x", "multipart/form-data")
        self.assertEqual(context.exception.category, "telegram_response_parse_error")

    def test_invalid_json_shape_is_unknown_delivery(self) -> None:
        response = MagicMock()
        response.__enter__.return_value = response
        response.read.return_value = b"[]"
        with patch("app.telegram_service.urllib.request.urlopen", return_value=response):
            with self.assertRaises(TelegramUnknownDeliveryError) as context:
                telegram_document_request("secret-token", "sendDocument", b"x", "multipart/form-data")
        self.assertEqual(context.exception.category, "telegram_response_parse_error")

    def test_api_rejection_is_definite_failure(self) -> None:
        response = MagicMock()
        response.__enter__.return_value = response
        response.read.return_value = json.dumps(
            {"ok": False, "error_code": 400, "description": "Bad Request"}
        ).encode()
        with patch("app.telegram_service.urllib.request.urlopen", return_value=response):
            with self.assertRaises(TelegramRequestError) as context:
                telegram_document_request("secret-token", "sendDocument", b"x", "multipart/form-data")
        self.assertEqual(context.exception.category, "telegram_api_rejected")
        self.assertEqual(context.exception.delivery_state, "failed")


if __name__ == "__main__":
    unittest.main()
