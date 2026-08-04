from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from app.fiona_briefing import BRIEF_SCHEDULES, FionaBriefKind


DEFAULT_POLLING_INTERVAL_MINUTES = 5
MIN_POLLING_INTERVAL_MINUTES = 1
MAX_ATTEMPTS = 3
STALE_RUNNING_MINUTES = 30
STARTUP_LOOKBACK_MINUTES = 24 * 60
LEDGER_SCHEMA_VERSION = "1.0"

STATUS_PENDING = "pending"
STATUS_RUNNING = "running"
STATUS_SUCCESS = "success"
STATUS_FAILED = "failed"
STATUS_SKIPPED_EXPIRED = "skipped_expired"
STATUS_UNKNOWN_DELIVERY_STATE = "unknown_delivery_state"
STATUS_SUPPRESSED_COLLISION = "suppressed_collision"
STATUS_DEFERRED_COLLISION = "deferred_collision"
STATUS_PARTIAL_DELIVERY = "partial_delivery"

ACTION_SEND = "send"
ACTION_SUPPRESS = "suppress"
ACTION_DEFER = "defer"

CATCH_UP_WINDOWS_MINUTES: dict[FionaBriefKind, int] = {
    FionaBriefKind.MARKET_NEWS: 60,
    FionaBriefKind.MORNING: 120,
    FionaBriefKind.EVENING: 150,
    FionaBriefKind.DAILY: 120,
    FionaBriefKind.WEEKLY: 240,
}
TASK_PRIORITY: dict[FionaBriefKind, int] = {
    FionaBriefKind.WEEKLY: 500,
    FionaBriefKind.DAILY: 400,
    FionaBriefKind.EVENING: 300,
    FionaBriefKind.MORNING: 300,
    FionaBriefKind.MARKET_NEWS: 200,
}
COLLISION_WINDOW_MINUTES = 180
FRESH_OCCURRENCE_MINUTES = 10
DAILY_NEXT_DAY_CUTOFF = time(0, 30)
DEFER_MINUTES = DEFAULT_POLLING_INTERVAL_MINUTES
UNCERTAIN_DELIVERY_LOG_NAME = "fiona_scheduler_delivery_uncertain.log"
KNOWN_UNCERTAIN_OCCURRENCES: set[str] = set()


@dataclass(frozen=True)
class ArbitrationDecision:
    occurrence: ScheduledOccurrence
    action: str
    reason: str
    suppressed_by_occurrence_id: str | None = None
    defer_until: datetime | None = None


@dataclass(frozen=True)
class ScheduledOccurrence:
    occurrence_id: str
    task_name: str
    brief_name: str
    scheduled_at: datetime
    detected_at: datetime
    catch_up: bool
    status: str = STATUS_PENDING

    @classmethod
    def create(cls, kind: FionaBriefKind, scheduled_at: datetime, detected_at: datetime) -> ScheduledOccurrence:
        local_scheduled = ensure_aware(scheduled_at)
        local_detected = ensure_aware(detected_at).astimezone(local_scheduled.tzinfo)
        return cls(
            occurrence_id=occurrence_id_for(kind, local_scheduled),
            task_name=kind.value,
            brief_name=kind.value,
            scheduled_at=local_scheduled,
            detected_at=local_detected,
            catch_up=local_detected > local_scheduled,
        )

    def to_entry(self) -> dict[str, Any]:
        return {
            "occurrence_id": self.occurrence_id,
            "task_name": self.task_name,
            "brief_name": self.brief_name,
            "scheduled_at": isoformat(self.scheduled_at),
            "detected_at": isoformat(self.detected_at),
            "started_at": None,
            "finished_at": None,
            "status": self.status,
            "attempt_count": 0,
            "catch_up": self.catch_up,
            "error_summary": "",
            "updated_at": isoformat(self.detected_at),
        }


