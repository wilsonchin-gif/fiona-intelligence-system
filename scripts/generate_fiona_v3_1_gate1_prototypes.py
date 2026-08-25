from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import sys

from PIL import Image


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.fiona_card_renderer import render_market_news_card, render_market_news_card_ios
from app.fiona_market_news_image import ChangedEventView, build_market_news_view_model, compose_market_news_caption
from app.fiona_narrative import NarrativeEngine
from scripts.generate_fiona_market_news_prototypes import (
    NOW,
    full_snapshot,
    missing_snapshot,
    prototype_events,
)


OUTPUT_DIR = ROOT / "reports" / "prototypes" / "fiona_v3_1_gate1"


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    events = prototype_events()
    narratives = NarrativeEngine().build(events, now=NOW)
    scenarios = {
        "full": full_snapshot(),
        "missing": missing_snapshot(),
        "stress": stress_snapshot(),
    }
    metrics: dict[str, object] = {
        "production_renderer": "native Pillow",
        "target": [1440, 1800],
        "comparison": [1080, 1350],
        "ios_preview": [390, 488],
        "telegram_calls": 0,
        "scenarios": {},
    }
    for name, snapshot in scenarios.items():
        v3_model = build_market_news_view_model(
            snapshot,
            events,
            narratives,
            generated_at=NOW,
            output_locale="zh-CN",
        )
        gate1_model = build_market_news_view_model(
            snapshot,
            events,
            narratives,
            generated_at=NOW,
            output_locale="en-US",
        )
        if name == "stress":
            gate1_model = replace(
                gate1_model,
                fiona_view=(
                    "Cross-market evidence remains deliberately verbose in this stress fixture while liquidity, "
                    "rates, ETF flows, stablecoin supply, policy signals, and risk assets still require independent "
                    "confirmation before Fiona raises the strength of the current judgment. " * 5
                ),
                what_changed=(
                    ChangedEventView(
                        "A deliberately long market development tests semantic clipping without reducing type size. " * 4,
                        "The evidence chain remains incomplete across several independent market variables. " * 5,
                        "Whether flows, rates, and risk assets confirm the same direction. " * 4,
                    ),
                ),
            )
        old_path = render_market_news_card(v3_model, OUTPUT_DIR / f"v3_0_{name}_1080x1350.png")
        new_path = render_market_news_card_ios(gate1_model, OUTPUT_DIR / f"market_news_gate1_{name}_1440x1800.png")
        preview_path = OUTPUT_DIR / f"ios_preview_{name}_390x488.png"
        with Image.open(new_path) as image:
            preview = image.resize((390, 488), Image.Resampling.LANCZOS)
            preview.save(preview_path, format="PNG", optimize=True)
        metrics["scenarios"][name] = {
            "v3_0_path": str(old_path),
            "v3_0_size_bytes": old_path.stat().st_size,
            "v3_1_path": str(new_path),
            "v3_1_size_bytes": new_path.stat().st_size,
            "caption_length": len(compose_market_news_caption(gate1_model)),
            "ios_preview_path": str(preview_path),
        }
    (OUTPUT_DIR / "qa_metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def stress_snapshot() -> dict[str, object]:
    snapshot = deepcopy(full_snapshot())
    snapshot["wilson_view"] = (
        "A deliberately long stress fixture validates that the card preserves its type scale and clips semantic "
        "content instead of shrinking the typography. Liquidity, rates, ETF flows, stablecoin supply, China "
        "policy signals, RWA adoption, and cross-market risk appetite all remain under independent review. " * 5
    )
    snapshot["errors"] = ["One delayed market source"]
    return snapshot


if __name__ == "__main__":
    main()
