from __future__ import annotations

import os
import re
import tempfile
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Mapping

from app.fiona_market_news_image import (
    MarketNewsViewModel,
    compose_market_news_caption,
)
from app.telegram_service import (
    TelegramRequestError,
    TelegramUnknownDeliveryError,
    normalize_caption,
    send_document_with_caption,
    send_photo_with_caption,
)


MAX_IMAGE_BYTES = 1_500_000
EXPECTED_IMAGE_SIZE = (1080, 1350)
PHOTO_EXPECTED_IMAGE_SIZE = (1440, 1800)
DELIVERY_SUCCESS = "success"
DELIVERY_FAILED = "failed"
DELIVERY_PARTIAL = "partial_delivery"


class MarketNewsMode(str, Enum):
    TEXT = "text"
    SHADOW = "shadow"
    IMAGE = "image"


class TelegramMediaMode(str, Enum):
    DOCUMENT = "document"
    PHOTO = "photo"


class ImageValidationError(RuntimeError):
    pass


@dataclass(frozen=True)
class ImageValidationResult:
    width: int
    height: int
    mode: str
    size_bytes: int


@dataclass
class MarketNewsDeliveryResult:
    requested_mode: str
    effective_mode: str
    telegram_media_mode: str = TelegramMediaMode.DOCUMENT.value
    output_locale: str = "zh-CN"
    image_generated: bool = False
    image_validation: bool = False
    image_sent: bool = False
    text_sent: bool = False
    fallback_used: bool = False
    fallback_reason: str = ""
    render_duration_ms: int = 0
    send_duration_ms: int = 0
    image_size_bytes: int = 0
    image_width: int = 0
    image_height: int = 0
    caption_length: int = 0
    data_completeness: int | None = None
    market_regime: str = ""
    evidence_level: str = ""
    error_category: str = ""
    errors: list[str] = field(default_factory=list)
    message_ids: list[int] = field(default_factory=list)
    final_delivery_channel: str = ""
    cleanup_success: bool = True
    cleanup_attempted: bool = False
    unknown_delivery_state: bool = False
    photo_send_status: str = "not_sent"
    document_send_status: str = "not_sent"
    push_result: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload.pop("push_result", None)
        payload.update(self.observability_fields())
        return payload

    def observability_fields(self) -> dict[str, Any]:
        return {
            "delivery_mode": self.requested_mode,
            "telegram_media_mode": self.telegram_media_mode,
            "output_locale": self.output_locale,
            "render_success": self.image_generated and self.image_validation,
            "render_width": self.image_width,
            "render_height": self.image_height,
            "png_width": self.image_width,
            "png_height": self.image_height,
            "png_size_bytes": self.image_size_bytes,
            "caption_length": self.caption_length,
            "fallback_state": self.fallback_state(),
            "cleanup_state": self.cleanup_state(),
            "photo_send_status": self.photo_send_status,
            "document_send_status": self.document_send_status,
            "fallback_used": self.fallback_used,
            "fallback_reason": self.fallback_reason,
            "final_delivery_channel": self.final_delivery_channel,
            "delivery_state": delivery_state_for(self),
            "error_category": self.error_category,
        }

    def fallback_state(self) -> str:
        if self.fallback_used:
            return "used"
        if self.requested_mode != MarketNewsMode.IMAGE.value:
            return "not_applicable"
        if self.unknown_delivery_state:
            return "suppressed_unknown_delivery"
        return "not_used"

    def cleanup_state(self) -> str:
        if not self.cleanup_attempted:
            return "not_required"
        return "success" if self.cleanup_success else "failed"


def market_news_mode_from_env(
    environ: Mapping[str, str] | None = None,
    warning_logger: Callable[[dict[str, Any]], None] | None = None,
) -> MarketNewsMode:
    source = os.environ if environ is None else environ
    return parse_market_news_mode(source.get("FIONA_MARKET_NEWS_MODE"), warning_logger)


def parse_market_news_mode(
    raw_value: str | None,
    warning_logger: Callable[[dict[str, Any]], None] | None = None,
) -> MarketNewsMode:
    normalized = str(raw_value or "text").strip().lower()
    try:
        return MarketNewsMode(normalized)
    except ValueError:
        if warning_logger is not None:
            warning_logger(
                {
                    "event": "fionaMarketNewsModeWarning",
                    "brief_type": "market_news",
                    "invalid_mode": normalized,
                    "fallback_mode": MarketNewsMode.TEXT.value,
                }
            )
        return MarketNewsMode.TEXT


def telegram_media_mode_from_env(
    environ: Mapping[str, str] | None = None,
    warning_logger: Callable[[dict[str, Any]], None] | None = None,
) -> TelegramMediaMode:
    source = os.environ if environ is None else environ
    return parse_telegram_media_mode(source.get("FIONA_TELEGRAM_MEDIA_MODE"), warning_logger)