@dataclass
class SchedulerLedger:
    path: Path
    last_check_at: datetime | None = None
    entries: dict[str, dict[str, Any]] = field(default_factory=dict)
    load_error: str | None = None

    @classmethod
    def load(cls, path: Path) -> SchedulerLedger:
        if not path.exists():
            return cls(path=path)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            last_check = parse_optional_datetime(payload.get("last_check_at"))
            raw_entries = payload.get("entries", {})
            entries = raw_entries if isinstance(raw_entries, dict) else {}
            return cls(path=path, last_check_at=last_check, entries=entries)
        except Exception as exc:  # noqa: BLE001 - malformed runtime state must not kill Fiona.
            return cls(path=path, load_error=str(exc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": LEDGER_SCHEMA_VERSION,
            "last_check_at": isoformat(self.last_check_at) if self.last_check_at else None,
            "entries": self.entries,
        }

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp_path.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp_path, self.path)

    def update_last_check(self, checked_at: datetime) -> None:
        self.last_check_at = ensure_aware(checked_at)

    def entry_for(self, occurrence: ScheduledOccurrence) -> dict[str, Any] | None:
        entry = self.entries.get(occurrence.occurrence_id)
        return entry if isinstance(entry, dict) else None

    def ensure_entry(self, occurrence: ScheduledOccurrence) -> dict[str, Any]:
        entry = self.entry_for(occurrence)
        if entry is None:
            entry = occurrence.to_entry()
            self.entries[occurrence.occurrence_id] = entry
        return entry

    def mark_running(self, occurrence: ScheduledOccurrence, started_at: datetime) -> None:
        entry = self.ensure_entry(occurrence)
        entry["status"] = STATUS_RUNNING
        entry["started_at"] = isoformat(started_at)
        entry["finished_at"] = None
        entry["detected_at"] = isoformat(occurrence.detected_at)
        entry["catch_up"] = occurrence.catch_up
        entry["attempt_count"] = int(entry.get("attempt_count", 0) or 0) + 1
        entry["error_summary"] = ""
        entry["updated_at"] = isoformat(started_at)

    def mark_success(self, occurrence: ScheduledOccurrence, finished_at: datetime) -> None:
        entry = self.ensure_entry(occurrence)
        entry["status"] = STATUS_SUCCESS
        entry["finished_at"] = isoformat(finished_at)
        entry["error_summary"] = ""
        entry["updated_at"] = isoformat(finished_at)

    def mark_failed(self, occurrence: ScheduledOccurrence, finished_at: datetime, error_summary: str) -> None:
        entry = self.ensure_entry(occurrence)
        entry["status"] = STATUS_FAILED
        entry["finished_at"] = isoformat(finished_at)
        entry["error_summary"] = truncate_error(error_summary)
        entry["updated_at"] = isoformat(finished_at)

    def mark_skipped_expired(self, occurrence: ScheduledOccurrence, detected_at: datetime) -> None:
        entry = self.ensure_entry(occurrence)
        entry["status"] = STATUS_SKIPPED_EXPIRED
        entry["finished_at"] = isoformat(detected_at)
        entry["error_summary"] = "catch_up_window_expired"
        entry["updated_at"] = isoformat(detected_at)

    def mark_unknown_delivery_state(self, occurrence: ScheduledOccurrence, finished_at: datetime, error_summary: str) -> None:
        entry = self.ensure_entry(occurrence)
        entry["status"] = STATUS_UNKNOWN_DELIVERY_STATE
        entry["finished_at"] = isoformat(finished_at)
        entry["error_summary"] = truncate_error(error_summary)
        entry["updated_at"] = isoformat(finished_at)

    def mark_partial_delivery(self, occurrence: ScheduledOccurrence, finished_at: datetime, error_summary: str) -> None:
        entry = self.ensure_entry(occurrence)
        entry["status"] = STATUS_PARTIAL_DELIVERY
        entry["finished_at"] = isoformat(finished_at)
        entry["error_summary"] = truncate_error(error_summary)
        entry["updated_at"] = isoformat(finished_at)

    def mark_suppressed_collision(
        self,
        occurrence: ScheduledOccurrence,
        suppressed_by_occurrence_id: str,
        suppression_reason: str,
        arbitrated_at: datetime,
    ) -> None:
        entry = self.ensure_entry(occurrence)
        entry["status"] = STATUS_SUPPRESSED_COLLISION
        entry["finished_at"] = isoformat(arbitrated_at)
        entry["suppressed_by_occurrence_id"] = suppressed_by_occurrence_id
        entry["suppression_reason"] = suppression_reason
        entry["arbitrated_at"] = isoformat(arbitrated_at)
        entry["updated_at"] = isoformat(arbitrated_at)

    def mark_deferred_collision(
        self,
        occurrence: ScheduledOccurrence,
        suppressed_by_occurrence_id: str,
        suppression_reason: str,
        arbitrated_at: datetime,
        defer_until: datetime,
    ) -> None:
        entry = self.ensure_entry(occurrence)
        entry["status"] = STATUS_DEFERRED_COLLISION
        entry["finished_at"] = None
        entry["suppressed_by_occurrence_id"] = suppressed_by_occurrence_id
        entry["suppression_reason"] = suppression_reason
        entry["arbitrated_at"] = isoformat(arbitrated_at)
        entry["defer_until"] = isoformat(defer_until)
        entry["updated_at"] = isoformat(arbitrated_at)

    def deferred_occurrences(self, now: datetime) -> list[ScheduledOccurrence]:
        current = ensure_aware(now)
        occurrences: list[ScheduledOccurrence] = []
        for entry in self.entries.values():
            if not isinstance(entry, dict) or entry.get("status") != STATUS_DEFERRED_COLLISION:
                continue
            defer_until = parse_optional_datetime(entry.get("defer_until"))
            scheduled_at = parse_optional_datetime(entry.get("scheduled_at"))
            brief_name = entry.get("brief_name")
            if defer_until is None or scheduled_at is None or not brief_name:
                continue
            if defer_until > current:
                continue
            try:
                kind = FionaBriefKind(str(brief_name))
            except ValueError:
                continue
            occurrences.append(ScheduledOccurrence.create(kind, scheduled_at, current))
        return occurrences


