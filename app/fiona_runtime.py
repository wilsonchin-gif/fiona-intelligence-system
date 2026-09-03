from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
import time as time_module
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any, Union

from app.fiona_briefing import (
    BRIEF_SCHEDULES,
    FionaBrief,
    FionaBriefKind,
    build_daily_brief,
    build_evening_brief,
    build_market_news_brief,
    build_morning_brief,
    build_weekly_brief,
)
from app.fiona_classifier import render_alert
from app.fiona_coverage_runtime import (
    run_global_coverage_shadow_safe,
    validate_global_coverage_runtime,
)
from app.fiona_engine import FionaAlertEngine
from app.fiona_lifecycle import LifecycleManager
from app.fiona_market_news_delivery import (
    MAX_IMAGE_BYTES,
    MarketNewsDeliveryCoordinator,
    MarketNewsMode,
    TelegramMediaMode,
    expected_image_size,
    market_news_mode_from_env,
    render_for_media,
    safe_error,
    telegram_media_mode_from_env,
    validate_market_news_png,
)
from app.fiona_market_news_image import (
    CAPTION_MAX_CHARS,
    MAX_TAGS,
    build_market_news_view_model,
    caption_intelligence,
    compose_market_news_caption,
    compose_market_news_fallback_text,
)
from app.fiona_locale import (
    OutputLocale,
    compose_safe_en_us_brief_fallback,
    contains_cjk,
    finalize_user_visible_text,
    output_locale_from_env,
    parse_output_locale,
)
from app.fiona_memory import DecisionMemoryRecord, FionaMemory
from app.fiona_narrative import NarrativeEngine
from app.fiona_scheduler import (
    ACTION_DEFER,
    ACTION_SEND,
    ACTION_SUPPRESS,
    STATUS_DEFERRED_COLLISION,
    STATUS_PARTIAL_DELIVERY,
    STATUS_SKIPPED_EXPIRED,
    STATUS_SUPPRESSED_COLLISION,
    STATUS_UNKNOWN_DELIVERY_STATE,
    UNCERTAIN_DELIVERY_LOG_NAME,
    SchedulerLedger,
    ScheduledOccurrence,
    arbitrate_occurrences,
    can_execute_occurrence,
    delivery_error_summary,
    delivery_status,
    due_occurrences,
    occurrence_expired,
    remember_uncertain_occurrence,
    scheduler_interval_minutes as scheduler_interval_minutes_v2,
    write_uncertain_delivery_journal,
)
from app.fiona_source_registry import coverage_profile_from_env, load_source_registry, validate_registry
from app.fiona_types import EventCategory, FionaEvent, MarketDirection, PushDecision
from app.telegram_service import (
    send_document_with_caption as telegram_send_document,
    send_message as telegram_send_message,
    send_photo_with_caption as telegram_send_photo,
)
from app.wilson import (
    DEFAULT_TIMEZONE,
    append_telegram_log,
    build_snapshot,
    latest_news_candidates,
    latest_news_source_failures,
    prepare_output_dirs,
    render_markdown as render_wilson_markdown,
    split_message,
    telegram_message_id,
)

ROOT = Path(__file__).resolve().parent.parent


def load_env_file(path: Path = ROOT / ".env") -> None:
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


load_env_file()
DEFAULT_OUTPUT = Path(os.getenv("FIONA_OUTPUT_DIR", str(ROOT / "reports" / "fiona"))).expanduser()
TELEGRAM_LOG_NAME = "fiona_telegram_push.log"
MEMORY_NAME = "fiona_memory.json"
SCHEDULER_LEDGER_NAME = "fiona_scheduler_ledger.json"

BriefSelector = Union[FionaBriefKind, str]


@dataclass
class FionaPayload:
    snapshot: dict[str, Any]
    events: list[FionaEvent]
    narratives: list[Any]
    brief: FionaBrief | None
    alert_messages: list[str]


def run_once(
    output_dir: Path = DEFAULT_OUTPUT,
    brief: BriefSelector = "auto",
    send: bool = False,
    timezone_name: str = DEFAULT_TIMEZONE,
    snapshot_builder: Callable[[datetime], dict[str, Any]] = build_snapshot,
    fallback_to_wilson: bool = True,
) -> dict[str, Any]:
    generated_at = now_in_timezone(timezone_name)
    latest_dir, archive_dir = prepare_output_dirs(output_dir, generated_at)
    memory_path = output_dir / MEMORY_NAME
    log_path = output_dir / TELEGRAM_LOG_NAME
    status: dict[str, Any] = {
        "ok": True,
        "generated_at": generated_at.isoformat(),
        "brief": str(brief),
        "output_dir": str(latest_dir),
        "archive_dir": str(archive_dir),
        "memory_path": str(memory_path),
        "telegram_log_path": str(log_path),
        "send": send,
        "database_url_configured": bool(os.getenv("DATABASE_URL", "").strip()),
        "alerts": {"enabled": alert_enabled(), "dry_run": alert_dry_run(), "count": 0, "pushed": []},
        "scheduled_briefs": [],
        "errors": [],
        "fallback": None,
    }

    snapshot: dict[str, Any] | None = None
    market_news_mode: MarketNewsMode | None = None
    telegram_media_mode = TelegramMediaMode.DOCUMENT
    warning_logger = lambda item: append_runtime_log(log_path, item)
    output_locale = output_locale_from_env(warning_logger=warning_logger)
    status["output_locale"] = output_locale.value
    coverage_profile = coverage_profile_from_env(warning_logger=warning_logger)
    status["coverage_profile"] = coverage_profile.value
    status["coverage_selection_authority"] = "legacy"
    localized_market_news_view_model: Any | None = None
    telegram_text_override: str | None = None
    try:
        snapshot = snapshot_builder(generated_at)
        payload = build_payload(snapshot, generated_at, memory_path, brief, output_locale=output_locale)
        if payload.brief is not None and payload.brief.kind == FionaBriefKind.MARKET_NEWS:
            market_news_mode = market_news_mode_from_env(
                warning_logger=warning_logger
            )
            telegram_media_mode = telegram_media_mode_from_env(warning_logger=warning_logger)
            status["market_news_mode"] = market_news_mode.value
            status["telegram_media_mode"] = telegram_media_mode.value
            if output_locale == OutputLocale.EN_US:
                localized_market_news_view_model = build_market_news_view_model(
                    payload.snapshot,
                    payload.events,
                    payload.narratives,
                    generated_at=generated_at,
                    output_locale=output_locale,
                )
                telegram_text_override = compose_market_news_fallback_text(localized_market_news_view_model)
            status["coverage_shadow"] = run_global_coverage_shadow_safe(
                latest_news_candidates() if snapshot_builder is build_snapshot else [],
                output_dir=output_dir,
                evaluated_at=generated_at,
                logger=warning_logger,
                collect_expanded=snapshot_builder is build_snapshot,
                legacy_failures=latest_news_source_failures() if snapshot_builder is build_snapshot else {},
            )
        write_payload(
            latest_dir,
            archive_dir,
            payload,
            status,
            telegram_text_override=telegram_text_override,
        )
        if send and should_push_alerts(brief):
            status["alerts"]["pushed"] = push_alerts(payload.alert_messages, log_path, output_locale=output_locale)
        if send and payload.brief is not None:
            if payload.brief.kind == FionaBriefKind.MARKET_NEWS:
                status["brief_push"] = push_market_news(
                    payload,
                    log_path,
                    mode=market_news_mode or MarketNewsMode.TEXT,
                    generated_at=generated_at,
                    status=status,
                    media_mode=telegram_media_mode,
                    output_locale=output_locale,
                    prebuilt_view_model=localized_market_news_view_model,
                    text_override=telegram_text_override,
                )
            else:
                status["brief_push"] = push_text(
                    payload.brief.render_text(),
                    log_path,
                    scope=payload.brief.title,
                    output_locale=output_locale,
                )
    except Exception as exc:  # noqa: BLE001 - runtime must not kill the scheduler on one bad cycle.
        status["ok"] = False
        status["errors"].append(str(exc))
        append_runtime_log(log_path, {"event": "fionaRuntimeError", "ok": False, "error": str(exc)})
        if fallback_to_wilson and (snapshot is not None or output_locale == OutputLocale.EN_US):
            fallback_text = (
                compose_safe_en_us_brief_fallback(brief, generated_at)
                if output_locale == OutputLocale.EN_US
                else render_wilson_markdown(snapshot)
            )
            for base in (latest_dir, archive_dir):
                (base / "fiona_fallback_telegram.md").write_text(fallback_text, encoding="utf-8")
            fallback_status: dict[str, Any] = {"used": True, "markdown": str(latest_dir / "fiona_fallback_telegram.md")}
            if send:
                fallback_status["push"] = push_text(
                    fallback_text,
                    log_path,
                    scope="Fiona fallback",
                    output_locale=output_locale,
                )
            status["fallback"] = fallback_status
        else:
            status["fallback"] = {"used": False}

    for base in (latest_dir, archive_dir):
        (base / "fiona_status.json").write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
    return status


