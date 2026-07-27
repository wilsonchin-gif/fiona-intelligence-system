from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from app.fiona_briefing import (
    build_daily_brief,
    build_evening_brief,
    build_morning_brief,
    build_weekly_brief,
)
from app.fiona_contracts import FionaTag, TagType
from app.fiona_market_news_image import (
    CAPTION_MAX_CHARS,
    CAPTION_MIN_CHARS,
    IMAGE_HEIGHT,
    IMAGE_WIDTH,
    build_market_news_prototype,
    build_market_news_tags,
    build_market_news_view_model,
    compose_market_news_caption,
    deduplicate_tags,
    read_png_dimensions,
    render_market_news_png,
    render_market_news_svg,
)
from app.fiona_narrative import NarrativeEngine
from app.fiona_types import EventCategory, FionaEvent, MarketDirection


NOW = datetime(2026, 7, 24, 8, 0, tzinfo=timezone.utc)


def sample_event(**overrides) -> FionaEvent:
    values = {
        "event_id": "phase2a_event",
        "created_at": NOW,
        "source": "unit_test",
        "category": EventCategory.MACRO,
        "title": "Fed liquidity repricing",
        "what_happened": "美债收益率抬升，风险偏好边际降温",
        "why_important": "宏观流动性会同时影响美股科技与加密资产",
        "affected_assets": ["SPX", "QQQ", "BTC", "RWA"],
        "watch_next": ["美债收益率与ETF资金是否形成同向确认"],
        "fiona_view": "跨市场信号仍需资金流验证。",
        "impact_score": 8,
        "urgency_score": 7,
        "confidence_score": 8,
        "intelligence_score": 82,
        "market_direction": MarketDirection.BEARISH,
        "raw_data": {"narratives": ["macro_liquidity_repricing"], "funds_score": 38},
    }
    values.update(overrides)
    return FionaEvent(**values)


