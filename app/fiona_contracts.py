from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


SCHEMA_VERSION = "2.0"


class VerificationStatus(str, Enum):
    CONFIRMED = "Confirmed"
    PROBABLE = "Probable"
    DEVELOPING = "Developing"
    UNVERIFIED = "Unverified"
    CONFLICTING = "Conflicting"
    FALSE = "False"
    STALE = "Stale"
    MANIPULATED = "Manipulated"


class SourceType(str, Enum):
    PRIMARY = "Primary"
    OFFICIAL = "Official"
    AUTHORITATIVE = "Authoritative"
    MAJOR_MEDIA = "MajorMedia"
    SPECIALIST = "Specialist"
    MARKET_DATA = "MarketData"
    SOCIAL = "Social"
    ANONYMOUS = "Anonymous"
    UNKNOWN = "Unknown"


class EpistemicType(str, Enum):
    FACT = "Fact"
    INFERENCE = "Inference"
    HYPOTHESIS = "Hypothesis"
    SCENARIO = "Scenario"
    OPINION = "Opinion"


class ScoreStatus(str, Enum):
    SUPPORTED = "supported"
    HEURISTIC = "heuristic"
    INSUFFICIENT_DATA = "insufficient_data"
    UNAVAILABLE = "unavailable"


class Route(str, Enum):
    IGNORE = "Ignore"
    STORE_ONLY = "Store Only"
    WATCH = "Watch"
    MARKET_NEWS = "Market News"
    MORNING = "Morning"
    EVENING = "Evening"
    DAILY = "Daily"
    WEEKLY = "Weekly"
    ALERT = "Alert"


class AlertType(str, Enum):
    INFORMATION = "Information"
    MARKET_ANOMALY = "MarketAnomaly"


class AlertStatus(str, Enum):
    DEVELOPING = "Developing"
    CONFIRMED = "Confirmed"
    UPDATED = "Updated"
    RESOLVED = "Resolved"
    RETRACTED = "Retracted"


class CauseStatus(str, Enum):
    KNOWN = "Known"
    PROBABLE = "Probable"
    UNKNOWN = "Unknown"
    CONFLICTING = "Conflicting"


class PersistenceClass(str, Enum):
    EPHEMERAL = "EPHEMERAL"
    LOCAL_DURABLE = "LOCAL_DURABLE"
    EXTERNAL_DURABLE = "EXTERNAL_DURABLE"


class TagType(str, Enum):
    MARKET = "Market"
    NARRATIVE = "Narrative"
    ASSET = "Asset"
    INSTITUTION = "Institution"
    PERSON = "Person"
    CONCEPT = "Concept"
    RISK = "Risk"
    EVENT = "Event"
    POLICY = "Policy"
    GEOGRAPHY = "Geography"


@dataclass(frozen=True)
class EvidenceRecord:
    source_id: str
    source_name: str
    source_type: SourceType = SourceType.UNKNOWN
    source_identity: str = ""
    independence_group: str = ""
    url: str | None = None
    claim: str = ""
    epistemic_type: EpistemicType = EpistemicType.FACT
    observed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if self.observed_at.tzinfo is None:
            object.__setattr__(self, "observed_at", self.observed_at.replace(tzinfo=timezone.utc))
        if not self.source_identity:
            object.__setattr__(self, "source_identity", canonical_source_identity(self.source_name or self.source_id))
        if not self.independence_group:
            object.__setattr__(self, "independence_group", self.source_identity)


@dataclass(frozen=True)
class VerificationDecision:
    status: VerificationStatus
    rule: str
    reason: str
    source_count: int
    independent_source_count: int
    evidence_source_ids: list[str] = field(default_factory=list)


def decide_verification(evidence: list[EvidenceRecord]) -> VerificationDecision:
    source_count = len(evidence)
    independent = independent_evidence(evidence)
    independent_count = len(independent)
    evidence_ids = [record.source_id for record in evidence]

    if independent_count >= 3:
        return VerificationDecision(
            status=VerificationStatus.CONFIRMED,
            rule="Confirmed Fact Rule A",
            reason="At least three independent sources support the claim.",
            source_count=source_count,
            independent_source_count=independent_count,
            evidence_source_ids=evidence_ids,
        )

    primary = [record for record in independent if record.source_type == SourceType.PRIMARY]
    supporting = [
        record
        for record in independent
        if record.source_type in {SourceType.AUTHORITATIVE, SourceType.OFFICIAL}
        and all(record.independence_group != item.independence_group for item in primary)
    ]
    if primary and supporting:
        return VerificationDecision(
            status=VerificationStatus.CONFIRMED,
            rule="Confirmed Fact Rule B",
            reason="One primary source and one independent authoritative supporting source support the claim.",
            source_count=source_count,
            independent_source_count=independent_count,
            evidence_source_ids=evidence_ids,
        )

    if independent_count >= 2:
        return VerificationDecision(
            status=VerificationStatus.PROBABLE,
            rule="Probable",
            reason="Multiple independent sources exist, but confirmed fact rules are not satisfied.",
            source_count=source_count,
            independent_source_count=independent_count,
            evidence_source_ids=evidence_ids,
        )

    return VerificationDecision(
        status=VerificationStatus.UNVERIFIED,
        rule="Insufficient Sources",
        reason="Confirmed fact rules are not satisfied. Duplicate syndication does not count as independent evidence.",
        source_count=source_count,
        independent_source_count=independent_count,
        evidence_source_ids=evidence_ids,
    )