def build_payload(
    snapshot: dict[str, Any],
    generated_at: datetime,
    memory_path: Path,
    brief: BriefSelector,
    output_locale: OutputLocale | str = OutputLocale.ZH_CN,
) -> FionaPayload:
    locale = output_locale if isinstance(output_locale, OutputLocale) else parse_output_locale(output_locale)
    memory = FionaMemory.load(memory_path)
    raw_events = snapshot_to_events(snapshot, generated_at)
    engine = FionaAlertEngine(LifecycleManager(memory.event_memory))
    events = [engine.process(event) for event in raw_events]
    memory.event_memory = engine.lifecycle_manager.records
    narratives = memory.update_narratives(events, now=generated_at)
    alert_messages = [
        render_alert(event, output_locale=locale)
        for event in events
        if event.push_decision == PushDecision.SEND_NOW
    ]

    brief_obj = build_selected_brief(brief, events, narratives, snapshot, generated_at, output_locale=locale)
    if brief_obj is not None:
        memory.remember_decision(
            DecisionMemoryRecord(
                created_at=generated_at,
                scope=brief_obj.title,
                direction=dominant_direction(events),
                conviction_score=average_conviction(events),
                reasoning=brief_obj.fiona_view,
                linked_event_ids=brief_obj.linked_event_ids,
                linked_narrative_ids=brief_obj.linked_narrative_ids,
            )
        )
    memory.save(memory_path)
    return FionaPayload(snapshot=snapshot, events=events, narratives=narratives, brief=brief_obj, alert_messages=alert_messages)


def build_selected_brief(
    brief: BriefSelector,
    events: list[FionaEvent],
    narratives: list[Any],
    snapshot: dict[str, Any],
    generated_at: datetime,
    output_locale: OutputLocale | str = OutputLocale.ZH_CN,
) -> FionaBrief | None:
    if str(brief).lower() == "alert":
        return None
    if str(brief).lower() == "auto":
        due = due_brief_kinds(generated_at)
        if not due:
            return None
        return build_brief(due[0], events, narratives, snapshot, generated_at, output_locale=output_locale)
    return build_brief(
        brief_kind_from_name(brief),
        events,
        narratives,
        snapshot,
        generated_at,
        output_locale=output_locale,
    )


def should_push_alerts(brief: BriefSelector) -> bool:
    if not alert_enabled():
        return False
    if alert_dry_run():
        return False
    return bool(str(brief).strip().lower().replace("-", "_") == "alert" or alert_enabled())


def alert_enabled() -> bool:
    value = first_runtime_env("FIONA_ALERT_ENABLED", "FIONAALERTENABLED") or "0"
    return value.strip().lower() in {"1", "true", "yes", "on"}


def alert_dry_run() -> bool:
    value = first_runtime_env("FIONA_ALERT_DRY_RUN", "FIONAALERTDRYRUN") or "1"
    return value.strip().lower() not in {"0", "false", "no", "off"}


def run_scheduler(
    output_dir: Path = DEFAULT_OUTPUT,
    send: bool = False,
    timezone_name: str = DEFAULT_TIMEZONE,
    interval_minutes: int | None = None,
    max_cycles: int | None = None,
    cycle_runner: Callable[..., dict[str, Any]] | None = None,
    sleep_fn: Callable[[float], None] = time_module.sleep,
) -> None:
    interval = scheduler_interval_minutes(interval_minutes)
    cycle = 0
    while True:
        cycle += 1
        try:
            runner = cycle_runner or run_scheduler_cycle
            status = runner(
                output_dir=output_dir,
                send=send,
                timezone_name=timezone_name,
                interval_minutes=interval,
            )
        except Exception as exc:  # noqa: BLE001 - production scheduler must survive one bad cycle.
            status = {
                "ok": False,
                "scheduler_cycle_error": str(exc),
                "send": send,
                "timezone": timezone_name,
                "interval_minutes": interval,
            }
        print(json.dumps({"scheduler_cycle": cycle, **status}, ensure_ascii=False, indent=2), flush=True)
        if max_cycles is not None and cycle >= max_cycles:
            return
        sleep_seconds = interval * 60
        if not status.get("ok", True):
            sleep_seconds = min(60, sleep_seconds)
        sleep_fn(sleep_seconds)


