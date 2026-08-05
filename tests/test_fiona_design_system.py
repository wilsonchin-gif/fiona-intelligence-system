from __future__ import annotations

import hashlib
import json
import re
import tempfile
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path

from PIL import Image, ImageDraw

from app.design_tokens import FIONA_TOKENS, token_manifest
from app.fiona_card_components import RenderContext
from app.fiona_card_renderer import (
    build_market_news_components,
    render_components,
    render_market_news_card,
)
from tests.test_fiona_card_renderer import view_model


EXPECTED_COMPONENTS = (
    "Header",
    "Market Regime",
    "Evidence",
    "Hero Judgment",
    "Heat Map",
    "What Changed",
    "Key Markets",
    "Narrative",
    "Watch Next",
    "Historical Context",
    "Brand Signature",
    "Footer",
)


class FionaDesignSystemTest(unittest.TestCase):
    def test_token_manifest_has_complete_design_foundations(self) -> None:
        manifest = token_manifest()
        self.assertEqual(
            set(manifest),
            {
                "version",
                "canvas",
                "colors",
                "typography",
                "spacing",
                "radius",
                "border",
                "shadow",
                "icon_size",
                "section_gap",
                "grid",
                "surfaces",
                "footer",
                "regions",
            },
        )
        self.assertEqual(manifest["canvas"]["width"], 1080)
        self.assertEqual(manifest["canvas"]["height"], 1350)
        self.assertEqual(manifest["footer"]["signature"], "FIONA INTELLIGENCE")

    def test_tokens_are_immutable_and_regions_are_read_only(self) -> None:
        with self.assertRaises(FrozenInstanceError):
            FIONA_TOKENS.canvas.width = 1  # type: ignore[misc]
        with self.assertRaises(TypeError):
            FIONA_TOKENS.regions["header"] = FIONA_TOKENS.regions["footer"]  # type: ignore[index]

    def test_renderer_and_components_have_no_raw_hex_color_literals(self) -> None:
        for module_name in ("app.fiona_card_renderer", "app.fiona_card_components"):
            source = Path(__import__(module_name, fromlist=[""]).__file__).read_text(encoding="utf-8")
            self.assertIsNone(re.search(r"#[0-9A-Fa-f]{6}", source), module_name)

    def test_renderer_and_components_have_no_hardcoded_font_sizes(self) -> None:
        for module_name in ("app.fiona_card_renderer", "app.fiona_card_components"):
            source = Path(__import__(module_name, fromlist=[""]).__file__).read_text(encoding="utf-8")
            self.assertIsNone(re.search(r"font\(\s*\d+", source), module_name)

    def test_component_contract_and_order_are_stable(self) -> None:
        components = build_market_news_components(view_model())
        self.assertEqual(tuple(component.name for component in components), EXPECTED_COMPONENTS)
        self.assertTrue(all(component.region_name in FIONA_TOKENS.regions for component in components))

    def test_every_component_renders_independently(self) -> None:
        for component in build_market_news_components(view_model()):
            image = Image.new(
                FIONA_TOKENS.canvas.color_mode,
                (FIONA_TOKENS.canvas.width, FIONA_TOKENS.canvas.height),
                FIONA_TOKENS.colors.background,
            )
            result = component.render(RenderContext(ImageDraw.Draw(image), FIONA_TOKENS))
            self.assertEqual(result.name, component.name)
            self.assertEqual(result.region, FIONA_TOKENS.regions[component.region_name].as_tuple())
            self.assertGreaterEqual(result.rendered_items, 0)

    def test_visual_structure_snapshot_is_deterministic(self) -> None:
        image = Image.new(
            FIONA_TOKENS.canvas.color_mode,
            (FIONA_TOKENS.canvas.width, FIONA_TOKENS.canvas.height),
            FIONA_TOKENS.colors.background,
        )
        results = render_components(
            build_market_news_components(view_model()),
            RenderContext(ImageDraw.Draw(image), FIONA_TOKENS),
        )
        payload = json.dumps(
            [(result.name, result.region, result.rendered_items) for result in results],
            separators=(",", ":"),
        )
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        self.assertEqual(digest, "cdb56ce892b4ba55363a962a77110e233d41db548f116c53bfaeeefab60ea728")

    def test_production_renderer_uses_token_canvas_and_size_limit(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = render_market_news_card(view_model(), Path(tmpdir) / "design-system.png")
            with Image.open(output) as image:
                self.assertEqual(image.size, (FIONA_TOKENS.canvas.width, FIONA_TOKENS.canvas.height))
                self.assertEqual(image.mode, FIONA_TOKENS.canvas.color_mode)
            self.assertLess(output.stat().st_size, FIONA_TOKENS.canvas.max_file_size_bytes)


if __name__ == "__main__":
    unittest.main()
