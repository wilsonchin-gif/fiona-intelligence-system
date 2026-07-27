from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageDraw

from app.fiona_card_renderer import (
    COMPONENT_REGIONS,
    DataConfidence,
    EvidenceLevel,
    JudgmentConfidence,
    MarketRegime,
    derive_evidence_level,
    derive_historical_context,
    derive_market_regime,
    derive_watch_next,
    derive_confidence,
    draw_evidence_level,
    draw_fiona_view,
    draw_footer,
    draw_header,
    draw_heat_map,
    draw_historical_context,
    draw_key_markets,
    draw_market_regime,
    draw_narrative,
    draw_tags,
    draw_watch_next,
    draw_what_changed,
    font,
    font_asset_paths,
    format_watch_variable,
    render_market_news_card,
    semantic_limit,
    text_width,
    validate_component_regions,
    validate_font_assets,
    wrap_text_pixels,
)
from app.fiona_market_news_image import ChangedEventView, HeatMapView, build_market_news_view_model
from app.fiona_narrative import NarrativeEngine
from app.fiona_types import EventCategory, FionaEvent, MarketDirection


NOW = datetime(2026, 7, 24, 8, 0, tzinfo=timezone.utc)


def sample_event() -> FionaEvent:
    return FionaEvent(
        event_id="renderer_event",
        created_at=NOW,
        source="unit_test",
        category=EventCategory.MACRO,
        title="Fed liquidity repricing",
        what_happened="美债收益率抬升，科技与加密风险偏好同步降温",
        why_important="利率重新定价正在影响高估值资产与美元流动性",
        affected_assets=["SPX", "QQQ", "BTC", "RWA"],
        watch_next=["美债收益率与ETF资金是否形成同向确认"],
        fiona_view="跨市场信号仍需资金流验证。",
        impact_score=8,
        urgency_score=7,
        confidence_score=8,
        intelligence_score=82,
        market_direction=MarketDirection.BEARISH,
        raw_data={"narratives": ["macro_liquidity_repricing"], "funds_score": 38},
    )