def run_scheduler_cycle(
    output_dir: Path = DEFAULT_OUTPUT,
    send: bool = False,
    timezone_name: str = DEFAULT_TIMEZONE,
    interval_minutes: int | None = None,
    now: datetime | None = None,
    runner: Callable[..., dict[str, Any]] | None = None,
) -> dict[str, Any]:
    current = now or now_in_timezone(timezone_name)
    ledger_path = output_dir / SCHEDULER_LEDGER_NAME
    ledger = SchedulerLedger.load(ledger_path)
    occurrences = due_occurrences(current, ledger.last_check_at, timezone_name)
    occurrences.extend(ledger.deferred_occurrences(current))
    eligible_occurrences: list[ScheduledOccurrence] = []
    expired_results: list[dict[str, Any]] = []
    preserved_terminal_statuses = {
        "success",
        STATUS_SKIPPED_EXPIRED,
        STATUS_UNKNOWN_DELIVERY_STATE,
        STATUS_PARTIAL_DELIVERY,
        STATUS_SUPPRESSED_COLLISION,
    }
    for occurrence in {item.occurrence_id: item for item in occurrences}.values():
        if not occurrence_expired(occurrence, current):
            eligible_occurrences.append(occurrence)
            continue
        existing = ledger.entry_for(occurrence)
        existing_status = str(existing.get("status", "")) if existing else ""
        if existing_status in preserved_terminal_statuses:
            expired_results.append(
                occurrence_result(occurrence, "skipped", True, existing_status)
            )
            continue
        ledger.mark_skipped_expired(occurrence, current)
        expired_results.append(
            occurrence_result(occurrence, STATUS_SKIPPED_EXPIRED, True, "catch_up_window_expired")
        )
    arbitration_decisions = arbitrate_occurrences(eligible_occurrences, current)
    status: dict[str, Any] = {
        "ok": True,
        "scheduler_now": current.isoformat(),
        "timezone": timezone_name,
        "send": send,
        "interval_minutes": scheduler_interval_minutes(interval_minutes),
        "ledger_path": str(ledger_path),
        "ledger_load_error": ledger.load_error,
        "due_occurrences": [occurrence.occurrence_id for occurrence in occurrences],
        "arbitration": [
            {
                "occurrence_id": decision.occurrence.occurrence_id,
                "action": decision.action,
                "reason": decision.reason,
                "suppressed_by_occurrence_id": decision.suppressed_by_occurrence_id,
                "defer_until": decision.defer_until.isoformat() if decision.defer_until else None,
            }
            for decision in arbitration_decisions
        ],
        "occurrence_results": expired_results,
        "errors": [],
    }

    for decision in arbitration_decisions:
        if decision.action == ACTION_SUPPRESS:
            ledger.mark_suppressed_collision(
                decision.occurrence,
                suppressed_by_occurrence_id=decision.suppressed_by_occurrence_id or "",
                suppression_reason=decision.reason,
                arbitrated_at=current,
            )
            result = occurrence_result(decision.occurrence, STATUS_SUPPRESSED_COLLISION, True, decision.reason)
        elif decision.action == ACTION_DEFER:
            ledger.mark_deferred_collision(
                decision.occurrence,
                suppressed_by_occurrence_id=decision.suppressed_by_occurrence_id or "",
                suppression_reason=decision.reason,
                arbitrated_at=current,
                defer_until=decision.defer_until or current,
            )
            result = occurrence_result(decision.occurrence, STATUS_DEFERRED_COLLISION, True, decision.reason)
        else:
            result = execute_scheduled_occurrence(
                occurrence=decision.occurrence,
                ledger=ledger,
                output_dir=output_dir,
                send=send,
                timezone_name=timezone_name,
                runner=runner or run_once,
            )
        status["occurrence_results"].append(result)
        if not result.get("ok", True):
            status["ok"] = False

    ledger.update_last_check(current)
    try:
        ledger.save()
    except Exception as exc:  # noqa: BLE001 - scheduler should report state persistence issues and continue.
        status["ok"] = False
        status["errors"].append(f"ledger_save_failed: {exc}")
    return status


def execute_scheduled_occurrence(
    occurrence: ScheduledOccurrence,
    ledger: SchedulerLedger,
    output_dir: Path,
    send: bool,
    timezone_name: str,
    runner: Callable[..., dict[str, Any]],
) -> dict[str, Any]:
    can_execute, reason = can_execute_occurrence(ledger, occurrence, occurrence.detected_at)
    if reason == STATUS_SKIPPED_EXPIRED:
        ledger.mark_skipped_expired(occurrence, occurrence.detected_at)
        return occurrence_result(occurrence, STATUS_SKIPPED_EXPIRED, True, reason)
    if not can_execute:
        return occurrence_result(occurrence, "skipped", True, reason)

    try:
        ledger.mark_running(occurrence, occurrence.detected_at)
        ledger.save()
    except Exception as exc:  # noqa: BLE001 - do not send if we cannot record the attempt.
        return occurrence_result(occurrence, "ledger_write_failed_before_send", False, str(exc))

    try:
        run_status = runner(
            output_dir=output_dir,
            brief=occurrence.brief_name,
            send=send,
            timezone_name=timezone_name,
            fallback_to_wilson=True,
        )
    except Exception as exc:  # noqa: BLE001 - one bad task must not stop other due tasks.
        finished_at = now_in_timezone(timezone_name)
        ledger.mark_failed(occurrence, finished_at, str(exc))
        try:
            ledger.save()
        except Exception:
            pass
        return occurrence_result(occurrence, "failed", False, str(exc))
    finished_at = now_in_timezone(timezone_name)
    final_delivery_status = delivery_status(run_status, send)
    delivered = final_delivery_status == "success"
    partial = final_delivery_status == STATUS_PARTIAL_DELIVERY
    final_status = "success" if delivered else STATUS_PARTIAL_DELIVERY if partial else "failed"
    try:
        if delivered:
            ledger.mark_success(occurrence, finished_at)
        elif partial:
            ledger.mark_partial_delivery(occurrence, finished_at, delivery_error_summary(run_status, send))
        else:
            ledger.mark_failed(occurrence, finished_at, delivery_error_summary(run_status, send))
        ledger.save()
    except Exception as exc:  # noqa: BLE001 - after Telegram success this is an unknown delivery state.
        if delivered or partial:
            ledger.mark_unknown_delivery_state(occurrence, finished_at, f"ledger_success_write_failed: {exc}")
            remember_uncertain_occurrence(occurrence.occurrence_id)
            journal_payload = {
                "occurrence_id": occurrence.occurrence_id,
                "timestamp": finished_at.isoformat(),
                "reason": str(exc),
                "delivery_status": final_delivery_status,
                "message_ids": (run_status.get("brief_push") or {}).get("message_ids") if isinstance(run_status.get("brief_push"), dict) else [],
            }
            try:
                write_uncertain_delivery_journal(output_dir / UNCERTAIN_DELIVERY_LOG_NAME, journal_payload)
            except Exception as journal_exc:  # noqa: BLE001 - last-resort visibility for local runs.
                print(f"fiona uncertain delivery journal failed: {journal_exc}", flush=True)
            try:
                ledger.save()
            except Exception:
                pass
            return occurrence_result(occurrence, STATUS_UNKNOWN_DELIVERY_STATE, False, str(exc), run_status)
        return occurrence_result(occurrence, "ledger_write_failed_after_run", False, str(exc), run_status)
    return occurrence_result(occurrence, final_status, delivered or partial, "delivered" if delivered else final_delivery_status, run_status)