def scheduler_interval_minutes(interval_minutes: int | None = None, env: dict[str, str] | None = None) -> int:
    if interval_minutes is not None:
        return normalize_interval(interval_minutes)

    source = env if env is not None else os.environ
    for name in ("WILSON_INTERVAL_MINUTES", "FIONA_RUNTIME_INTERVAL_MINUTES"):
        value = source.get(name)
        if value is not None and str(value).strip():
            return normalize_interval(value)
    return DEFAULT_POLLING_INTERVAL_MINUTES


def normalize_interval(value: Any) -> int:
    try:
        parsed = int(str(value).strip())
    except (TypeError, ValueError):
        return DEFAULT_POLLING_INTERVAL_MINUTES
    if parsed < MIN_POLLING_INTERVAL_MINUTES:
        return DEFAULT_POLLING_INTERVAL_MINUTES
    return parsed


def due_occurrences(
    now: datetime,
    last_check_at: datetime | None,
    timezone_name: str,
    startup_lookback_minutes: int | None = None,
) -> list[ScheduledOccurrence]:
    current = to_timezone(now, timezone_name)
    if last_check_at is None:
        return startup_due_occurrences(current, timezone_name)
    else:
        previous = to_timezone(last_check_at, timezone_name)
        lookback = startup_lookback_minutes if startup_lookback_minutes is not None else STARTUP_LOOKBACK_MINUTES
        window_start = previous if previous < current else current - timedelta(minutes=lookback)

    occurrences: list[ScheduledOccurrence] = []
    for scheduled_at, kind in scheduled_points_between(window_start, current, timezone_name):
        occurrences.append(ScheduledOccurrence.create(kind, scheduled_at, current))
    return occurrences


def startup_due_occurrences(current: datetime, timezone_name: str) -> list[ScheduledOccurrence]:
    occurrences: list[ScheduledOccurrence] = []
    max_window = max(CATCH_UP_WINDOWS_MINUTES.values())
    window_start = to_timezone(current, timezone_name) - timedelta(minutes=max_window, seconds=1)
    for scheduled_at, kind in scheduled_points_between(window_start, current, timezone_name):
        max_age = timedelta(minutes=CATCH_UP_WINDOWS_MINUTES[kind])
        if to_timezone(current, timezone_name) - scheduled_at <= max_age:
            occurrences.append(ScheduledOccurrence.create(kind, scheduled_at, current))
    return occurrences


