from __future__ import annotations

from datetime import datetime, timedelta

from app.fiona_classifier import decide_push, is_level_upgrade
from app.fiona_types import AlertLevel, EventMemoryRecord, FionaEvent, LifecycleStatus, PushDecision


class LifecycleManager:
    def __init__(self, records: dict[str, EventMemoryRecord] | None = None) -> None:
        self.records: dict[str, EventMemoryRecord] = records or {}

    def apply(self, event: FionaEvent, now: datetime | None = None) -> FionaEvent:
        current_time = now or event.created_at
        previous = self.records.get(event.event_family_id)
        if previous is None:
            event.lifecycle_status = LifecycleStatus.NEW
            event.push_decision = decide_push(event, cooling=False, upgraded=True)
            self.records[event.event_family_id] = self.create_record(event, current_time)
            return event

        upgraded = self.is_upgrade(event, previous)
        resolved = self.is_resolved(event)
        if resolved:
            event.lifecycle_status = LifecycleStatus.RESOLVED
        elif upgraded:
            event.lifecycle_status = LifecycleStatus.NEW
        else:
            event.lifecycle_status = LifecycleStatus.ONGOING

        cooling = self.in_cooldown(event, previous, current_time)
        event.push_decision = decide_push(event, cooling=cooling, upgraded=upgraded)
        if event.lifecycle_status == LifecycleStatus.RESOLVED and previous.last_level == AlertLevel.S:
            event.push_decision = PushDecision.SEND_NOW
        self.update_record(event, previous, current_time)
        return event

    def mark_pushed(self, event: FionaEvent, pushed_at: datetime | None = None) -> None:
        record = self.records.get(event.event_family_id)
        if record is None:
            return
        record.last_pushed_at = pushed_at or event.created_at

    def create_record(self, event: FionaEvent, now: datetime) -> EventMemoryRecord:
        return EventMemoryRecord(
            event_family_id=event.event_family_id,
            first_seen_at=now,
            last_seen_at=now,
            last_event_id=event.event_id,
            last_level=event.level,
            last_intelligence_score=event.intelligence_score,
            lifecycle_status=event.lifecycle_status,
            update_count=1,
            last_pushed_at=now if event.push_decision == PushDecision.SEND_NOW else None,
            resolved_at=now if event.lifecycle_status == LifecycleStatus.RESOLVED else None,
            evidence_seen=set(event.evidence),
        )

    def update_record(self, event: FionaEvent, record: EventMemoryRecord, now: datetime) -> None:
        record.last_seen_at = now
        record.last_event_id = event.event_id
        record.last_level = event.level
        record.last_intelligence_score = event.intelligence_score
        record.lifecycle_status = event.lifecycle_status
        record.update_count += 1
        record.evidence_seen.update(event.evidence)
        if event.lifecycle_status == LifecycleStatus.RESOLVED:
            record.resolved_at = now
        if event.push_decision == PushDecision.SEND_NOW:
            record.last_pushed_at = now

    def is_upgrade(self, event: FionaEvent, previous: EventMemoryRecord) -> bool:
        if event.intelligence_score - previous.last_intelligence_score >= 15:
            return True
        if is_level_upgrade(previous.last_level, event.level):
            return True
        new_evidence = set(event.evidence) - previous.evidence_seen
        return bool(new_evidence and event.intelligence_score >= 60)

    def is_resolved(self, event: FionaEvent) -> bool:
        if bool(event.raw_data.get("resolved")):
            return True
        if any(str(item).lower() in {"resolved", "recovered", "support_reclaimed"} for item in event.evidence):
            return True
        return False

    def in_cooldown(self, event: FionaEvent, previous: EventMemoryRecord, now: datetime) -> bool:
        if previous.last_pushed_at is None:
            return False
        return now - previous.last_pushed_at < timedelta(minutes=max(0, event.cooldown_minutes))
