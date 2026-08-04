from __future__ import annotations

import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PRODUCTION_CONFIG = ROOT / "railway.toml"
VALIDATOR_CONFIG = ROOT / "railway.validator.toml"


class RailwayValidatorConfigTests(unittest.TestCase):
    def test_production_config_remains_scheduler_only(self) -> None:
        config = self._load(PRODUCTION_CONFIG)

        self.assertEqual(config["build"]["builder"], "NIXPACKS")
        self.assertEqual(
            config["deploy"]["startCommand"],
            "python3 -m app.fiona_runtime --send run-scheduler",
        )
        self.assertEqual(config["deploy"]["restartPolicyType"], "ON_FAILURE")
        self.assertNotIn("cronSchedule", config["deploy"])

    def test_validator_config_is_one_shot_and_isolated(self) -> None:
        config = self._load(VALIDATOR_CONFIG)
        text = VALIDATOR_CONFIG.read_text(encoding="utf-8")

        self.assertEqual(config["build"]["builder"], "NIXPACKS")
        self.assertEqual(
            config["deploy"]["startCommand"],
            "python3 -m app.fiona_runtime validate-market-news-image",
        )
        self.assertEqual(config["deploy"]["restartPolicyType"], "NEVER")
        self.assertNotIn("cronSchedule", config["deploy"])
        self.assertNotIn("healthcheckPath", config["deploy"])
        self.assertNotIn("run-scheduler", text)
        self.assertNotIn("--send", text)

    def test_validator_config_contains_no_secrets_or_local_dependencies(self) -> None:
        text = VALIDATOR_CONFIG.read_text(encoding="utf-8")
        forbidden = (
            "TELEGRAM_BOT_TOKEN",
            "TELEGRAM_GROUP_ID",
            "TELEGRAM_CHAT_ID",
            "/Users/mac",
            "/usr/bin/sips",
        )

        for value in forbidden:
            with self.subTest(value=value):
                self.assertNotIn(value, text)

    def test_validator_config_is_not_the_default_production_config(self) -> None:
        production_text = PRODUCTION_CONFIG.read_text(encoding="utf-8")

        self.assertEqual(PRODUCTION_CONFIG.name, "railway.toml")
        self.assertEqual(VALIDATOR_CONFIG.name, "railway.validator.toml")
        self.assertNotIn(VALIDATOR_CONFIG.name, production_text)
        self.assertNotEqual(PRODUCTION_CONFIG.resolve(), VALIDATOR_CONFIG.resolve())

    @staticmethod
    def _load(path: Path) -> dict[str, object]:
        with path.open("rb") as config_file:
            return tomllib.load(config_file)


if __name__ == "__main__":
    unittest.main()