def scheduled_points_between(start_exclusive: datetime, end_inclusive: datetime, timezone_name: str) -> list[tuple[datetime, FionaBriefKind]]:
    start = to_timezone(start_exclusive, timezone_name)
    end = to_timezone(end_inclusive, timezone_name)
    if start > end:
        start, end = end, start

    points: list[tuple[datetime, FionaBriefKind]] = []
    current_date = start.date()
    while current_date <= end.date():
        for kind, schedule in BRIEF_SCHEDULES.items():
            if kind == FionaBriefKind.WEEKLY and current_date.isoweekday() != 7:
                continue
            scheduled = combine_local(current_date, schedule.send_time, timezone_name)
            if start < scheduled <= end:
                points.append((scheduled, kind))
        current_date = current_date + timedelta(days=1)
    points.sort(key=lambda item: item[0])
    return points


def occurrence_expired(occurrence: ScheduledOccurrence, now: datetime) -> bool:
    kind = FionaBriefKind(occurrence.brief_name)
    current = to_timezone(now, occurrence.scheduled_at.tzinfo)
    scheduled = occurrence.scheduled_at.astimezone(current.tzinfo)
    if (
        kind == FionaBriefKind.DAILY
        and current.date() > scheduled.date()
        and current.timetz().replace(tzinfo=None) > DAILY_NEXT_DAY_CUTOFF
    ):
        return True
    max_age = timedelta(minutes=CATCH_UP_WINDOWS_MINUTES[kind])
    return current - scheduled > max_age


def can_execute_occurrence(
    ledger: SchedulerLedger,
    occurrence: ScheduledOccurrence,
    now: datetime,
    max_attempts: int = MAX_ATTEMPTS,
    uncertain_occurrence_ids: set[str] | None = None,
) -> tuple[bool, str]:
    uncertain = KNOWN_UNCERTAIN_OCCURRENCES if uncertain_occurrence_ids is None else uncertain_occurrence_ids
    if occurrence.occurrence_id in uncertain:
        return False, STATUS_UNKNOWN_DELIVERY_STATE
    if occurrence_expired(occurrence, now):
        return False, STATUS_SKIPPED_EXPIRED

    entry = ledger.entry_for(occurrence)
    if not entry:
        return True, "new"

    status = str(entry.get("status", ""))
    if status == STATUS_SUCCESS:
        return False, "duplicate_success"
    if status == STATUS_SKIPPED_EXPIRED:
        return False, STATUS_SKIPPED_EXPIRED
    if status == STATUS_UNKNOWN_DELIVERY_STATE:
        return False, STATUS_UNKNOWN_DELIVERY_STATE
    if status == STATUS_PARTIAL_DELIVERY:
        return False, STATUS_PARTIAL_DELIVERY
    if status == STATUS_SUPPRESSED_COLLISION:
        return False, STATUS_SUPPRESSED_COLLISION

    attempt_count = int(entry.get("attempt_count", 0) or 0)
    if attempt_count >= max_attempts:
        return False, "retry_limit_reached"

    if status == STATUS_RUNNING:
        started_at = parse_optional_datetime(entry.get("started_at"))
        if started_at is not None and ensure_aware(now) - started_at < timedelta(minutes=STALE_RUNNING_MINUTES):
            return False, "running_not_stale"
        return True, "stale_running_retry"

    if status == STATUS_FAILED:
        return True, "failed_retry"

    return True, "retryable_status"


