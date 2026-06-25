from __future__ import annotations

import json
import os
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT / ".env"
TIMEOUT = 90
USER_AGENT = "WilsonMarketNews/0.1"


def send_message(text: str) -> dict[str, Any]:
    """Send a plain Telegram text message."""
    config = telegram_config()
    payload = urllib.parse.urlencode(
        {
            "chat_id": config["chat_id"],
            "text": text,
        }
    ).encode("utf-8")
    return telegram_request(config["bot_token"], "sendMessage", payload, "application/x-www-form-urlencoded")


def send_photo(image_path: str | Path) -> dict[str, Any]:
    """Send a PNG/JPEG image to Telegram as a compressed photo."""
    path = Path(image_path).expanduser()
    if not path.exists():
        raise FileNotFoundError(f"Image not found: {path}")

    config = telegram_config()
    data, content_type = multipart_form_data({"chat_id": config["chat_id"]}, {"photo": path})
    return telegram_request(config["bot_token"], "sendPhoto", data, content_type)


def send_document(document_path: str | Path) -> dict[str, Any]:
    """Send a file to Telegram without image recompression."""
    path = Path(document_path).expanduser()
    if not path.exists():
        raise FileNotFoundError(f"Document not found: {path}")

    config = telegram_config()
    data, content_type = multipart_form_data({"chat_id": config["chat_id"]}, {"document": path})
    return telegram_request(config["bot_token"], "sendDocument", data, content_type)


def telegram_config() -> dict[str, str]:
    load_env_file()
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = first_env_value("TELEGRAM_GROUP_ID", "TELEGRAM_CHAT_ID", "TELEGRAM_CHANNEL_ID")
    missing = []
    if not bot_token:
        missing.append("TELEGRAM_BOT_TOKEN")
    if not chat_id:
        missing.append("TELEGRAM_GROUP_ID or TELEGRAM_CHAT_ID")
    if missing:
        raise RuntimeError(f"Missing Telegram env: {', '.join(missing)}")
    return {"bot_token": bot_token, "chat_id": chat_id}


def first_env_value(*names: str) -> str:
    for name in names:
        value = os.getenv(name, "").strip()
        if value:
            return value
    return ""


def load_env_file(path: Path = ENV_PATH) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def telegram_request(bot_token: str, method: str, data: bytes, content_type: str) -> dict[str, Any]:
    url = f"https://api.telegram.org/bot{bot_token}/{method}"
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": content_type, "User-Agent": USER_AGENT},
    )
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        body = json.loads(response.read().decode("utf-8", "ignore"))
    if not body.get("ok"):
        raise RuntimeError(body)
    return body


def multipart_form_data(fields: dict[str, str], files: dict[str, Path]) -> tuple[bytes, str]:
    boundary = f"----WilsonTelegramBoundary{int(time.time() * 1000)}"
    chunks: list[bytes] = []
    for name, value in fields.items():
        chunks.extend(
            [
                f"--{boundary}\r\n".encode(),
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode(),
                str(value).encode("utf-8"),
                b"\r\n",
            ]
        )
    for name, path in files.items():
        chunks.extend(
            [
                f"--{boundary}\r\n".encode(),
                f'Content-Disposition: form-data; name="{name}"; filename="{path.name}"\r\n'.encode(),
                f"Content-Type: {content_type_for(path)}\r\n\r\n".encode(),
                path.read_bytes(),
                b"\r\n",
            ]
        )
    chunks.append(f"--{boundary}--\r\n".encode())
    return b"".join(chunks), f"multipart/form-data; boundary={boundary}"


def content_type_for(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".png":
        return "image/png"
    if suffix in {".jpg", ".jpeg"}:
        return "image/jpeg"
    return "application/octet-stream"
