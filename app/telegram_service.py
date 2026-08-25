from __future__ import annotations

import json
import os
import re
import socket
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT / ".env"
TIMEOUT = 90
USER_AGENT = "WilsonMarketNews/0.1"
TELEGRAM_CAPTION_MAX_LENGTH = 1024


class TelegramRequestError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        category: str,
        delivery_state: str,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.category = category
        self.delivery_state = delivery_state
        self.status_code = status_code


class TelegramUnknownDeliveryError(TelegramRequestError):
    def __init__(self, message: str, *, category: str) -> None:
        super().__init__(message, category=category, delivery_state="unknown")


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
    return send_photo_with_caption(image_path)


def send_photo_with_caption(
    image_path: str | Path,
    caption: str = "",
    parse_mode: str | None = None,
) -> dict[str, Any]:
    """Send a native Telegram photo with classified delivery semantics."""
    path = Path(image_path).expanduser()
    if not path.exists():
        raise FileNotFoundError(f"Image not found: {path}")

    config = telegram_config()
    fields = {"chat_id": config["chat_id"]}
    safe_caption = normalize_caption(caption)
    if safe_caption:
        fields["caption"] = safe_caption
    safe_parse_mode = str(parse_mode or "").strip()
    if safe_parse_mode:
        fields["parse_mode"] = safe_parse_mode
    data, content_type = multipart_form_data(fields, {"photo": path})
    return telegram_photo_request(config["bot_token"], "sendPhoto", data, content_type)


def send_document(document_path: str | Path) -> dict[str, Any]:
    """Send a file to Telegram without image recompression."""
    path = Path(document_path).expanduser()
    if not path.exists():
        raise FileNotFoundError(f"Document not found: {path}")

    config = telegram_config()
    data, content_type = multipart_form_data({"chat_id": config["chat_id"]}, {"document": path})
    return telegram_request(config["bot_token"], "sendDocument", data, content_type)


def send_document_with_caption(
    document_path: str | Path,
    caption: str = "",
) -> dict[str, Any]:
    """Send a document with a plain-text Caption and classified delivery errors."""
    path = Path(document_path).expanduser()
    if not path.exists():
        raise FileNotFoundError(f"Document not found: {path}")

    config = telegram_config()
    fields = {"chat_id": config["chat_id"]}
    safe_caption = normalize_caption(caption)
    if safe_caption:
        fields["caption"] = safe_caption
    data, content_type = multipart_form_data(fields, {"document": path})
    return telegram_document_request(
        config["bot_token"],
        "sendDocument",
        data,
        content_type,
    )


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


def telegram_document_request(
    bot_token: str,
    method: str,
    data: bytes,
    content_type: str,
) -> dict[str, Any]:
    return telegram_classified_request(
        bot_token,
        method,
        data,
        content_type,
        server_error_is_unknown=False,
    )


def telegram_photo_request(
    bot_token: str,
    method: str,
    data: bytes,
    content_type: str,
) -> dict[str, Any]:
    return telegram_classified_request(
        bot_token,
        method,
        data,
        content_type,
        server_error_is_unknown=True,
    )


def telegram_classified_request(
    bot_token: str,
    method: str,
    data: bytes,
    content_type: str,
    *,
    server_error_is_unknown: bool,
) -> dict[str, Any]:
    url = f"https://api.telegram.org/bot{bot_token}/{method}"
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": content_type, "User-Agent": USER_AGENT},
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            raw_body = response.read().decode("utf-8", "ignore")
    except urllib.error.HTTPError as exc:
        if server_error_is_unknown and exc.code >= 500:
            raise TelegramUnknownDeliveryError(
                "Telegram server returned an ambiguous error; delivery state is unknown",
                category="telegram_server_error",
            ) from exc
        raise TelegramRequestError(
            f"Telegram API HTTP error {exc.code}",
            category="telegram_http_error",
            delivery_state="failed",
            status_code=exc.code,
        ) from exc
    except (TimeoutError, socket.timeout) as exc:
        raise TelegramUnknownDeliveryError(
            "Telegram request timed out; delivery state is unknown",
            category="telegram_timeout",
        ) from exc
    except urllib.error.URLError as exc:
        raise TelegramUnknownDeliveryError(
            "Telegram network request failed; delivery state is unknown",
            category="telegram_network_error",
        ) from exc
    except OSError as exc:
        raise TelegramUnknownDeliveryError(
            "Telegram connection failed; delivery state is unknown",
            category="telegram_connection_error",
        ) from exc
    try:
        body = json.loads(raw_body)
    except (TypeError, ValueError) as exc:
        raise TelegramUnknownDeliveryError(
            "Telegram response could not be parsed; delivery state is unknown",
            category="telegram_response_parse_error",
        ) from exc
    if not isinstance(body, dict):
        raise TelegramUnknownDeliveryError(
            "Telegram response shape is invalid; delivery state is unknown",
            category="telegram_response_parse_error",
        )
    if not body.get("ok"):
        description = sanitize_telegram_description(
            str(body.get("description") or "Telegram API rejected the request")
        )
        raise TelegramRequestError(
            description,
            category="telegram_api_rejected",
            delivery_state="failed",
            status_code=safe_int(body.get("error_code")),
        )
    return body


def multipart_form_data(fields: dict[str, str], files: dict[str, Path]) -> tuple[bytes, str]:
    boundary = f"----WilsonTelegramBoundary{uuid.uuid4().hex}"
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
        with path.open("rb") as file_handle:
            file_content = file_handle.read()
        chunks.extend(
            [
                f"--{boundary}\r\n".encode(),
                f'Content-Disposition: form-data; name="{name}"; filename="{path.name}"\r\n'.encode(),
                f"Content-Type: {content_type_for(path)}\r\n\r\n".encode(),
                file_content,
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


def normalize_caption(caption: str, max_length: int = TELEGRAM_CAPTION_MAX_LENGTH) -> str:
    clean = str(caption or "").strip()
    if len(clean) <= max_length:
        return clean
    prefix = clean[: max(1, max_length - 1)]
    boundary = max(prefix.rfind(mark) for mark in ("\n\n", "\n", "。", "！", "？", ".", "!", "?"))
    if boundary >= max_length // 2:
        return prefix[: boundary + 1].rstrip()
    return prefix.rstrip() + "…"


def safe_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def sanitize_telegram_description(value: str) -> str:
    clean = str(value or "")
    clean = re.sub(
        r"https://api\.telegram\.org/bot[^/\s]+",
        "[telegram-api]",
        clean,
        flags=re.IGNORECASE,
    )
    return re.sub(r"\bbot\d+:[A-Za-z0-9_-]+\b", "bot[redacted]", clean)
