from __future__ import annotations

import re
import unittest
from dataclasses import replace

from app.fiona_contracts import FionaTag, TagType
from app.fiona_market_news_image import (
    CAPTION_BODY_MAX_CHARS,
    CAPTION_BODY_MIN_CHARS,
    CAPTION_DISCLAIMER,
    CAPTION_MAX_CHARS,
    ChangedEventView,
    DataQualityView,
    HeatMapView,
    compose_market_news_caption,
    count_cjk_characters,
    select_caption_hashtags,
)
from app.fiona_narrative import NarrativeEngine
from scripts.generate_fiona_market_news_prototypes import (
    NOW,
    full_snapshot,
    long_text_snapshot,
    missing_snapshot,
    prototype_events,
)
from app.fiona_market_news_image import build_market_news_view_model


def base_model(snapshot=None):
    events = prototype_events()
    narratives = NarrativeEngine().build(events, now=NOW)
    return build_market_news_view_model(
        snapshot or full_snapshot(),
        events,
        narratives,
        generated_at=NOW,
    )


def regime_model(kind: str):
    model = base_model()
    configurations = {
        "risk_on": ((72, "Bullish"), (68, "Bullish"), (64, "Bullish"), (66, "Bullish")),
        "risk_off": ((30, "Bearish"), (34, "Bearish"), (36, "Bearish"), (32, "Bearish")),
        "transition": ((72, "Bullish"), (48, "Neutral"), (35, "Bearish"), (64, "Bullish")),
    }
    cards = tuple(
        HeatMapView(
            key=original.key,
            label=original.label,
            score=score,
            direction=direction,
            key_metric=original.key_metric,
        )
        for original, (score, direction) in zip(model.heat_map, configurations[kind])
    )
    return replace(model, heat_map=cards)


def section(caption: str, name: str, next_name: str | None = None) -> str:
    start = caption.index(f"【{name}】")
    if next_name is None:
        return caption[start:]
    end = caption.index(f"【{next_name}】", start)
    return caption[start:end]


