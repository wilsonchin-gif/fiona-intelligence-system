from __future__ import annotations

import json
import shutil
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.fiona_market_news_delivery import (
    MarketNewsDeliveryCoordinator,
    MarketNewsMode,
)
from app.fiona_market_news_image import build_market_news_view_model
from app.fiona_narrative import NarrativeEngine
from scripts.generate_fiona_market_news_prototypes import (
    NOW,
    full_snapshot,
    long_text_snapshot,
    missing_snapshot,
    prototype_events,
)


OUTPUT_DIR = ROOT / "reports" / "dry_runs" / "fiona_market_news_phase_2c"


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    events = prototype_events()
    narratives = NarrativeEngine().build(events, now=NOW)
    scenarios = {
        "full": full_snapshot(),
        "missing": missing_snapshot(),
        "long": long_text_snapshot(),
    }
    report: dict[str, object] = {
        "network_requests": 0,
        "telegram_transport": "fake",
        "scenarios": [],
    }

    for index, (name, snapshot) in enumerate(scenarios.items(), 1):
        destination = OUTPUT_DIR / f"market_news_phase2c_{name}.png"
        logs: list[dict[str, object]] = []

        def fake_document_sender(path: str | Path, caption: str) -> dict[str, object]:
            shutil.copy2(path, destination)
            return {"ok": True, "result": {"message_id": 9000 + index}}

        coordinator = MarketNewsDeliveryCoordinator(
            text_sender=lambda text: (_ for _ in ()).throw(
                AssertionError("Dry-run image success must not use text fallback.")
            ),
            document_sender=fake_document_sender,
            logger=logs.append,
        )
        result = coordinator.deliver(
            mode=MarketNewsMode.IMAGE,
            legacy_text="Dry-run legacy fallback",
            view_model_factory=lambda snapshot=snapshot: build_market_news_view_model(
                snapshot,
                events,
                narratives,
                generated_at=NOW,
            ),
            occurrence_id=f"dry-run:{name}",
        )
        report["scenarios"].append(
            {
                "scenario": name,
                "mode": result.requested_mode,
                "render_result": result.image_generated and result.image_validation,
                "image_dimensions": [result.image_width, result.image_height],
                "image_size_bytes": result.image_size_bytes,
                "caption_length": result.caption_length,
                "fallback_used": result.fallback_used,
                "cleanup_success": result.cleanup_success,
                "output_path": str(destination),
                "delivery_channel": result.final_delivery_channel,
                "logged_metrics": logs[-1] if logs else {},
            }
        )

    report_path = OUTPUT_DIR / "dry_run_report.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