def independent_evidence(evidence: list[EvidenceRecord]) -> list[EvidenceRecord]:
    seen: set[str] = set()
    output: list[EvidenceRecord] = []
    for record in evidence:
        key = record.independence_group or record.source_identity or record.source_id
        if key in seen:
            continue
        seen.add(key)
        output.append(record)
    return output


@dataclass(frozen=True)
class ScoreRecord:
    value: int | None = None
    status: ScoreStatus = ScoreStatus.UNAVAILABLE
    evidence: list[str] = field(default_factory=list)
    data_support: str = ""
    calculation_method: str = ""
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if self.updated_at.tzinfo is None:
            object.__setattr__(self, "updated_at", self.updated_at.replace(tzinfo=timezone.utc))
        if self.status in {ScoreStatus.INSUFFICIENT_DATA, ScoreStatus.UNAVAILABLE}:
            object.__setattr__(self, "value", None)
        if self.value is not None and not 0 <= self.value <= 100:
            raise ValueError("ScoreRecord.value must be between 0 and 100 when provided.")


@dataclass(frozen=True)
class RouteDecision:
    route: Route
    reason: str
    confidence: int
    decided_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if self.decided_at.tzinfo is None:
            object.__setattr__(self, "decided_at", self.decided_at.replace(tzinfo=timezone.utc))
        if not 0 <= self.confidence <= 100:
            raise ValueError("RouteDecision.confidence must be between 0 and 100.")


@dataclass(frozen=True)
class FionaTag:
    canonical_id: str
    display_name: str
    tag_type: TagType
    aliases: tuple[str, ...] = ()
    telegram_hashtag: str = ""

    def __post_init__(self) -> None:
        canonical = normalize_canonical_id(self.canonical_id or self.display_name, self.tag_type)
        object.__setattr__(self, "canonical_id", canonical)
        if not self.telegram_hashtag:
            object.__setattr__(self, "telegram_hashtag", normalize_telegram_hashtag(canonical))
        else:
            object.__setattr__(self, "telegram_hashtag", normalize_telegram_hashtag(self.telegram_hashtag))


@dataclass(frozen=True)
class AlertContract:
    alert_type: AlertType
    status: AlertStatus = AlertStatus.DEVELOPING
    cause_status: CauseStatus = CauseStatus.UNKNOWN
    verification_status: VerificationStatus = VerificationStatus.UNVERIFIED
    risk_level: int | None = None
    impact_scope: tuple[str, ...] = ()
    lifecycle_status: str = ""
    price_regime: str = ""
    flow_direction: str = ""
    official_response: str = ""


MATERIAL_CHANGE_FIELDS = {
    "verification_status": "verification change",
    "risk_level": "risk level change",
    "impact_scope": "impact expansion",
    "cause_status": "cause confirmation",
    "price_regime": "price regime change",
    "flow_direction": "flow reversal",
    "official_response": "official response",
    "lifecycle_status": "lifecycle change",
}


def classify_material_changes(previous: AlertContract, current: AlertContract) -> list[str]:
    changes: list[str] = []
    for field_name, label in MATERIAL_CHANGE_FIELDS.items():
        old = getattr(previous, field_name)
        new = getattr(current, field_name)
        if field_name == "impact_scope":
            old_set = set(old)
            new_set = set(new)
            if not old_set.issuperset(new_set) and new_set != old_set:
                changes.append(label)
        elif old != new:
            changes.append(label)
    if previous.cause_status != CauseStatus.CONFLICTING and current.cause_status == CauseStatus.CONFLICTING:
        changes.append("cause invalidation")
    if len(set(current.impact_scope)) > len(set(previous.impact_scope)) and len(set(current.impact_scope)) >= 2:
        changes.append("cross-market contagion")
    return unique(changes)


@dataclass(frozen=True)
class MemoryPersistenceContract:
    memory_type: str
    persistence_class: PersistenceClass
    storage: str
    railway_redeploy_safe: bool
    notes: str = ""


def railway_json_memory_contract(memory_type: str = "Event History") -> MemoryPersistenceContract:
    return MemoryPersistenceContract(
        memory_type=memory_type,
        persistence_class=PersistenceClass.EPHEMERAL,
        storage="Railway container filesystem JSON",
        railway_redeploy_safe=False,
        notes="Railway container file memory must not be described as durable memory.",
    )