class FionaMarketNewsCaptionRCTest(unittest.TestCase):
    def test_full_missing_and_long_scenarios_stay_in_caption_limits(self) -> None:
        for snapshot in (full_snapshot(), missing_snapshot(), long_text_snapshot()):
            caption = compose_market_news_caption(base_model(snapshot))
            self.assertGreaterEqual(len(caption), 220)
            self.assertLessEqual(len(caption), CAPTION_MAX_CHARS)
            self.assertGreaterEqual(count_cjk_characters(caption), CAPTION_BODY_MIN_CHARS)
            self.assertLessEqual(count_cjk_characters(caption), CAPTION_BODY_MAX_CHARS)
            self.assertTrue(caption.endswith(CAPTION_DISCLAIMER))

    def test_fiona_view_is_present_and_uses_one_to_three_complete_sentences(self) -> None:
        caption = compose_market_news_caption(base_model())
        view = section(caption, "Fiona’s View", "Watch Next")
        sentences = re.findall(r"[^。！？]+[。！？]", view.split("\n", 1)[1])
        self.assertGreaterEqual(len(sentences), 1)
        self.assertLessEqual(len(sentences), 3)
        self.assertNotIn("…", view)

    def test_market_regime_outputs_all_supported_release_scenarios(self) -> None:
        expected = {
            "risk_on": "Risk On",
            "risk_off": "Risk Off",
            "transition": "Transition",
        }
        for kind, label in expected.items():
            self.assertIn(f"{label}｜Evidence:", compose_market_news_caption(regime_model(kind)))

        unknown = base_model(missing_snapshot())
        caption = compose_market_news_caption(unknown)
        self.assertIn("Unknown｜Evidence: Limited", caption)
        self.assertIn("暂不形成明确市场状态判断", caption)

    def test_limited_evidence_removes_unverified_cause_and_softens_view(self) -> None:
        model = replace(
            base_model(),
            source_count=0,
            data_quality=DataQualityView(
                status="Degraded",
                missing_fields=("heat_map.us", "key_markets.btc", "key_markets.spx"),
            ),
        )
        caption = compose_market_news_caption(model)
        changed = section(caption, "What Changed", "Fiona’s View")
        self.assertIn("Evidence: Limited", caption)
        self.assertIn("市场影响仍待更多数据确认", changed)
        self.assertIn("当前证据仍有限", caption)
        self.assertNotIn(model.what_changed[0].why, changed)

    def test_watch_next_is_specific_deduplicated_and_limited_to_three(self) -> None:
        model = base_model()
        caption = compose_market_news_caption(model)
        watch = section(caption, "Watch Next")
        bullets = [line for line in watch.splitlines() if line.startswith("• ")]
        self.assertLessEqual(len(bullets), 3)
        self.assertEqual(len(bullets), len({item.casefold() for item in bullets}))
        self.assertFalse(any(item in watch for item in ("关注市场变化", "关注宏观", "关注风险", "关注 BTC")))

    def test_hashtags_are_limited_and_alias_deduplicated_without_truncation(self) -> None:
        tags = (
            FionaTag("asset_btc", "BTC", TagType.ASSET, telegram_hashtag="#BTC"),
            FionaTag("asset_bitcoin", "Bitcoin", TagType.ASSET, telegram_hashtag="#Bitcoin"),
            FionaTag("institution_fed", "Fed", TagType.INSTITUTION, telegram_hashtag="#Fed"),
            FionaTag("institution_federal_reserve", "Federal Reserve", TagType.INSTITUTION, telegram_hashtag="#FederalReserve"),
            FionaTag("asset_eth", "ETH", TagType.ASSET, telegram_hashtag="#ETH"),
            FionaTag("asset_rwa", "RWA", TagType.ASSET, telegram_hashtag="#RWA"),
            FionaTag("risk_liquidity", "Liquidity", TagType.RISK, telegram_hashtag="#Liquidity"),
            FionaTag("market_crypto", "Crypto", TagType.MARKET, telegram_hashtag="#Crypto"),
            FionaTag("market_us", "US Market", TagType.MARKET, telegram_hashtag="#USMarket"),
            FionaTag("market_global", "Markets", TagType.MARKET, telegram_hashtag="#Markets"),
        )
        selected = select_caption_hashtags(replace(base_model(), tags=tags))
        self.assertLessEqual(len(selected), 8)
        self.assertFalse({"#BTC", "#Bitcoin"}.issubset(selected))
        self.assertFalse({"#Fed", "#FederalReserve"}.issubset(selected))
        self.assertTrue(all(re.fullmatch(r"#[A-Za-z0-9_]+", item) for item in selected))

    def test_caption_does_not_dump_heat_map_or_key_market_values(self) -> None:
        model = base_model()
        caption = compose_market_news_caption(model)
        self.assertFalse(all(card.label in caption for card in model.heat_map))
        self.assertFalse(all(item.value in caption for item in model.key_markets))
        self.assertNotIn("/100", caption)

    def test_what_changed_keeps_event_and_why_but_moves_watch_out(self) -> None:
        model = base_model()
        caption = compose_market_news_caption(model)
        changed = section(caption, "What Changed", "Fiona’s View")
        first = model.what_changed[0]
        self.assertIn(first.event, changed)
        self.assertIn(first.why, changed)
        self.assertNotIn(first.watch, changed)
        self.assertIn(first.watch, section(caption, "Watch Next"))

    def test_missing_data_does_not_emit_market_values_or_strong_direction(self) -> None:
        model = build_market_news_view_model({}, [], [], generated_at=NOW)
        caption = compose_market_news_caption(model)
        self.assertIn("Unknown｜Evidence: Limited", caption)
        self.assertIn("当前信号覆盖不足", caption)
        self.assertNotIn("Risk On", caption)
        self.assertNotIn("Risk Off", caption)
        self.assertNotRegex(caption, r"\$[0-9]")

    def test_no_high_confidence_narrative_is_explicit(self) -> None:
        model = replace(base_model(), current_narrative=())
        caption = compose_market_news_caption(model)
        self.assertIn("暂无高置信主叙事", caption)
        self.assertIn("主叙事是否获得资金流与价格确认", caption)

    def test_long_content_is_semantically_compressed_without_broken_structure(self) -> None:
        model = replace(
            base_model(long_text_snapshot()),
            what_changed=tuple(
                ChangedEventView(
                    event=("超长事件描述" * 20) + str(index),
                    why=("跨市场证据仍需要成交量与资金流共同确认" * 12),
                    watch=("US10Y与DXY是否继续同向上行并得到成交量确认" * 8),
                )
                for index in range(4)
            ),
            fiona_view=("当前市场状态由多个相互分化的变量共同驱动。" * 20),
        )
        caption = compose_market_news_caption(model)
        self.assertLessEqual(len(caption), CAPTION_MAX_CHARS)
        self.assertNotIn("…", caption)
        for heading in ("Market Regime", "What Changed", "Fiona’s View", "Watch Next"):
            self.assertEqual(caption.count(f"【{heading}】"), 1)
        self.assertEqual(caption.count("【"), caption.count("】"))
        self.assertNotRegex(caption, r"<[^>]*$")
        self.assertTrue(caption.endswith(CAPTION_DISCLAIMER))

    def test_trading_prediction_and_marketing_language_is_not_emitted(self) -> None:
        model = replace(
            base_model(),
            fiona_view=(
                "重磅：BTC将上涨至150000，这是大机会和财富密码。"
                "Fiona精准预测牛市启动，投资者应买入并抄底。"
            ),
        )
        caption = compose_market_news_caption(model)
        for forbidden in (
            "重磅", "暴涨", "暴跌预警", "大机会", "千载难逢", "牛市启动",
            "财富密码", "精准预测", "独家发现", "将上涨至", "目标价",
        ):
            self.assertNotIn(forbidden, caption)
        self.assertNotIn("买入", caption)
        self.assertNotIn("抄底", caption)


if __name__ == "__main__":
    unittest.main()
