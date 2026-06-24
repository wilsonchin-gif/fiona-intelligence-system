from __future__ import annotations

import argparse
import http.server
import json
import socketserver
import time
from datetime import datetime, timezone
from pathlib import Path

from app.analysis import build_report
from app.config import MARKET_TITLES, load_sources
from app.fetchers import fetch_all
from app.render import write_reports
from app.scoring import rank_items

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = ROOT / "config" / "sources.json"
DEFAULT_OUTPUT = ROOT / "reports"


def run_once(config_path: Path, output_dir: Path, limit: int) -> dict[str, object]:
    sources = load_sources(config_path)
    raw_items, errors = fetch_all(sources)
    ranked = rank_items(raw_items, sources, now=datetime.now(timezone.utc))
    reports = [build_report(market, ranked, limit=limit) for market in MARKET_TITLES]
    write_reports(reports, output_dir)
    status = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "raw_items": len(raw_items),
        "ranked_items": len(ranked),
        "reports": [report.market for report in reports],
        "errors": errors,
    }
    (output_dir / "latest" / "status.json").write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
    return status


def watch(config_path: Path, output_dir: Path, limit: int, interval_minutes: int) -> None:
    while True:
        status = run_once(config_path, output_dir, limit)
        print(json.dumps(status, ensure_ascii=False), flush=True)
        time.sleep(max(1, interval_minutes) * 60)


def serve(output_dir: Path, port: int) -> None:
    directory = output_dir / "latest"
    handler = lambda *args, **kwargs: http.server.SimpleHTTPRequestHandler(*args, directory=str(directory), **kwargs)
    with socketserver.TCPServer(("", port), handler) as httpd:
        print(f"Serving {directory} at http://127.0.0.1:{port}/")
        httpd.serve_forever()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Hourly US/China/Crypto market intelligence reporter")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--limit", type=int, default=18)
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("run-once", help="Fetch sources and generate three latest reports once")
    watch_parser = subparsers.add_parser("watch", help="Run forever and refresh reports on an interval")
    watch_parser.add_argument("--interval-minutes", type=int, default=60)
    serve_parser = subparsers.add_parser("serve", help="Serve reports/latest over a local web server")
    serve_parser.add_argument("--port", type=int, default=8765)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.command == "run-once":
        status = run_once(args.config, args.output, args.limit)
        print(json.dumps(status, ensure_ascii=False, indent=2))
    elif args.command == "watch":
        watch(args.config, args.output, args.limit, args.interval_minutes)
    elif args.command == "serve":
        serve(args.output, args.port)


if __name__ == "__main__":
    main()

