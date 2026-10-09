"""Operator-only state initialization. Does not run scheduler or contact Telegram."""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from app.fiona_state import initialize_state


def migrate_bundle(bundle_path: Path, root: Path, boundary: datetime) -> dict:
    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    files = bundle["files"]
    ledger = json.loads(files["fiona_scheduler_ledger.json"])
    memory = json.loads(files["fiona_memory.json"])
    standalone = json.loads(files["alerts/fiona_alert_memory.json"]) if "alerts/fiona_alert_memory.json" in files else None
    coverage = json.loads(files["fiona_coverage_shadow_history.json"]) if "fiona_coverage_shadow_history.json" in files else None
    uncertain_records = [json.loads(line) for line in files.get("fiona_scheduler_delivery_uncertain.log", "").splitlines() if line.strip()]
    if not root.is_absolute() or root == Path("/app") or root.is_relative_to(Path("/app")):
        raise ValueError("dedicated absolute state root required")
    return initialize_state(root, ledger_payload=ledger, memory_payload=memory, standalone_payload=standalone,
                            coverage_payload=coverage, uncertain_records=uncertain_records, boundary=boundary,
                            provenance="authoritative_legacy_bundle_with_safe_cutover_boundary")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--boundary", required=True, help="Aware timestamp; elapsed unknown occurrences are not replayed")
    args = parser.parse_args()
    result = migrate_bundle(args.bundle, args.root, datetime.fromisoformat(args.boundary))
    print(json.dumps({"ok": True, **result}, separators=(",", ":")))


if __name__ == "__main__":
    main()