@dataclass(frozen=True)
class FionaEventV2Contract:
    event_id: str
    title: str
    event_type: str
    detected_at: datetime
    schema_version: str = SCHEMA_VERSION
    occurred_at: datetime | None = None
    verification_status: VerificationStatus = VerificationStatus.UNVERIFIED
    sources: list[EvidenceRecord] = field(default_factory=list)
    source_count: int = 0
    entities: list[str] = field(default_factory=list)
    assets: list[str] = field(default_factory=list)
    markets: list[str] = field(default_factory=list)
    tags: list[FionaTag] = field(default_factory=list)
    importance_score: ScoreRecord = field(default_factory=ScoreRecord)
    confidence_score: ScoreRecord = field(default_factory=ScoreRecord)
    urgency_score: ScoreRecord = field(default_factory=ScoreRecord)
    impact_score: ScoreRecord = field(default_factory=ScoreRecord)
    novelty_score: ScoreRecord = field(default_factory=ScoreRecord)
    persistence_score: ScoreRecord = field(default_factory=ScoreRecord)
    cross_market_score: ScoreRecord = field(default_factory=ScoreRecord)
    narrative_score: ScoreRecord = field(default_factory=ScoreRecord)
    risk_score: ScoreRecord = field(default_factory=ScoreRecord)
    lifecycle_status: str | None = None
    routes: list[RouteDecision] = field(default_factory=list)
    parent_event_id: str | None = None

    def __post_init__(self) -> None:
        if self.detected_at.tzinfo is None:
            object.__setattr__(self, "detected_at", self.detected_at.replace(tzinfo=timezone.utc))
        if self.occurred_at is not None and self.occurred_at.tzinfo is None:
            object.__setattr__(self, "occurred_at", self.occurred_at.replace(tzinfo=timezone.utc))
        if self.source_count == 0 and self.sources:
            object.__setattr__(self, "source_count", len(self.sources))

    @classmethod
    def from_v1_event(cls, event: Any) -> FionaEventV2Contract:
        detected_at = getattr(event, "created_at")
        evidence_source = EvidenceRecord(
            source_id=str(getattr(event, "source", "unknown") or "unknown"),
            source_name=str(getattr(event, "source", "unknown") or "unknown"),
            source_type=SourceType.UNKNOWN,
            claim=str(getattr(event, "what_happened", "")),
            observed_at=detected_at,
        )
        return cls(
            event_id=str(getattr(event, "event_id")),
            title=str(getattr(event, "title")),
            event_type=str(getattr(getattr(event, "category"), "value", getattr(event, "category", ""))),
            detected_at=detected_at,
            occurred_at=detected_at,
            sources=[evidence_source],
            entities=[],
            assets=list(getattr(event, "affected_assets", []) or []),
            markets=[],
            confidence_score=ScoreRecord(
                value=int(getattr(event, "confidence_score", 0) or 0) * 10,
                status=ScoreStatus.HEURISTIC,
                evidence=list(getattr(event, "evidence", []) or []),
                data_support="V1 event confidence is heuristic.",
                calculation_method="v1_confidence_score * 10",
                updated_at=detected_at,
            ),
            urgency_score=ScoreRecord(
                value=int(getattr(event, "urgency_score", 0) or 0) * 10,
                status=ScoreStatus.HEURISTIC,
                evidence=list(getattr(event, "evidence", []) or []),
                data_support="V1 urgency is heuristic.",
                calculation_method="v1_urgency_score * 10",
                updated_at=detected_at,
            ),
            impact_score=ScoreRecord(
                value=int(getattr(event, "impact_score", 0) or 0) * 10,
                status=ScoreStatus.HEURISTIC,
                evidence=list(getattr(event, "evidence", []) or []),
                data_support="V1 impact is heuristic.",
                calculation_method="v1_impact_score * 10",
                updated_at=detected_at,
            ),
            lifecycle_status=str(getattr(getattr(event, "lifecycle_status", ""), "value", getattr(event, "lifecycle_status", ""))) or None,
        )


def canonical_source_identity(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return normalized or "unknown"


def normalize_canonical_id(value: str, tag_type: TagType) -> str:
    base = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]+", "_", value.strip()).strip("_").lower()
    prefix = tag_type.value.lower()
    if not base:
        base = prefix
    if not base.startswith(f"{prefix}_"):
        base = f"{prefix}_{base}"
    return base


def normalize_telegram_hashtag(value: str) -> str:
    raw = value.strip().lstrip("#")
    raw = re.sub(r"[^A-Za-z0-9_]+", "_", raw)
    raw = re.sub(r"_+", "_", raw).strip("_")
    if not raw:
        raw = "Fiona"
    if raw[0].isdigit():
        raw = f"Fiona_{raw}"
    return f"#{raw[:64]}"


def unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        output.append(value)
    return output