def parse_telegram_media_mode(
    raw_value: str | None,
    warning_logger: Callable[[dict[str, Any]], None] | None = None,
) -> TelegramMediaMode:
    normalized = str(raw_value or TelegramMediaMode.DOCUMENT.value).strip().lower()
    try:
        return TelegramMediaMode(normalized)
    except ValueError:
        if warning_logger is not None:
            warning_logger(
                {
                    "event": "fionaTelegramMediaModeWarning",
                    "invalid_mode": normalized,
                    "fallback_mode": TelegramMediaMode.DOCUMENT.value,
                }
            )
        return TelegramMediaMode.DOCUMENT


class MarketNewsDeliveryCoordinator:
    def __init__(
        self,
        *,
        text_sender: Callable[[str], dict[str, Any]],
        document_sender: Callable[[str | Path, str], dict[str, Any]] = send_document_with_caption,
        photo_sender: Callable[[str | Path, str], dict[str, Any]] = send_photo_with_caption,
        renderer: Callable[[MarketNewsViewModel, str | Path], Path] | None = None,
        caption_builder: Callable[[MarketNewsViewModel], str] = compose_market_news_caption,
        logger: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        self.text_sender = text_sender
        self.document_sender = document_sender
        self.photo_sender = photo_sender
        self.renderer = renderer
        self.caption_builder = caption_builder
        self.logger = logger or (lambda payload: None)

    def deliver(
        self,
        *,
        mode: MarketNewsMode,
        legacy_text: str,
        view_model_factory: Callable[[], MarketNewsViewModel],
        occurrence_id: str | None = None,
        media_mode: TelegramMediaMode = TelegramMediaMode.DOCUMENT,
        output_locale: str = "zh-CN",
    ) -> MarketNewsDeliveryResult:
        result = MarketNewsDeliveryResult(
            requested_mode=mode.value,
            effective_mode=mode.value,
            telegram_media_mode=media_mode.value,
            output_locale=output_locale,
        )
        if mode == MarketNewsMode.TEXT:
            result.push_result = self._send_text(legacy_text)
            self._apply_text_result(result)
            result.final_delivery_channel = "text"
            self._log_result(result, occurrence_id)
            return result

        if mode == MarketNewsMode.SHADOW:
            result.push_result = self._send_text(legacy_text)
            self._apply_text_result(result)
            result.final_delivery_channel = "text"

        temp_directory: tempfile.TemporaryDirectory[str] | None = None
        temp_root: Path | None = None
        stage = "view_model"
        try:
            view_model = view_model_factory()
            evidence, regime = assess_market_news(view_model)
            result.data_completeness = evidence.completeness
            result.evidence_level = evidence.level.value
            result.market_regime = regime.regime.value

            stage = "caption"
            caption = normalize_caption(self.caption_builder(view_model))
            result.caption_length = len(caption)

            stage = "temporary_file"
            temp_directory = tempfile.TemporaryDirectory(prefix="fiona-market-news-")
            temp_root = Path(temp_directory.name)
            image_path = temp_root / "fiona_market_news.png"

            stage = "renderer"
            render_started = time.monotonic()
            try:
                rendered_path = (
                    self.renderer(view_model, image_path)
                    if self.renderer is not None
                    else render_for_media(view_model, image_path, media_mode)
                )
            finally:
                result.render_duration_ms = elapsed_ms(render_started)
            result.image_generated = True

            stage = "image_validation"
            validation = validate_market_news_png(
                rendered_path,
                expected_size=expected_image_size(media_mode),
            )
            result.image_validation = True
            result.image_size_bytes = validation.size_bytes
            result.image_width = validation.width
            result.image_height = validation.height

            if mode == MarketNewsMode.SHADOW:
                return result

            stage = f"send_{media_mode.value}"
            send_started = time.monotonic()
            try:
                sender = self.photo_sender if media_mode == TelegramMediaMode.PHOTO else self.document_sender
                response = sender(rendered_path, caption)
            finally:
                result.send_duration_ms = elapsed_ms(send_started)
            message_id = telegram_message_id(response)
            if message_id is None:
                raise TelegramRequestError(
                    f"Telegram send{media_mode.value.title()} response did not include message_id",
                    category="telegram_missing_message_id",
                    delivery_state="failed",
                )
            result.image_sent = True
            if media_mode == TelegramMediaMode.PHOTO:
                result.photo_send_status = "success"
            else:
                result.document_send_status = "success"
            result.message_ids = [message_id]
            result.final_delivery_channel = media_mode.value
            result.push_result = media_push_result(message_id, media_mode)
        except TelegramUnknownDeliveryError as exc:
            result.error_category = exc.category
            result.errors.append(str(exc))
            result.unknown_delivery_state = True
            if media_mode == TelegramMediaMode.PHOTO:
                result.photo_send_status = "unknown"
            else:
                result.document_send_status = "unknown"
            result.final_delivery_channel = f"{media_mode.value}_unknown"
            result.push_result = unknown_media_push_result(str(exc), media_mode)
        except Exception as exc:  # noqa: BLE001 - every definite image failure falls back to legacy text.
            result.error_category = error_category_for(stage, exc)
            result.errors.append(safe_error(exc))
            if stage == "send_photo":
                result.photo_send_status = "failed"
            elif stage == "send_document":
                result.document_send_status = "failed"
            if mode == MarketNewsMode.IMAGE:
                result.fallback_used = True
                result.fallback_reason = result.error_category
                result.effective_mode = MarketNewsMode.TEXT.value
                result.push_result = self._send_text(legacy_text)
                self._apply_text_result(result)
                result.final_delivery_channel = "text"
            else:
                self.logger(
                    {
                        "event": "fionaMarketNewsShadowWarning",
                        "mode": mode.value,
                        "brief_type": "market_news",
                        "error_category": result.error_category,
                        "error": safe_error(exc),
                    }
                )
        finally:
            if temp_directory is not None:
                result.cleanup_attempted = True
                try:
                    temp_directory.cleanup()
                except Exception as exc:  # noqa: BLE001 - cleanup visibility must not alter delivery.
                    result.cleanup_success = False
                    result.errors.append(f"cleanup_failed: {safe_error(exc)}")
                else:
                    result.cleanup_success = temp_root is None or not temp_root.exists()
            self._log_result(result, occurrence_id)
        return result

    def _send_text(self, text: str) -> dict[str, Any]:
        try:
            return self.text_sender(text)
        except Exception as exc:  # noqa: BLE001 - preserve scheduler-visible failure without a second send.
            return {
                "scope": "Fiona Market News",
                "ok": False,
                "delivery_status": DELIVERY_FAILED,
                "message_ids": [],
                "successful_chunks": [],
                "failed_chunks": [1],
                "errors": [safe_error(exc)],
                "total_chunks": 1,
            }

    def _apply_text_result(self, result: MarketNewsDeliveryResult) -> None:
        message_ids = result.push_result.get("message_ids")
        result.message_ids = [int(item) for item in message_ids or [] if safe_int(item) is not None]
        result.text_sent = bool(result.push_result.get("ok") and result.message_ids)
        if result.push_result.get("errors"):
            result.errors.extend(str(item) for item in result.push_result["errors"])

    def _log_result(
        self,
        result: MarketNewsDeliveryResult,
        occurrence_id: str | None,
    ) -> None:
        observability = result.observability_fields()
        self.logger(
            {
                "event": "fionaMarketNewsDelivery",
                "mode": result.requested_mode,
                "delivery_mode": observability["delivery_mode"],
                "occurrence_id": occurrence_id,
                "brief_type": "market_news",
                "render_success": observability["render_success"],
                "image_generated": result.image_generated,
                "image_validation": result.image_validation,
                "telegram_media_mode": observability["telegram_media_mode"],
                "output_locale": observability["output_locale"],
                "photo_send_status": observability["photo_send_status"],
                "document_send_status": observability["document_send_status"],
                "render_duration_ms": result.render_duration_ms,
                "render_width": observability["render_width"],
                "render_height": observability["render_height"],
                "telegram_send_duration_ms": result.send_duration_ms,
                "image_width": result.image_width,
                "image_height": result.image_height,
                "image_size_bytes": result.image_size_bytes,
                "png_width": observability["png_width"],
                "png_height": observability["png_height"],
                "png_size_bytes": observability["png_size_bytes"],
                "caption_length": observability["caption_length"],
                "data_completeness": result.data_completeness,
                "market_regime": result.market_regime,
                "evidence_level": result.evidence_level,
                "fallback_used": result.fallback_used,
                "fallback_reason": result.fallback_reason,
                "fallback_state": observability["fallback_state"],
                "final_delivery_channel": result.final_delivery_channel,
                "delivery_state": observability["delivery_state"],
                "cleanup_success": result.cleanup_success,
                "cleanup_state": observability["cleanup_state"],
                "error_category": result.error_category,
            }
        )


def validate_market_news_png(
    path: str | Path,
    *,
    expected_size: tuple[int, int] = EXPECTED_IMAGE_SIZE,
    max_size_bytes: int = MAX_IMAGE_BYTES,
) -> ImageValidationResult:
    from PIL import Image

    target = Path(path)
    if not target.exists() or not target.is_file():
        raise ImageValidationError("Rendered PNG does not exist.")
    if target.suffix.lower() != ".png":
        raise ImageValidationError("Rendered file does not use the PNG extension.")
    size_bytes = target.stat().st_size
    if size_bytes <= 0:
        raise ImageValidationError("Rendered PNG is empty.")
    if size_bytes > max_size_bytes:
        raise ImageValidationError("Rendered PNG exceeds the 1.5 MB product limit.")
    try:
        with Image.open(target) as image:
            image.load()
            if image.format != "PNG":
                raise ImageValidationError("Rendered file MIME does not match PNG.")
            if image.size != expected_size:
                raise ImageValidationError(
                    f"Rendered PNG has invalid dimensions: {image.width}x{image.height}."
                )
            if image.mode not in {"RGB", "RGBA"}:
                raise ImageValidationError(f"Rendered PNG has unsupported mode: {image.mode}.")
            return ImageValidationResult(
                width=image.width,
                height=image.height,
                mode=image.mode,
                size_bytes=size_bytes,
            )
    except ImageValidationError:
        raise
    except Exception as exc:
        raise ImageValidationError("Rendered file could not be decoded as PNG.") from exc


def render_with_pillow(
    view_model: MarketNewsViewModel,
    output_path: str | Path,
) -> Path:
    from app.fiona_card_renderer import render_market_news_card

    return render_market_news_card(view_model, output_path)


def render_with_pillow_ios(
    view_model: MarketNewsViewModel,
    output_path: str | Path,
) -> Path:
    from app.fiona_card_renderer import render_market_news_card_ios

    return render_market_news_card_ios(view_model, output_path)


def render_for_media(
    view_model: MarketNewsViewModel,
    output_path: str | Path,
    media_mode: TelegramMediaMode,
) -> Path:
    if media_mode == TelegramMediaMode.PHOTO:
        return render_with_pillow_ios(view_model, output_path)
    return render_with_pillow(view_model, output_path)


def expected_image_size(media_mode: TelegramMediaMode) -> tuple[int, int]:
    return PHOTO_EXPECTED_IMAGE_SIZE if media_mode == TelegramMediaMode.PHOTO else EXPECTED_IMAGE_SIZE


def assess_market_news(view_model: MarketNewsViewModel) -> tuple[Any, Any]:
    from app.fiona_card_renderer import derive_evidence_level, derive_market_regime

    return derive_evidence_level(view_model), derive_market_regime(view_model)


def media_push_result(message_id: int, media_mode: TelegramMediaMode) -> dict[str, Any]:
    return {
        "scope": "Fiona Market News",
        "ok": True,
        "delivery_status": DELIVERY_SUCCESS,
        "message_ids": [message_id],
        "successful_chunks": [1],
        "failed_chunks": [],
        "errors": [],
        "total_chunks": 1,
        "channel": media_mode.value,
    }


def unknown_media_push_result(error: str, media_mode: TelegramMediaMode) -> dict[str, Any]:
    return {
        "scope": "Fiona Market News",
        "ok": False,
        "delivery_status": DELIVERY_PARTIAL,
        "message_ids": [],
        "successful_chunks": [],
        "failed_chunks": [1],
        "errors": [error],
        "total_chunks": 1,
        "channel": media_mode.value,
        "unknown_delivery_state": True,
    }


def document_push_result(message_id: int) -> dict[str, Any]:
    return media_push_result(message_id, TelegramMediaMode.DOCUMENT)


def unknown_document_push_result(error: str) -> dict[str, Any]:
    return unknown_media_push_result(error, TelegramMediaMode.DOCUMENT)


def telegram_message_id(response: dict[str, Any]) -> int | None:
    result = response.get("result") if isinstance(response, dict) else None
    value = result.get("message_id") if isinstance(result, dict) else None
    return safe_int(value)


def error_category_for(stage: str, exc: Exception) -> str:
    if isinstance(exc, TelegramRequestError):
        return exc.category
    categories = {
        "view_model": "view_model_failed",
        "caption": "caption_failed",
        "temporary_file": "temporary_file_failed",
        "renderer": "renderer_failed",
        "image_validation": "image_validation_failed",
        "send_document": "document_send_failed",
        "send_photo": "photo_send_failed",
    }
    return categories.get(stage, "market_news_image_failed")


def safe_error(exc: Exception) -> str:
    value = str(exc)
    value = re.sub(
        r"https://api\.telegram\.org/bot[^/\s]+",
        "[telegram-api]",
        value,
        flags=re.IGNORECASE,
    )
    value = re.sub(r"\bbot\d+:[A-Za-z0-9_-]+\b", "bot[redacted]", value)
    return value


def safe_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def elapsed_ms(started_at: float) -> int:
    return max(0, round((time.monotonic() - started_at) * 1000))


def delivery_state_for(result: MarketNewsDeliveryResult) -> str:
    if result.unknown_delivery_state:
        return DELIVERY_PARTIAL
    status = str(result.push_result.get("delivery_status") or "")
    if status:
        return status
    if result.image_sent or result.text_sent:
        return DELIVERY_SUCCESS
    return DELIVERY_FAILED