def arbitrate_occurrences(occurrences: list[ScheduledOccurrence], now: datetime) -> list[ArbitrationDecision]:
    if not occurrences:
        return []

    unique = {occurrence.occurrence_id: occurrence for occurrence in occurrences}
    ordered = sorted(unique.values(), key=lambda occurrence: occurrence.scheduled_at)
    groups: list[list[ScheduledOccurrence]] = []
    current_group: list[ScheduledOccurrence] = []
    for occurrence in ordered:
        if not current_group:
            current_group = [occurrence]
            continue
        previous = current_group[-1]
        if abs(occurrence.scheduled_at - previous.scheduled_at) <= timedelta(minutes=COLLISION_WINDOW_MINUTES):
            current_group.append(occurrence)
        else:
            groups.append(current_group)
            current_group = [occurrence]
    if current_group:
        groups.append(current_group)

    decisions: list[ArbitrationDecision] = []
    for group in groups:
        if len(group) == 1:
            decisions.append(ArbitrationDecision(group[0], ACTION_SEND, "single_due_occurrence"))
            continue
        decisions.extend(arbitrate_collision_group(group, now))
    return sorted(decisions, key=lambda decision: decision.occurrence.scheduled_at)


def arbitrate_collision_group(group: list[ScheduledOccurrence], now: datetime) -> list[ArbitrationDecision]:
    winner = select_collision_winner(group, now)
    decisions = [ArbitrationDecision(winner, ACTION_SEND, collision_winner_reason(group, winner, now))]
    for occurrence in group:
        if occurrence.occurrence_id == winner.occurrence_id:
            continue
        reason = collision_reason(occurrence, winner, now)
        if should_defer_collision(occurrence, winner, now):
            decisions.append(
                ArbitrationDecision(
                    occurrence,
                    ACTION_DEFER,
                    reason,
                    suppressed_by_occurrence_id=winner.occurrence_id,
                    defer_until=ensure_aware(now) + timedelta(minutes=DEFER_MINUTES),
                )
            )
        else:
            decisions.append(
                ArbitrationDecision(
                    occurrence,
                    ACTION_SUPPRESS,
                    reason,
                    suppressed_by_occurrence_id=winner.occurrence_id,
                )
            )
    return decisions


def select_collision_winner(group: list[ScheduledOccurrence], now: datetime) -> ScheduledOccurrence:
    candidates = list(group)
    normal_candidates = [occurrence for occurrence in candidates if occurrence_is_normal(occurrence, now)]
    if normal_candidates:
        candidates = normal_candidates

    current_day_candidates = [
        occurrence for occurrence in candidates if occurrence_is_current_local_day(occurrence, now)
    ]
    if current_day_candidates:
        candidates = current_day_candidates

    if all(occurrence_is_normal(occurrence, now) for occurrence in candidates):
        return max(
            candidates,
            key=lambda occurrence: (
                TASK_PRIORITY[FionaBriefKind(occurrence.brief_name)],
                -occurrence_age_minutes(occurrence, now),
                occurrence.scheduled_at,
            ),
        )
    return max(
        candidates,
        key=lambda occurrence: (
            -occurrence_age_minutes(occurrence, now),
            TASK_PRIORITY[FionaBriefKind(occurrence.brief_name)],
            occurrence.scheduled_at,
        ),
    )


def should_defer_collision(occurrence: ScheduledOccurrence, winner: ScheduledOccurrence, now: datetime) -> bool:
    # Collision losers are terminally suppressed. Deferral can create a second
    # notification burst after the winner has already been delivered.
    return False


def occurrence_is_normal(occurrence: ScheduledOccurrence, now: datetime) -> bool:
    return occurrence_age_minutes(occurrence, now) <= FRESH_OCCURRENCE_MINUTES


def occurrence_is_current_local_day(occurrence: ScheduledOccurrence, now: datetime) -> bool:
    current = to_timezone(now, occurrence.scheduled_at.tzinfo)
    scheduled = occurrence.scheduled_at.astimezone(current.tzinfo)
    return scheduled.date() == current.date()