def sample_snapshot() -> dict[str, object]:
    return {
        "generated_at": NOW.isoformat(),
        "generated_at_display": "2026-07-24 16:00",
        "heatmap": [
            {"key": "us", "label": "US Market", "score": 54, "status": "Neutral", "summary": "S&P 500 -0.34%"},
            {"key": "china", "label": "China Market", "score": 58, "status": "Neutral", "summary": "中证500 +0.42%"},
            {"key": "crypto", "label": "Crypto Market", "score": 47, "status": "Neutral", "summary": "BTC +0.28%"},
            {"key": "rwa", "label": "RWA Market", "score": 66, "status": "Neutral", "summary": "TVL +0.31%"},
        ],
        "us_market": {"primary": {"name": "S&P 500", "price": 6376.21, "change_pct": -0.34}},
        "crypto_market": {
            "btc": {"current_price": 118420, "change_pct": 0.28},
            "eth": {"current_price": 3728.4, "change_pct": -0.61},
        },
        "rwa_market": {"tvl": {"value": 13_420_000_000, "change_1d": 0.31}},
        "daily_market": {
            "quotes": [
                {"symbol": "HSI", "price": 25572.88, "change_pct": 0.73},
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


def view_model(snapshot: dict[str, object] | None = None):
    events = [sample_event()]
    narratives = NarrativeEngine().build(events, now=NOW)
    return build_market_news_view_model(snapshot or sample_snapshot(), events, narratives, generated_at=NOW)


class FionaMarketNewsImageTest(unittest.TestCase):
    def test_active_image_modules_have_no_macos_command_dependency(self) -> None:
        root = Path(__file__).resolve().parent.parent
        for relative_path in (
            "app/fiona_market_news_image.py",
            "app/fiona_card_renderer.py",
            "app/fiona_market_news_delivery.py",
        ):
            source = (root / relative_path).read_text(encoding="utf-8")
            self.assertNotIn("/usr/bin/sips", source)
            self.assertNotIn("subprocess.run", source)
            self.assertNotIn("/Users/mac", source)

    def test_view_model_keeps_snapshot_data_consistent(self) -> None:
        model = view_model()

        self.assertEqual(model.heat_map[0].score, 54)
        self.assertEqual(model.key_markets[0].value, "$118,420")
        self.assertEqual(model.key_markets[1].value, "6,376.21")
        self.assertEqual(model.key_markets[2].value, "4.32%")
        self.assertEqual(model.key_markets[4].value, "$13.42B")
        self.assertEqual(model.data_quality.status, "Full")

    def test_missing_heat_map_slots_do_not_borrow_neighbor_data(self) -> None:
        snapshot = sample_snapshot()
        snapshot["heatmap"] = [
            {"key": "us", "label": "US Market", "score": 54, "status": "Neutral", "summary": "S&P 500 -0.34%"},
            {"key": "crypto", "label": "Crypto Market", "score": 47, "status": "Neutral", "summary": "BTC +0.28%"},
        ]
        model = view_model(snapshot)

        self.assertEqual([item.key for item in model.heat_map], ["us", "china", "crypto", "rwa"])
        self.assertIsNone(model.heat_map[1].score)
        self.assertEqual(model.heat_map[1].direction, "Unavailable")
        self.assertEqual(model.heat_map[2].score, 47)
        self.assertIsNone(model.heat_map[3].score)

    def test_caption_has_required_length_view_and_fallback(self) -> None:
        model = view_model()
        caption = compose_market_news_caption(model)

        self.assertGreaterEqual(len(caption), CAPTION_MIN_CHARS)
        self.assertLessEqual(len(caption), CAPTION_MAX_CHARS)
        self.assertIn("【Fiona’s View】", caption)
        self.assertIn("#BTC", caption)

        missing = build_market_news_view_model({}, [], [], generated_at=NOW)
        fallback = compose_market_news_caption(missing)
        self.assertGreaterEqual(len(fallback), CAPTION_MIN_CHARS)
        self.assertLessEqual(len(fallback), CAPTION_MAX_CHARS)
        self.assertIn("暂无新增高价值变化", fallback)

    def test_tags_are_classified_deduplicated_and_limited(self) -> None:
        event = sample_event(affected_assets=["BTC", "BTC", "RWA"], what_happened="Fed与BTC流动性变化")
        tags = build_market_news_tags([event, event], [])
        duplicate = FionaTag("asset_btc", "Bitcoin", TagType.ASSET, telegram_hashtag="#BTC")
        combined = deduplicate_tags([duplicate, duplicate, *tags])

        self.assertLessEqual(len(tags), 8)
        self.assertEqual(len({tag.canonical_id for tag in combined}), len(combined))
        self.assertEqual(len({tag.telegram_hashtag.lower() for tag in combined}), len(combined))
        self.assertTrue(all(isinstance(tag.tag_type, TagType) for tag in tags))

    def test_image_is_png_1080_by_1350_and_svg_contains_chinese(self) -> None:
        model = view_model()
        svg = render_market_news_svg(model)
        self.assertIn("美债收益率", svg)
        self.assertIn("FIONA’S VIEW", svg)

        with tempfile.TemporaryDirectory() as tmpdir:
            output = render_market_news_png(model, Path(tmpdir) / "market_news.png")
            self.assertEqual(read_png_dimensions(output), (IMAGE_WIDTH, IMAGE_HEIGHT))
            self.assertGreater(output.stat().st_size, 10_000)

    def test_long_text_wraps_without_changing_canvas_size(self) -> None:
        snapshot = sample_snapshot()
        snapshot["wilson_view"] = (
            "过去四小时的变化来自美债收益率、美元流动性、美股科技权重、比特币ETF资金流、稳定币供给、"
            "RWA机构采用以及中国核心资产承接之间的信号分化。当前价格表现尚未形成稳定的跨市场共振，"
            "下一轮需要继续验证ETF资金是否恢复、美元与美债是否同向上行，以及RWA TVL能否保持流入。"
        )
        model = view_model(snapshot)
        svg = render_market_news_svg(model)

        self.assertLessEqual(svg.count("<text"), 80)
        with tempfile.TemporaryDirectory() as tmpdir:
            output = render_market_news_png(model, Path(tmpdir) / "long.png")
            self.assertEqual(read_png_dimensions(output), (1080, 1350))

    def test_renderer_failure_preserves_original_text_fallback(self) -> None:
        def fail_converter(_source: Path, _target: Path) -> None:
            raise RuntimeError("renderer unavailable")

        with tempfile.TemporaryDirectory() as tmpdir:
            result = build_market_news_prototype(
                view_model(),
                Path(tmpdir) / "failed.png",
                original_text="原有 Fiona Market News 文字内容",
                converter=fail_converter,
            )

        self.assertEqual(result.mode, "text_fallback")
        self.assertEqual(result.fallback_text, "原有 Fiona Market News 文字内容")
        self.assertIsNone(result.image_path)
        self.assertIn("renderer unavailable", result.error)

    def test_missing_image_output_also_uses_text_fallback(self) -> None:
        def empty_converter(_source: Path, _target: Path) -> None:
            return None

        with tempfile.TemporaryDirectory() as tmpdir:
            result = build_market_news_prototype(
                view_model(),
                Path(tmpdir) / "missing.png",
                original_text="原文字模式",
                converter=empty_converter,
            )

        self.assertEqual(result.mode, "text_fallback")
        self.assertEqual(result.fallback_text, "原文字模式")
        self.assertIn("did not create", result.error)

    def test_other_four_brief_builders_remain_available(self) -> None:
        events = [sample_event()]
        narratives = NarrativeEngine().build(events, now=NOW)
        snapshot = sample_snapshot()

        self.assertEqual(build_morning_brief(events, narratives, generated_at=NOW).title, "Fiona Morning")
        self.assertEqual(build_evening_brief(events, narratives, generated_at=NOW).title, "Fiona Evening")
        self.assertEqual(build_daily_brief(events, narratives, snapshot=snapshot, generated_at=NOW).title, "Fiona Daily")
        self.assertEqual(build_weekly_brief(events, narratives, snapshot=snapshot, generated_at=NOW).title, "Fiona Weekly")


if __name__ == "__main__":
    unittest.main()