def sample_snapshot() -> dict[str, object]:
    return {
        "generated_at": NOW.isoformat(),
        "heatmap": [
            {"key": "us", "label": "US Market", "score": 54, "status": "Neutral", "summary": "S&P 500 -0.34%"},
            {"key": "china", "label": "China Market", "score": 58, "status": "Neutral", "summary": "中证500 +0.42%"},
            {"key": "crypto", "label": "Crypto Market", "score": 47, "status": "Neutral", "summary": "BTC +0.28%"},
            {"key": "rwa", "label": "RWA Market", "score": 66, "status": "Neutral", "summary": "TVL +0.31%"},
        ],
        "us_market": {"primary": {"price": 6376.21, "change_pct": -0.34}},
        "crypto_market": {
            "btc": {"current_price": 118420, "change_pct": 0.28},
            "eth": {"current_price": 3728.4, "change_pct": -0.61},
        },
        "rwa_market": {"tvl": {"value": 13_420_000_000, "change_1d": 0.31}},
        "daily_market": {
            "quotes": [
                {"symbol": "^TNX", "price": 4.32, "change_pct": 0.06},
                {"symbol": "GC=F", "price": 2450.5, "change_pct": 1.2},
                {"symbol": "HSI", "price": 25572.88, "change_pct": 0.73},
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


class FionaCardRendererTest(unittest.TestCase):
    def test_renderer_creates_1080_by_1350_png(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = render_market_news_card(view_model(), Path(tmpdir) / "card.png")
            with Image.open(output) as image:
                self.assertEqual(image.size, (1080, 1350))
                self.assertEqual(image.format, "PNG")
                self.assertEqual(image.mode, "RGB")
            self.assertLess(output.stat().st_size, 1_500_000)

    def test_fixed_font_supports_chinese_english_and_numbers(self) -> None:
        validate_font_assets()
        selected_font = font(28)
        self.assertIsNotNone(selected_font.getmask("中文 Fiona 123").getbbox())

    def test_font_paths_are_repository_relative_and_linux_compatible(self) -> None:
        regular, bold = font_asset_paths(Path("/app"))

        self.assertEqual(regular, Path("/app/assets/fonts/NotoSansSC-Regular.otf"))
        self.assertEqual(bold, Path("/app/assets/fonts/NotoSansSC-Bold.otf"))
        source = Path(__import__("app.fiona_card_renderer", fromlist=[""]).__file__).read_text(
            encoding="utf-8"
        )
        self.assertNotIn("/Users/mac", source)
        self.assertNotIn("/System/Library/Fonts", source)

    def test_long_text_wraps_without_splitting_locked_asset_terms(self) -> None:
        image = Image.new("RGB", (800, 300), "black")
        draw = ImageDraw.Draw(image)
        selected_font = font(26)
        text = "过去四小时RWA机构采用与BTC ETF资金流出现分化，US10Y继续影响风险偏好。"
        lines = wrap_text_pixels(draw, text, selected_font, 360, 4)

        self.assertTrue(lines)
        self.assertTrue(all(text_width(draw, line, selected_font) <= 360 for line in lines))
        self.assertNotIn("R\nWA", "\n".join(lines))
        self.assertNotIn("BTC\n ETF", "\n".join(lines))
        self.assertNotIn("US\n10Y", "\n".join(lines))

    def test_semantic_limit_uses_one_ellipsis_and_no_partial_ascii_word(self) -> None:
        text = "市场正在观察RWAInstitutionalAdoption是否形成稳定资金确认以及跨市场共振"
        limited = semantic_limit(text, 22)

        self.assertLessEqual(limited.count("…"), 1)
        self.assertNotRegex(limited, r"RWAInstitut…$")
        self.assertNotIn(limited[-1], {"，", "；", "、", ",", ";"})

    def test_missing_data_keeps_fixed_heat_map_slots(self) -> None:
        snapshot = sample_snapshot()
        snapshot["heatmap"] = [
            {"key": "us", "label": "US Market", "score": 54, "status": "Neutral", "summary": "S&P 500 -0.34%"},
            {"key": "crypto", "label": "Crypto Market", "score": 47, "status": "Neutral", "summary": "BTC +0.28%"},
        ]
        snapshot["rwa_market"] = {}
        snapshot["errors"] = ["China unavailable", "RWA unavailable"]
        model = view_model(snapshot)

        self.assertEqual([item.key for item in model.heat_map], ["us", "china", "crypto", "rwa"])
        self.assertIsNone(model.heat_map[1].score)
        self.assertIsNone(model.heat_map[3].score)
        self.assertEqual(derive_confidence(model).data, DataConfidence.PARTIAL)

        with tempfile.TemporaryDirectory() as tmpdir:
            output = render_market_news_card(model, Path(tmpdir) / "missing.png")
            self.assertTrue(output.exists())

    def test_confidence_layer_supports_high_medium_and_low(self) -> None:
        full = view_model()
        partial_snapshot = sample_snapshot()
        partial_snapshot["errors"] = ["one source missing"]
        partial = view_model(partial_snapshot)
        limited = build_market_news_view_model({}, [], [], generated_at=NOW)

        self.assertEqual(derive_confidence(full).judgment, JudgmentConfidence.HIGH)
        self.assertEqual(derive_confidence(full).data, DataConfidence.VERIFIED)
        self.assertEqual(derive_confidence(partial).judgment, JudgmentConfidence.MEDIUM)
        self.assertEqual(derive_confidence(partial).data, DataConfidence.PARTIAL)
        self.assertEqual(derive_confidence(limited).judgment, JudgmentConfidence.LOW)
        self.assertEqual(derive_confidence(limited).data, DataConfidence.LIMITED)

    def test_all_required_components_have_regions_and_functions(self) -> None:
        self.assertEqual(
            set(COMPONENT_REGIONS),
            {
                "header",
                "market_regime",
                "fiona_view",
                "heat_map",
                "what_changed",
                "key_markets",
                "narrative",
                "watch_next",
                "historical_context",
                "tags",
                "footer",
            },
        )
        for component in (
            draw_header,
            draw_evidence_level,
            draw_market_regime,
            draw_fiona_view,
            draw_heat_map,
            draw_what_changed,
            draw_key_markets,
            draw_narrative,
            draw_watch_next,
            draw_historical_context,
            draw_tags,
            draw_footer,
        ):
            self.assertTrue(callable(component))
        validate_component_regions()

    def test_market_regime_supports_all_states(self) -> None:
        model = view_model()

        def with_heat(*values: tuple[int | None, str]):
            cards = tuple(
                HeatMapView(key, label, score, direction, "metric")
                for (key, label), (score, direction) in zip(
                    (("us", "US"), ("china", "China"), ("crypto", "Crypto"), ("rwa", "RWA")),
                    values,
                )
            )
            return replace(model, heat_map=cards)

        self.assertEqual(
            derive_market_regime(
                with_heat((72, "Bullish"), (68, "Bullish"), (64, "Neutral"), (66, "Bullish"))
            ).regime,
            MarketRegime.RISK_ON,
        )
        self.assertEqual(
            derive_market_regime(
                with_heat((32, "Bearish"), (40, "Bearish"), (36, "Bearish"), (42, "Neutral"))
            ).regime,
            MarketRegime.RISK_OFF,
        )
        self.assertEqual(
            derive_market_regime(
                with_heat((72, "Bullish"), (38, "Bearish"), (54, "Neutral"), (57, "Neutral"))
            ).regime,
            MarketRegime.TRANSITION,
        )
        self.assertEqual(derive_market_regime(model).regime, MarketRegime.NEUTRAL)
        self.assertEqual(
            derive_market_regime(
                with_heat((None, "Unavailable"), (None, "Unavailable"), (47, "Neutral"), (None, "Unavailable"))
            ).regime,
            MarketRegime.UNKNOWN,
        )

    def test_evidence_level_uses_sources_completeness_and_critical_fields(self) -> None:
        verified = replace(view_model(), source_count=3)
        self.assertEqual(derive_evidence_level(verified).level, EvidenceLevel.VERIFIED)

        strong = replace(verified, source_count=2)
        self.assertEqual(derive_evidence_level(strong).level, EvidenceLevel.STRONG)

        moderate = replace(verified, source_count=1)
        self.assertEqual(derive_evidence_level(moderate).level, EvidenceLevel.MODERATE)

        limited = build_market_news_view_model({}, [], [], generated_at=NOW)
        assessment = derive_evidence_level(limited)
        self.assertEqual(assessment.level, EvidenceLevel.LIMITED)
        self.assertEqual(assessment.source_count, 0)

    def test_watch_next_is_specific_deduplicated_and_limited_to_three(self) -> None:
        model = replace(
            view_model(),
            what_changed=(
                ChangedEventView("A", "Why A", "US10Y是否继续上行"),
                ChangedEventView("B", "Why B", "US10Y是否继续上行"),
                ChangedEventView("C", "Why C", "ETF Flow是否恢复净流入"),
                ChangedEventView("D", "Why D", "DXY是否继续走强"),
            ),
        )
        self.assertEqual(
            derive_watch_next(model),
            ("US10Y是否继续上行", "ETF Flow是否恢复净流入", "DXY是否继续走强"),
        )
        self.assertEqual(
            format_watch_variable("美债收益率与美元是否继续同向上行"),
            "US10Y / DXY direction",
        )
        self.assertEqual(
            format_watch_variable("ETF是否恢复净流入，稳定币供给是否同步扩张"),
            "ETF Flow / Stablecoin supply",
        )

    def test_historical_context_uses_rule_based_reference(self) -> None:
        liquidity = derive_historical_context(view_model())
        self.assertEqual(liquidity.topic, "Liquidity")
        self.assertIn("liquidity tightening", liquidity.reference)

        no_context = replace(
            view_model(),
            fiona_view="市场方向尚未收敛。",
            what_changed=(),
            current_narrative=(),
            tags=(),
        )
        self.assertEqual(derive_historical_context(no_context).topic, "Context")

    def test_long_and_missing_variants_keep_complete_layout(self) -> None:
        missing = build_market_news_view_model({}, [], [], generated_at=NOW)
        long_model = replace(view_model(), fiona_view="流动性、ETF、US10Y与RWA信号持续分化。" * 20)
        with tempfile.TemporaryDirectory() as tmpdir:
            for name, model in (("missing", missing), ("long", long_model)):
                output = render_market_news_card(model, Path(tmpdir) / f"{name}.png")
                with Image.open(output) as image:
                    self.assertEqual(image.size, (1080, 1350))
                    self.assertEqual(image.mode, "RGB")
        validate_component_regions()


if __name__ == "__main__":
    unittest.main()