def occurrence_result(
    occurrence: ScheduledOccurrence,
    status: str,
    ok: bool,
    reason: str,
    run_status: dict[str, Any] | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "ok": ok,
        "occurrence_id": occurrence.occurrence_id,
        "task_name": occurrence.task_name,
        "brief_name": occurrence.brief_name,
        "scheduled_at": occurrence.scheduled_at.isoformat(),
        "detected_at": occurrence.detected_at.isoformat(),
        "catch_up": occurrence.catch_up,
        "status": status,
        "reason": reason,
    }
    if run_status is not None:
        result["run_status"] = run_status
    return result


def scheduler_interval_minutes(interval_minutes: int | None = None) -> int:
    return scheduler_interval_minutes_v2(interval_minutes)


def validate_market_news_image_runtime(
    output_dir: Path = DEFAULT_OUTPUT,
    timezone_name: str = DEFAULT_TIMEZONE,
    snapshot_builder: Callable[[datetime], dict[str, Any]] = build_snapshot,
    renderer: Callable[[Any, str | Path], Path] | None = None,
    media_mode: TelegramMediaMode = TelegramMediaMode.PHOTO,
    output_locale: OutputLocale = OutputLocale.EN_US,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "ok": False,
        "mode": "validation",
        "media_mode": media_mode.value,
        "output_locale": output_locale.value,
        "data_source": "production_runtime",
        "view_model_success": False,
        "caption_success": False,
        "caption_length": 0,
        "caption_hash": "",
        "caption_checks": {},
        "section_presence": {},
        "render_success": False,
        "image_validation": False,
        "png_width": 0,
        "png_height": 0,
        "png_size_bytes": 0,
        "cleanup_state": "not_started",
        "market_regime": "",
        "evidence_level": "",
        "telegram_api_calls": 0,
        "scheduler_ledger_mutations": 0,
        "temporary_path_exists_after_cleanup": False,
        "cjk_leakage": False,
        "error_category": "",
        "errors": [],
    }
    stage = "snapshot"
    temp_directory: tempfile.TemporaryDirectory[str] | None = None
    temp_root: Path | None = None
    try:
        generated_at = now_in_timezone(timezone_name)
        snapshot = snapshot_builder(generated_at)

        stage = "view_model"
        memory = FionaMemory.load(output_dir / MEMORY_NAME)
        engine = FionaAlertEngine(LifecycleManager(memory.event_memory))
        events = [engine.process(event) for event in snapshot_to_events(snapshot, generated_at)]
        narratives = memory.update_narratives(events, now=generated_at)
        view_model = build_market_news_view_model(
            snapshot,
            events,
            narratives,
            generated_at=generated_at,
            output_locale=output_locale,
        )
        evidence, regime, _ = caption_intelligence(view_model)
        result["view_model_success"] = True
        result["market_regime"] = regime.regime.value
        result["evidence_level"] = evidence.level.value

        stage = "caption"
        caption = compose_market_news_caption(view_model)
        caption_checks = validate_market_news_caption(caption, output_locale=output_locale)
        result["caption_length"] = len(caption)
        result["caption_hash"] = hashlib.sha256(caption.encode("utf-8")).hexdigest()
        result["caption_checks"] = caption_checks
        result["section_presence"] = caption_checks["section_presence"]
        result["cjk_leakage"] = contains_cjk(caption)
        result["caption_success"] = all(
            value for key, value in caption_checks.items() if key != "section_presence"
        ) and all(caption_checks["section_presence"].values())
        if not result["caption_success"]:
            raise ValueError("Caption RC validation failed")

        stage = "temporary_file"
        temp_directory = tempfile.TemporaryDirectory(prefix="fiona-market-news-validation-")
        temp_root = Path(temp_directory.name)
        output_path = temp_root / "fiona_market_news_validation.png"

        stage = "renderer"
        rendered_path = (
            renderer(view_model, output_path)
            if renderer is not None
            else render_for_media(view_model, output_path, media_mode)
        )
        result["render_success"] = True

        stage = "image_validation"
        validation = validate_market_news_png(
            rendered_path,
            expected_size=expected_image_size(media_mode),
        )
        result["image_validation"] = True
        result["png_width"] = validation.width
        result["png_height"] = validation.height
        result["png_size_bytes"] = validation.size_bytes
    except Exception as exc:  # noqa: BLE001 - validation must return a safe machine-readable result.
        result["error_category"] = f"{stage}_failed"
        result["errors"].append(safe_error(exc))
    finally:
        if temp_directory is not None:
            try:
                temp_directory.cleanup()
            except Exception as exc:  # noqa: BLE001 - cleanup failure is a failed release gate.
                result["cleanup_state"] = "failed"
                result["errors"].append(f"cleanup_failed: {safe_error(exc)}")
            else:
                result["cleanup_state"] = "success"
        else:
            result["cleanup_state"] = "not_required"
        result["temporary_path_exists_after_cleanup"] = bool(temp_root and temp_root.exists())

    result["ok"] = bool(
        result["view_model_success"]
        and result["caption_success"]
        and result["render_success"]
        and result["image_validation"]
        and (result["png_width"], result["png_height"]) == expected_image_size(media_mode)
        and 0 < result["png_size_bytes"] < MAX_IMAGE_BYTES
        and result["cleanup_state"] == "success"
        and not result["temporary_path_exists_after_cleanup"]
        and result["telegram_api_calls"] == 0
        and result["scheduler_ledger_mutations"] == 0
        and not result["cjk_leakage"]
        and not result["errors"]
    )
    return result


