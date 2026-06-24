from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.fiona_narrative import NarrativeEngine
from app.fiona_types import AlertLevel, EventMemoryRecord, FionaEvent, LifecycleStatus, MarketDirection, NarrativeRecord, NarrativeStatus


@dataclass
class DecisionMemoryRecord:
    created_at: datetime
    scope: str
    direction: MarketDirection
    conviction_score: int
    reasoning: str
    linked_event_ids: list[str] = field(default_factory=list)
    linked_narrative_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "created_at": self.created_at.astimezone(timezone.utc).isoformat(),
            "scope": self.scope,
            "direction": self.direction.value,
            "conviction_score": self.conviction_score,
            "reasoning": self.reasoning,
            "linked_event_ids": self.linked_event_ids,
            "linked_narrative_ids": self.linked_narrative_ids,
        }


@dataclass
class FionaMemory:
    event_memory: dict[str, EventMemoryRecord] = field(default_factory=dict)
    narrative_memory: dict[str, NarrativeRecord] = field(default_factory=dict)
    decision_memory: list[DecisionMemoryRecord] = field(default_factory=list)

    def update_narratives(self, events: list[FionaEvent], now: datetime | None = None) -> list[NarrativeRecord]:
        records = NarrativeEngine().build(events, now=now)
        for record in records:
            self.narrative_memory[record.narrative_id] = record
        return records

    def remember_decision(self, record: DecisionMemoryRecord) -> None:
        self.decision_memory.append(record)

    def current_narratives(self, limit: int = 3) -> list[NarrativeRecord]:
        return sorted(self.narrative_memory.values(), key=lambda item: item.narrative_score, reverse=True)[:limit]

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_memory": {key: value.to_dict() for key, value in self.event_memory.items()},
            "narrative_memory": {key: value.to_dict() for key, value in self.narrative_memory.items()},
            "decision_memory": [record.to_dict() for record in self.decision_memory],
        }

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> FionaMemory:
        if not path.exists():
            return cls()
        payload = json.loads(path.read_text(encoding="utf-8"))
        event_memory = {
            key: event_memory_from_dict(value)
            for key, value in dict(payload.get("event_memory", {})).items()
            if isinstance(value, dict)
        }
        narrative_memory = {
            key: narrative_memory_from_dict(value)
            for key, value in dict(payload.get("narrative_memory", {})).items()
            if isinstance(value, dict)
        }
        decision_memory = [
            decision_memory_from_dict(value)
            for value in list(payload.get("decision_memory", []))
            if isinstance(value, dict)
        ]
        return cls(event_memory=event_memory, narrative_memory=narrative_memory, decision_memory=decision_memory)


def event_memory_from_dict(value: dict[str, Any]) -> EventMemoryRecord:
    return EventMemoryRecord(
        event_family_id=str(value.get("event_family_id", "")),
        first_seen_at=parse_datetime(value.get("first_seen_at")),
        last_seen_at=parse_datetime(value.get("last_seen_at")),
        last_event_id=str(value.get("last_event_id", "")),
        last_level=AlertLevel(str(value.get("last_level", AlertLevel.B.value))),
        last_intelligence_score=int(value.get("last_intelligence_score", 1) or 1),
        lifecycle_status=LifecycleStatus(str(value.get("lifecycle_status", LifecycleStatus.NEW.value))),
        update_count=int(value.get("update_count", 1) or 1),
        last_pushed_at=parse_optional_datetime(value.get("last_pushed_at")),
        resolved_at=parse_optional_datetime(value.get("resolved_at")),
        evidence_seen=set(value.get("evidence_seen", [])),
    )


def narrative_memory_from_dict(value: dict[str, Any]) -> NarrativeRecord:
    return NarrativeRecord(
        narrative_id=str(value.get("narrative_id", "")),
        name=str(value.get("name", "")),
        category=str(value.get("category", "")),
        assets=list(value.get("assets", [])),
        keywords=list(value.get("keywords", [])),
        first_seen_at=parse_datetime(value.get("first_seen_at")),
        last_seen_at=parse_datetime(value.get("last_seen_at")),
        mention_count=int(value.get("mention_count", 0) or 0),
        source_count=int(value.get("source_count", 0) or 0),
        event_count=int(value.get("event_count", 0) or 0),
        avg_intelligence_score=float(value.get("avg_intelligence_score", 0) or 0),
        momentum_score=int(value.get("momentum_score", 0) or 0),
        confidence_score=int(value.get("confidence_score", 0) or 0),
        narrative_score=int(value.get("narrative_score", 0) or 0),
        funds_score=int(value.get("funds_score", 50) or 50),
        persistence_score=int(value.get("persistence_score", 0) or 0),
        cross_market_score=int(value.get("cross_market_score", 0) or 0),
        direction=MarketDirection(str(value.get("direction", MarketDirection.NEUTRAL.value))),
        status=NarrativeStatus(str(value.get("status", NarrativeStatus.WATCHLIST.value))),
        summary=str(value.get("summary", "")),
        false_reasons=list(value.get("false_reasons", [])),
        event_ids=list(value.get("event_ids", [])),
        sources=set(value.get("sources", [])),
    )


def decision_memory_from_dict(value: dict[str, Any]) -> DecisionMemoryRecord:
    return DecisionMemoryRecord(
        created_at=parse_datetime(value.get("created_at")),
        scope=str(value.get("scope", "")),
        direction=MarketDirection(str(value.get("direction", MarketDirection.NEUTRAL.value))),
        conviction_score=int(value.get("conviction_score", 0) or 0),
        reasoning=str(value.get("reasoning", "")),
        linked_event_ids=list(value.get("linked_event_ids", [])),
        linked_narrative_ids=list(value.get("linked_narrative_ids", [])),
    )


def parse_optional_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    return parse_datetime(value)


def parse_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str) and value:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc)