def collision_winner_reason(
    group: list[ScheduledOccurrence],
    winner: ScheduledOccurrence,
    now: datetime,
) -> str:
    if occurrence_is_normal(winner, now) and any(
        not occurrence_is_normal(candidate, now) for candidate in group
    ):
        rule = "normal_over_catch_up"
    elif occurrence_is_current_local_day(winner, now) and any(
        not occurrence_is_current_local_day(candidate, now) for candidate in group
    ):
        rule = "current_day_over_previous_day"
    elif any(
        occurrence_age_minutes(winner, now) < occurrence_age_minutes(candidate, now)
        for candidate in group
        if candidate.occurrence_id != winner.occurrence_id
    ):
        rule = "freshness_before_static_priority"
    else:
        rule = "semantic_priority"
    return (
        f"{rule}; winner={winner.brief_name}; "
        f"winner_age={occurrence_age_minutes(winner, now):.0f}m"
    )


def collision_reason(occurrence: ScheduledOccurrence, winner: ScheduledOccurrence, now: datetime) -> str:
    return (
        f"collision_with_{winner.brief_name}; "
        f"candidate_class={'normal' if occurrence_is_normal(occurrence, now) else 'catch_up'}; "
        f"winner_class={'normal' if occurrence_is_normal(winner, now) else 'catch_up'}; "
        f"candidate_age={occurrence_age_minutes(occurrence, now):.0f}m; "
        f"winner_age={occurrence_age_minutes(winner, now):.0f}m"
    )


def occurrence_age_minutes(occurrence: ScheduledOccurrence, now: datetime) -> float:
    current = to_timezone(now, occurrence.scheduled_at.tzinfo)
    return max(0.0, (current - occurrence.scheduled_at).total_seconds() / 60)


def write_uncertain_delivery_journal(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def remember_uncertain_occurrence(occurrence_id: str) -> None:
    KNOWN_UNCERTAIN_OCCURRENCES.add(occurrence_id)


def clear_uncertain_occurrences() -> None:
    KNOWN_UNCERTAIN_OCCURRENCES.clear()


def delivery_succeeded(status: dict[str, Any], send: bool) -> bool:
    return delivery_status(status, send) == "success"


def delivery_status(status: dict[str, Any], send: bool) -> str:
    if not status.get("ok"):
        return "failed"
    if not send:
        return "success"
    brief_push = status.get("brief_push")
    if not isinstance(brief_push, dict):
        return "failed"
    explicit = str(brief_push.get("delivery_status", "")).strip()
    if explicit in {"success", STATUS_PARTIAL_DELIVERY, "failed"}:
        return explicit
    message_ids = brief_push.get("message_ids") if isinstance(brief_push.get("message_ids"), list) else []
    errors = brief_push.get("errors") if isinstance(brief_push.get("errors"), list) else []
    if brief_push.get("ok") and message_ids and not errors:
        return "success"
    if message_ids and errors:
        return STATUS_PARTIAL_DELIVERY
    return "failed"


def delivery_error_summary(status: dict[str, Any], send: bool) -> str:
    if status.get("errors"):
        return "; ".join(str(item) for item in status.get("errors", []))
    if send:
        brief_push = status.get("brief_push")
        if isinstance(brief_push, dict) and brief_push.get("errors"):
            return "; ".join(str(item) for item in brief_push.get("errors", []))
        return "telegram_delivery_not_confirmed"
    return "runtime_status_not_ok"


def occurrence_id_for(kind: FionaBriefKind, scheduled_at: datetime) -> str:
    local = ensure_aware(scheduled_at)
    return f"{kind.value}:{local.isoformat(timespec='seconds')}"


def combine_local(local_date: date, local_time: time, timezone_name: str) -> datetime:
    return datetime.combine(local_date, local_time, tzinfo=ZoneInfo(timezone_name))


def to_timezone(value: datetime, timezone_name: str | timezone | ZoneInfo) -> datetime:
    tz = ZoneInfo(timezone_name) if isinstance(timezone_name, str) else timezone_name
    aware = ensure_aware(value)
    return aware.astimezone(tz)


def ensure_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def parse_optional_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError:
        return None
    return ensure_aware(parsed)


def isoformat(value: datetime) -> str:
    return ensure_aware(value).isoformat(timespec="seconds")


def truncate_error(value: str, limit: int = 500) -> str:
    text = str(value).replace("\n", " ").strip()
    return text[:limit]
