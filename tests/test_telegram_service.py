from __future__ import annotations

import os
import unittest

from app.telegram_service import telegram_config


class TelegramServiceTest(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