def validate_market_news_caption(
    caption: str,
    *,
    output_locale: OutputLocale | str = OutputLocale.ZH_CN,
) -> dict[str, Any]:
    locale = output_locale if isinstance(output_locale, OutputLocale) else parse_output_locale(output_locale)
    if locale == OutputLocale.EN_US:
        required_sections = (
            "Fiona Global Intelligence",
            "Market state:",
            "Fiona's view:",
            "Watch next:",
        )
        section_presence = {section: section in caption for section in required_sections}
        hashtag_tokens = [token for token in caption.split() if token.startswith("#")]
        valid_hashtags = [token for token in hashtag_tokens if re.fullmatch(r"#[A-Za-z0-9_]+", token)]
        return {
            "section_presence": section_presence,
            "length_safe": 180 <= len(caption) <= 450,
            "hashtags_safe": (
                len(hashtag_tokens) <= 4
                and len(valid_hashtags) == len(hashtag_tokens)
                and len({item.casefold() for item in valid_hashtags}) == len(valid_hashtags)
            ),
            "markup_safe": re.search(r"<[^>]+>", caption) is None,
            "language_safe": not contains_cjk(caption),
            "density_safe": caption.count("\n") <= 9,
        }
    required_sections = (
        "【Market Regime】",
        "【What Changed】",
        "【Fiona’s View】",
        "【Watch Next】",
    )
    section_presence = {section: section in caption for section in required_sections}
    hashtag_tokens = [token for token in caption.split() if token.startswith("#")]
    valid_hashtags = [token for token in hashtag_tokens if re.fullmatch(r"#[A-Za-z0-9_]+", token)]
    forbidden_terms = (
        "买入",
        "卖出",
        "加仓",
        "减仓",
        "梭哈",
        "抄底",
        "逃顶",
        "目标价",
        "必涨",
        "必跌",
        "财富密码",
        "精准预测",
        "独家发现",
        "千载难逢",
        "牛市启动",
    )
    return {
        "section_presence": section_presence,
        "length_safe": 0 < len(caption) <= CAPTION_MAX_CHARS,
        "hashtags_safe": (
            len(hashtag_tokens) <= MAX_TAGS
            and len(valid_hashtags) == len(hashtag_tokens)
            and len({item.casefold() for item in valid_hashtags}) == len(valid_hashtags)
        ),
        "markup_safe": (
            caption.count("【") == caption.count("】")
            and re.search(r"<[^>]+>", caption) is None
        ),
        "language_safe": not any(term in caption for term in forbidden_terms),
        "density_safe": caption.count("\n• ") <= 5,
    }


def build_brief(
    kind: FionaBriefKind,
    events: list[FionaEvent],
    narratives: list[Any],
    snapshot: dict[str, Any],
    generated_at: datetime,
    output_locale: OutputLocale | str = OutputLocale.ZH_CN,
) -> FionaBrief:
    if kind == FionaBriefKind.MORNING:
        return build_morning_brief(events, narratives, generated_at=generated_at, output_locale=output_locale)
    if kind == FionaBriefKind.EVENING:
        return build_evening_brief(events, narratives, generated_at=generated_at, output_locale=output_locale)
    if kind == FionaBriefKind.MARKET_NEWS:
        return build_market_news_brief(
            events,
            narratives,
            snapshot=snapshot,
            generated_at=generated_at,
            output_locale=output_locale,
        )
    if kind == FionaBriefKind.DAILY:
        return build_daily_brief(
            events,
            narratives,
            snapshot=snapshot,
            generated_at=generated_at,
            output_locale=output_locale,
        )
    if kind == FionaBriefKind.WEEKLY:
        return build_weekly_brief(
            events,
            narratives,
            snapshot=snapshot,
            generated_at=generated_at,
            output_locale=output_locale,
        )
    raise ValueError(f"Unsupported Fiona brief kind: {kind}")


def due_brief_kinds(now: datetime, tolerance_minutes: int = 15) -> list[FionaBriefKind]:
    current = now if now.tzinfo else now.replace(tzinfo=timezone.utc)
    due: list[FionaBriefKind] = []
    for kind, schedule in BRIEF_SCHEDULES.items():
        if kind == FionaBriefKind.WEEKLY and current.isoweekday() != 7:
            continue
        scheduled = current.replace(hour=schedule.send_time.hour, minute=schedule.send_time.minute, second=0, microsecond=0)
        if abs(current - scheduled) <= timedelta(minutes=tolerance_minutes):
            due.append(kind)
    return due


def brief_kind_from_name(value: BriefSelector) -> FionaBriefKind:
    if isinstance(value, FionaBriefKind):
        return value
    normalized = str(value).strip().lower().replace("-", "_")
    aliases = {
        "morning": FionaBriefKind.MORNING,
        "evening": FionaBriefKind.EVENING,
        "market": FionaBriefKind.MARKET_NEWS,
        "market_news": FionaBriefKind.MARKET_NEWS,
        "news": FionaBriefKind.MARKET_NEWS,
        "daily": FionaBriefKind.DAILY,
        "weekly": FionaBriefKind.WEEKLY,
    }
    if normalized not in aliases:
        raise ValueError(f"Unsupported brief selector: {value}")
    return aliases[normalized]


def snapshot_to_events(snapshot: dict[str, Any], generated_at: datetime) -> list[FionaEvent]:
    heatmap = {str(item.get("key")): item for item in snapshot.get("heatmap", []) if isinstance(item, dict)}
    events = [
        us_event(snapshot.get("us_market", {}), heatmap.get("us", {}), generated_at),
        china_event(snapshot.get("china_market", {}), heatmap.get("china", {}), generated_at),
        btc_event(snapshot.get("crypto_market", {}), heatmap.get("crypto", {}), generated_at),
        eth_event(snapshot.get("crypto_market", {}), generated_at),
        rwa_event(snapshot.get("rwa_market", {}), heatmap.get("rwa", {}), generated_at),
    ]
    return [event for event in events if event is not None]


def us_event(market: Any, heat: dict[str, Any], generated_at: datetime) -> FionaEvent:
    data = market if isinstance(market, dict) else {}
    overview = as_text_list(data.get("market_overview"))
    macro = as_text_list(data.get("macro_policy"))
    ai = as_text_list(data.get("ai_sector"))
    title = "US market macro and AI sector update"
    what = first_or_default(macro, first_or_default(overview, "美国市场出现新的宏观与指数信号。"))
    direction = direction_from_heat(heat)
    score = heat_score(heat)
    return FionaEvent(
        event_id=f"us_{generated_at.strftime('%Y%m%d%H%M')}",
        created_at=generated_at,
        source="wilson_snapshot",
        category=EventCategory.MACRO,
        title=title,
        what_happened=what,
        why_important="美股会通过利率预期、科技权重和美元流动性影响全球风险偏好。",
        affected_assets=["SPY", "QQQ", "DXY", "US10Y", "BTC"],
        watch_next=["美债收益率和美元是否继续同向上行", "AI龙头是否获得成交量确认"],
        fiona_view="美股信号需要同时看宏观、ETF和AI龙头承接，不能只看指数涨跌。",
        impact_score=impact_from_heat(score),
        urgency_score=6,
        confidence_score=7,
        market_direction=direction,
        raw_data={
            "narratives": ["macro_liquidity_repricing", "ai_valuation_reset"] if ai else ["macro_liquidity_repricing"],
            "narrative_strength": 12,
            "novelty": 6,
            "funds_score": funds_score_from_direction(direction),
            "fed_rate_related": contains_any(macro, ("fed", "fomc", "rate", "cpi", "ppi", "美联储", "利率", "通胀")),
            "signals": signals_for(direction),
        },
    )


