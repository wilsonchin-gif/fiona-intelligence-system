from __future__ import annotations

import argparse
from pathlib import Path

from app.telegram_service import send_document, send_message, send_photo


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Test Wilson Telegram push.")
    parser.add_argument("--message", default="Wilson's Market News Telegram test.")
    parser.add_argument("--photo", type=Path, help="Optional image path to send after the test message.")
    parser.add_argument("--document", type=Path, help="Optional file path to send as a Telegram document before the test message.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.document:
        document_result = send_document(args.document)
        document_message = document_result.get("result", {}) if isinstance(document_result, dict) else {}
        print(f"Document sent: {document_result.get('ok')} message_id={document_message.get('message_id')}")

    if args.photo:
        photo_result = send_photo(args.photo)
        photo_message = photo_result.get("result", {}) if isinstance(photo_result, dict) else {}
        print(f"Photo sent: {photo_result.get('ok')} message_id={photo_message.get('message_id')}")

    message_result = send_message(args.message)
    message = message_result.get("result", {}) if isinstance(message_result, dict) else {}
    print(f"Message sent: {message_result.get('ok')} message_id={message.get('message_id')}")


if __name__ == "__main__":
    main()
