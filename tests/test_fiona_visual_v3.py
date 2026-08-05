from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from PIL import Image
from PIL import ImageDraw

from app.fiona_card_renderer import (
    BACKGROUND,
    COMPONENT_REGIONS,
    FIONA_GOLD,
    PRIMARY_TEXT,
    TYPOGRAPHY,
    VISUAL_SYSTEM_VERSION,
    font,
    render_market_news_card,
    validate_component_regions,
    wrap_text_pixels,
)
from app.fiona_market_news_image import build_market_news_view_model
from tests.test_fiona_card_renderer import NOW, sample_snapshot, view_model


def relative_luminance(value: str) -> float:
    channels = [int(value[index : index + 2], 16) / 255 for index in (1, 3, 5)]

    def linear(channel: float) -> float:
        return channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4

    red, green, blue = (linear(channel) for channel in channels)
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def contrast_ratio(first: str, second: str) -> float:
    light, dark = sorted((relative_luminance(first), relative_luminance(second)), reverse=True)
    return (light + 0.05) / (dark + 0.05)


class FionaVisualV3Test(unittest.TestCase):
    def test_visual_system_is_v3_and_judgment_first(self) -> None:
        self.assertEqual(VISUAL_SYSTEM_VERSION, "V3")
        self.assertLess(COMPONENT_REGIONS["fiona_view"][1], COMPONENT_REGIONS["heat_map"][1])
        self.assertGreater(TYPOGRAPHY["fiona_view"], TYPOGRAPHY["section_title"])
        self.assertGreaterEqual(TYPOGRAPHY["product_title"], 40)
        validate_component_regions()

    def test_primary_text_and_brand_accent_have_mobile_contrast(self) -> None:
        self.assertGreaterEqual(contrast_ratio(PRIMARY_TEXT, BACKGROUND), 7.0)
        self.assertGreaterEqual(contrast_ratio(FIONA_GOLD, BACKGROUND), 4.5)

    def test_full_missing_and_stress_variants_render_fixed_pngs(self) -> None:
        full = view_model()
        missing = build_market_news_view_model({}, [], [], generated_at=NOW)
        stress = replace(
            view_model(sample_snapshot()),
            fiona_view=(
                "过去四小时的变化来自宏观利率、美元流动性、美股科技权重、BTC ETF资金流、"
                "稳定币供给与RWA机构采用之间的持续分化。"
            ) * 8,
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            for name, model in (("full", full), ("missing", missing), ("stress", stress)):
                output = render_market_news_card(model, Path(tmpdir) / f"{name}.png")
                with Image.open(output) as image:
                    self.assertEqual(image.size, (1080, 1350))
                    self.assertEqual(image.format, "PNG")
                    self.assertEqual(image.getpixel((12, 2)), tuple(int(FIONA_GOLD[i : i + 2], 16) for i in (1, 3, 5)))
                self.assertLess(output.stat().st_size, 1_500_000)

    def test_share_identity_and_non_predictive_labels_are_rendered(self) -> None:
        renderer_source = Path(
            __import__("app.fiona_card_renderer", fromlist=[""]).__file__
        ).read_text(encoding="utf-8")
        component_source = Path(
            __import__("app.fiona_card_components", fromlist=[""]).__file__
        ).read_text(encoding="utf-8")
        token_source = Path(
            __import__("app.design_tokens", fromlist=[""]).__file__
        ).read_text(encoding="utf-8")
        source = renderer_source + component_source + token_source
        for label in (
            "TODAY'S JUDGEMENT",
            "FIONA INTELLIGENCE",
            "NOT A FORECAST",
            "AI MARKET INTELLIGENCE",
        ):
            self.assertIn(label, source)

    def test_wrapped_judgment_never_starts_with_orphan_punctuation(self) -> None:
        image = Image.new("RGB", (1080, 200), BACKGROUND)
        lines = wrap_text_pixels(
            ImageDraw.Draw(image),
            "变化来自美债收益率、美元流动性、美股科技权重、比特币ETF资金流。",
            font(TYPOGRAPHY["fiona_view"], bold=True),
            420,
            2,
        )
        self.assertTrue(all(not line.startswith(("，", "。", "、")) for line in lines))


if __name__ == "__main__":
    unittest.main()