def china_event(market: Any, heat: dict[str, Any], generated_at: datetime) -> FionaEvent:
    data = market if isinstance(market, dict) else {}
    policy = as_text_list(data.get("policy_update"))
    overview = as_text_list(data.get("market_overview"))
    direction = direction_from_heat(heat)
    score = heat_score(heat)
    return FionaEvent(
        event_id=f"china_{generated_at.strftime('%Y%m%d%H%M')}",
        created_at=generated_at,
        source="wilson_snapshot",
        category=EventCategory.REGULATION,
        title="China market policy and flow update",
        what_happened=first_or_default(policy, first_or_default(overview, "中国市场等待政策与资金承接确认。")),
        why_important="中国市场更依赖政策预期、流动性边际变化和核心资产承接。",
        affected_assets=["CSI500", "ASHR", "MCHI", "CNH"],
        watch_next=["政策口径是否转化为成交量", "核心资产和人民币汇率是否同步确认"],
        fiona_view="中国市场先看政策和资金是否形成闭环，单日涨跌不应直接外推。",
        impact_score=impact_from_heat(score),
        urgency_score=5,
        confidence_score=6,
        market_direction=direction,
        raw_data={
            "narratives": ["china_policy_flow_watch"],
            "narrative_strength": 8,
            "novelty": 5,
            "funds_score": funds_score_from_direction(direction),
            "major_regulatory_action": contains_any(policy, ("央行", "证监", "政策", "lpr", "rrr", "pboc", "csrc")),
            "signals": signals_for(direction),
        },
    )


def btc_event(crypto: Any, heat: dict[str, Any], generated_at: datetime) -> FionaEvent:
    data = crypto if isinstance(crypto, dict) else {}
    btc = data.get("btc") if isinstance(data.get("btc"), dict) else {}
    change = first_number(btc.get("change_pct"), btc.get("price_change_percentage_24h"))
    direction = direction_from_change(change, direction_from_heat(heat))
    return FionaEvent(
        event_id=f"btc_{generated_at.strftime('%Y%m%d%H%M')}",
        created_at=generated_at,
        source="wilson_snapshot",
        category=EventCategory.PRICE,
        title="BTC price and ETF confirmation watch",
        what_happened=f"BTC本周期变化 {format_pct(change)}。",
        why_important="BTC是加密风险偏好的核心锚，1小时或短周期波动需要看ETF、稳定币和杠杆是否同步确认。",
        affected_assets=["BTC", "ETH", "SOL"],
        watch_next=["BTC关键支撑/压力是否被放量突破", "ETF资金流和稳定币供给是否同步恶化"],
        fiona_view="BTC波动本身不是结论，只有资金流和风险指标共振时才提高情报权重。",
        impact_score=impact_from_change(change),
        urgency_score=8 if abs(change or 0) >= 1.5 else 5,
        confidence_score=8,
        market_direction=direction,
        raw_data={
            "symbol": "BTC",
            "change_pct": change or 0,
            "support_break": bool((change or 0) <= -1.5),
            "narratives": ["btc_etf_flow_weakness"] if (change or 0) < 0 else [],
            "narrative_strength": 14 if abs(change or 0) >= 1.5 else 8,
            "novelty": 7,
            "funds_score": funds_score_from_direction(direction),
            "signals": signals_for(direction),
        },
        evidence=["price_move"] if abs(change or 0) >= 1.5 else [],
    )


def eth_event(crypto: Any, generated_at: datetime) -> FionaEvent:
    data = crypto if isinstance(crypto, dict) else {}
    eth = data.get("eth") if isinstance(data.get("eth"), dict) else {}
    change = first_number(eth.get("change_pct"), eth.get("price_change_percentage_24h"))
    direction = direction_from_change(change, MarketDirection.NEUTRAL)
    return FionaEvent(
        event_id=f"eth_{generated_at.strftime('%Y%m%d%H%M')}",
        created_at=generated_at,
        source="wilson_snapshot",
        category=EventCategory.PRICE,
        title="ETH price confirmation watch",
        what_happened=f"ETH本周期变化 {format_pct(change)}。",
        why_important="ETH波动会影响Layer1、DeFi和山寨风险偏好，需要和BTC及资金流一起判断。",
        affected_assets=["ETH", "L1", "DeFi"],
        watch_next=["ETH/BTC强弱是否继续变化", "链上活跃度和DEX成交是否确认"],
        fiona_view="ETH若没有资金流和链上活跃确认，单独波动更像风险偏好噪音。",
        impact_score=impact_from_change(change),
        urgency_score=8 if abs(change or 0) >= 3 else 5,
        confidence_score=7,
        market_direction=direction,
        raw_data={
            "symbol": "ETH",
            "change_pct": change or 0,
            "narrative_strength": 8,
            "novelty": 5,
            "funds_score": funds_score_from_direction(direction),
            "signals": signals_for(direction),
        },
        evidence=["price_move"] if abs(change or 0) >= 3 else [],
    )


def rwa_event(market: Any, heat: dict[str, Any], generated_at: datetime) -> FionaEvent:
    data = market if isinstance(market, dict) else {}
    direction = direction_from_heat(heat)
    score = heat_score(heat)
    events = rwa_relevant_lines(as_text_list(data.get("major_events")))
    return FionaEvent(
        event_id=f"rwa_{generated_at.strftime('%Y%m%d%H%M')}",
        created_at=generated_at,
        source="wilson_snapshot",
        category=EventCategory.RWA,
        title="RWA institutional adoption watch",
        what_happened=first_or_default(events, "RWA市场继续跟踪TVL、市值、成交和机构事件。"),
        why_important="RWA是机构资金链上化的重要线索，价值在持续性和资金确认，不在短线热度。",
        affected_assets=["RWA", "ONDO", "MKR", "BUIDL"],
        watch_next=["RWA TVL是否持续流入", "机构项目更新是否带来真实资金和使用场景"],
        fiona_view="RWA应看机构采用和资金持续性，避免把短期公告当作完整主线。",
        impact_score=impact_from_heat(score),
        urgency_score=5,
        confidence_score=7,
        market_direction=direction,
        raw_data={
            "narratives": ["rwa_institutional_adoption"],
            "notable_update": bool(events),
            "narrative_strength": 12,
            "novelty": 6,
            "funds_score": funds_score_from_direction(direction),
            "signals": signals_for(direction),
        },
    )


def rwa_relevant_lines(lines: list[str]) -> list[str]:
    keywords = ("rwa", "real world", "tokenized", "tokenization", "treasury", "blackrock", "franklin", "ondo", "buidl", "代币化", "国债")
    return [line for line in lines if contains_any([line], keywords)]


def write_payload(
    latest_dir: Path,
    archive_dir: Path,
    payload: FionaPayload,
    status: dict[str, Any],
    *,
    telegram_text_override: str | None = None,
) -> None:
    for base in (latest_dir, archive_dir):
        base.mkdir(parents=True, exist_ok=True)
        (base / "fiona_snapshot.json").write_text(json.dumps(payload.snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
        (base / "fiona_events.json").write_text(json.dumps([event.to_dict() for event in payload.events], ensure_ascii=False, indent=2), encoding="utf-8")
        (base / "fiona_narratives.json").write_text(
            json.dumps([record.to_dict() for record in payload.narratives], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        if payload.alert_messages:
            (base / "fiona_alerts.md").write_text("\n\n---\n\n".join(payload.alert_messages), encoding="utf-8")
        else:
            (base / "fiona_alerts.md").unlink(missing_ok=True)
        if payload.brief is not None:
            telegram_text = telegram_text_override or payload.brief.render_text()
            (base / "fiona_telegram.md").write_text(telegram_text, encoding="utf-8")
        else:
            (base / "fiona_telegram.md").unlink(missing_ok=True)
    status["alerts"]["count"] = len(payload.alert_messages)
    if payload.brief is not None:
        status["scheduled_briefs"].append(
            {
                "kind": payload.brief.kind.value,
                "title": payload.brief.title,
                "markdown": str(latest_dir / "fiona_telegram.md"),
            }
        )


def push_alerts(
    alert_messages: list[str],
    log_path: Path,
    output_locale: OutputLocale | str = OutputLocale.ZH_CN,
) -> list[dict[str, Any]]:
    results = []
    for index, message in enumerate(alert_messages, 1):
        result = push_text(
            message,
            log_path,
            scope=f"Fiona Alert {index}",
            output_locale=output_locale,
        )
        results.append(result)
    return results


def push_market_news(
    payload: FionaPayload,
    log_path: Path,
    *,
    mode: MarketNewsMode,
    generated_at: datetime,
    status: dict[str, Any],
    media_mode: TelegramMediaMode = TelegramMediaMode.DOCUMENT,
    output_locale: OutputLocale = OutputLocale.ZH_CN,
    prebuilt_view_model: Any | None = None,
    text_override: str | None = None,
) -> dict[str, Any]:
    if payload.brief is None:
        raise ValueError("Market News delivery requires a generated brief.")
    view_model_cache: dict[str, Any] = {}
    if prebuilt_view_model is not None:
        view_model_cache["value"] = prebuilt_view_model

    def view_model_factory() -> Any:
        if "value" not in view_model_cache:
            view_model_cache["value"] = build_market_news_view_model(
                payload.snapshot,
                payload.events,
                payload.narratives,
                generated_at=generated_at,
                output_locale=output_locale,
            )
        return view_model_cache["value"]

    legacy_text = text_override or payload.brief.render_text()
    if output_locale == OutputLocale.EN_US and text_override is None:
        legacy_text = compose_market_news_fallback_text(view_model_factory())
    if mode == MarketNewsMode.TEXT:
        return push_text(
            legacy_text,
            log_path,
            scope=payload.brief.title,
            output_locale=output_locale,
        )

    coordinator = MarketNewsDeliveryCoordinator(
        text_sender=lambda text: push_text(
            text,
            log_path,
            scope=payload.brief.title,
            output_locale=output_locale,
        ),
        document_sender=telegram_send_document,
        photo_sender=telegram_send_photo,
        logger=lambda item: append_runtime_log(log_path, item),
    )
    delivery = coordinator.deliver(
        mode=mode,
        legacy_text=legacy_text,
        view_model_factory=view_model_factory,
        media_mode=media_mode,
        output_locale=output_locale.value,
    )
    status["market_news_delivery"] = delivery.to_dict()
    return delivery.push_result


def push_text(
    text: str,
    log_path: Path,
    scope: str,
    output_locale: OutputLocale | str | None = None,
) -> dict[str, Any]:
    locale = output_locale_from_env() if output_locale is None else (
        output_locale if isinstance(output_locale, OutputLocale) else parse_output_locale(output_locale)
    )
    safe_text = finalize_user_visible_text(
        text,
        locale,
        fallback=lambda: compose_safe_en_us_brief_fallback(scope, datetime.now(timezone.utc)),
    )
    if safe_text != text:
        append_runtime_log(
            log_path,
            {
                "event": "fionaLocaleFallback",
                "scope": scope,
                "output_locale": locale.value,
                "reason": "cjk_leakage_blocked",
            },
        )
    chunks = split_message(safe_text)
    result: dict[str, Any] = {
        "scope": scope,
        "ok": False,
        "delivery_status": "failed",
        "message_ids": [],
        "successful_chunks": [],
        "failed_chunks": [],
        "errors": [],
        "total_chunks": len(chunks),
    }
    for index, chunk in enumerate(chunks, 1):
        try:
            response = telegram_send_message(chunk)
            message_id = telegram_message_id(response)
            if message_id is None:
                result["failed_chunks"].append(index)
                result["errors"].append(f"chunk {index}: missing message_id")
                append_telegram_log(log_path, {"event": "sendMessage", "scope": scope, "ok": False, "chunk": index, "error": "missing message_id"})
                continue
            result["message_ids"].append(message_id)
            result["successful_chunks"].append(index)
            append_telegram_log(log_path, {"event": "sendMessage", "scope": scope, "ok": True, "chunk": index, "message_id": message_id})
        except Exception as exc:  # noqa: BLE001 - push failure must not stop Fiona.
            error = str(exc)
            result["errors"].append(error)
            result["failed_chunks"].append(index)
            append_telegram_log(log_path, {"event": "sendMessage", "scope": scope, "ok": False, "chunk": index, "error": error})
    if result["successful_chunks"] and not result["failed_chunks"] and len(result["successful_chunks"]) == result["total_chunks"]:
        result["delivery_status"] = "success"
        result["ok"] = True
    elif result["successful_chunks"]:
        result["delivery_status"] = STATUS_PARTIAL_DELIVERY
        result["ok"] = False
    return result


def append_runtime_log(log_path: Path, payload: dict[str, Any]) -> None:
    append_telegram_log(log_path, payload)


def dominant_direction(events: list[FionaEvent]) -> MarketDirection:
    scores = {MarketDirection.BULLISH: 0, MarketDirection.NEUTRAL: 0, MarketDirection.BEARISH: 0}
    for event in events:
        scores[event.market_direction] += max(1, event.intelligence_score)
    return max(scores, key=scores.get) if events else MarketDirection.NEUTRAL


def average_conviction(events: list[FionaEvent]) -> int:
    if not events:
        return 0
    return round(sum(event.conviction_score for event in events) / len(events))


def now_in_timezone(timezone_name: str) -> datetime:
    try:
        from zoneinfo import ZoneInfo

        return datetime.now(ZoneInfo(timezone_name))
    except Exception:
        return datetime.now(timezone.utc)


def as_text_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    if isinstance(value, dict):
        text = value.get("text")
        return [str(text)] if text else []
    return []


def first_or_default(values: list[str], default: str) -> str:
    return values[0] if values else default


def heat_score(heat: dict[str, Any]) -> int:
    try:
        return int(heat.get("score", 50))
    except (TypeError, ValueError):
        return 50


def direction_from_heat(heat: dict[str, Any]) -> MarketDirection:
    status = str(heat.get("status", "")).lower()
    if status == "bullish":
        return MarketDirection.BULLISH
    if status == "bearish":
        return MarketDirection.BEARISH
    return MarketDirection.NEUTRAL


def direction_from_change(change: float | None, default: MarketDirection) -> MarketDirection:
    if change is None:
        return default
    if change > 0.4:
        return MarketDirection.BULLISH
    if change < -0.4:
        return MarketDirection.BEARISH
    return MarketDirection.NEUTRAL


def impact_from_heat(score: int) -> int:
    return max(4, min(10, round(4 + abs(score - 50) / 6)))


def impact_from_change(change: float | None) -> int:
    absolute = abs(change or 0)
    if absolute >= 5:
        return 10
    if absolute >= 3:
        return 9
    if absolute >= 1.5:
        return 8
    if absolute >= 0.8:
        return 6
    return 4


def funds_score_from_direction(direction: MarketDirection) -> int:
    if direction == MarketDirection.BULLISH:
        return 70
    if direction == MarketDirection.BEARISH:
        return 28
    return 50


def signals_for(direction: MarketDirection) -> dict[str, str]:
    if direction == MarketDirection.BULLISH:
        return {"price": "bullish", "funds": "inflow", "narrative": "supportive"}
    if direction == MarketDirection.BEARISH:
        return {"price": "bearish", "funds": "outflow", "risk": "stress"}
    return {"price": "neutral", "funds": "neutral", "narrative": "mixed"}


def contains_any(lines: list[str], keywords: tuple[str, ...]) -> bool:
    text = " ".join(lines).lower()
    return any(keyword.lower() in text for keyword in keywords)


def first_number(*values: Any) -> float | None:
    for value in values:
        try:
            if value in (None, "", "-"):
                continue
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def format_pct(value: float | None) -> str:
    if value is None:
        return "-"
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.2f}%"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fiona Intelligence System runtime")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--timezone", default=first_runtime_env("FIONA_TIMEZONE", "WILSON_TIMEZONE") or DEFAULT_TIMEZONE)
    parser.add_argument("--brief", default=os.getenv("FIONA_BRIEF", "auto"), help="auto, alert, morning, evening, market-news, daily, weekly")
    parser.add_argument("--send", action="store_true", help="Push generated Fiona text to Telegram")
    parser.add_argument("--no-fallback", action="store_true", help="Disable Wilson text fallback if Fiona generation fails")
    parser.add_argument("--interval-minutes", type=int, default=None, help="Scheduler polling interval")
    parser.add_argument("--max-cycles", type=int, default=None, help="Testing only: stop scheduler after N cycles")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("run-once", help="Generate one Fiona cycle")
    subparsers.add_parser("run-scheduler", help="Run Fiona continuously for Railway production")
    subparsers.add_parser(
        "validate-market-news-image",
        help="Validate the production Market News image pipeline without Telegram or scheduler state",
    )
    subparsers.add_parser(
        "validate-en-us-surfaces",
        help="Validate every active en-US user surface without Telegram or scheduler state",
    )
    subparsers.add_parser(
        "validate-global-coverage",
        help="Validate Gate 2 source, clustering, and shadow ranking without delivery or scheduler state",
    )
    subparsers.add_parser(
        "validate-source-registry",
        help="Validate the canonical source registry without network or production side effects",
    )
    return parser.parse_args()


def resolve_send(send_flag: bool) -> bool:
    for env_name in ("WILSON_SEND", "FIONA_SEND", "FIONA_SEND_TELEGRAM"):
        env_value = os.getenv(env_name)
        if env_value is not None and env_value.strip() != "":
            return env_value.strip() == "1"
    return bool(send_flag)


def first_runtime_env(*names: str) -> str:
    for name in names:
        value = os.getenv(name, "").strip()
        if value:
            return value
    return ""


def main() -> None:
    args = parse_args()
    if args.command == "validate-source-registry":
        validation = validate_registry(load_source_registry())
        print(json.dumps(validation, ensure_ascii=False, separators=(",", ":")), flush=True)
        raise SystemExit(0 if validation["ok"] else 1)
    if args.command == "validate-global-coverage":
        validation = validate_global_coverage_runtime()
        print(json.dumps(validation, ensure_ascii=False, separators=(",", ":")), flush=True)
        raise SystemExit(0 if validation["ok"] else 1)
    if args.command == "validate-en-us-surfaces":
        from app.fiona_surface_validation import validate_en_us_user_surfaces_runtime

        validation = validate_en_us_user_surfaces_runtime()
        print(json.dumps(validation, ensure_ascii=False, separators=(",", ":")), flush=True)
        raise SystemExit(0 if validation["all_user_surfaces_en_us"] else 1)
    if args.command == "validate-market-news-image":
        validation = validate_market_news_image_runtime(
            output_dir=args.output.expanduser(),
            timezone_name=args.timezone,
        )
        print(json.dumps(validation, ensure_ascii=False, separators=(",", ":")), flush=True)
        raise SystemExit(0 if validation["ok"] else 1)
    send = resolve_send(args.send)
    if args.command == "run-scheduler":
        run_scheduler(
            output_dir=args.output.expanduser(),
            send=send,
            timezone_name=args.timezone,
            interval_minutes=args.interval_minutes,
            max_cycles=args.max_cycles,
        )
        return
    status = run_once(
        output_dir=args.output.expanduser(),
        brief=args.brief,
        send=send,
        timezone_name=args.timezone,
        fallback_to_wilson=not args.no_fallback,
    )
    print(json.dumps(status, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
