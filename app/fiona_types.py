from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class EventCategory(str, Enum):
    PRICE = "price"
    ETF = "etf"
    MACRO = "macro"
    INSTITUTION = "institution"
    RISK = "risk"
    RWA = "rwa"
    ONCHAIN = "onchain"
    REGULATION = "regulation"
    OTHER = "other"


class MarketDirection(str, Enum):
    BULLISH = "Bullish"
    NEUTRAL = "Neutral"
    BEARISH = "Bearish"


class AlertLevel(str, Enum):
    S = "S"
    A = "A"
    B = "B"


class LifecycleStatus(str, Enum):
    NEW = "NEW"
    ONGOING = "ONGOING"
    RESOLVED = "RESOLVED"


class PushDecision(str, Enum):
    SEND_NOW = "send_now"
    BRIEF_POOL = "brief_pool"
    SUPPRESS_DUPLICATE = "suppress_duplicate"


class NarrativeStatus(str, Enum):
    CURRENT = "Current Narrative"
    EMERGING = "Emerging Narrative"
    WATCHLIST = "Watchlist Narrative"
    FADING = "Fading Narrative"
    FALSE = "False Narrative"


@dataclass(frozen=True)
class IntelligenceComponents:
    impact_weight: int = 0
    time_horizon_weight: int = 0
    narrative_weight: int = 0
    cross_market_weight: int = 0
    novelty_weight: int = 0
    decision_value_weight: int = 0
    confidence_adjustment: int = 0
    noise_penalty: int = 0
    repetition_penalty: int = 0

    def to_dict(self) -> dict[str, int]:
        return {
            "impact_weight": self.impact_weight,
            "time_horizon_weight": self.time_horizon_weight,
            "narrative_weight": self.narrative_weight,
            "cross_market_weight": self.cross_market_weight,
            "novelty_weight": self.novelty_weight,
            "decision_value_weight": self.decision_value_weight,
            "confidence_adjustment": self.confidence_adjustment,
            "noise_penalty": self.noise_penalty,
            "repetition_penalty": self.repetition_penalty,
        }


@dataclass
class FionaEvent:
    event_id: str
    created_at: datetime
    source: str
    category: EventCategory
    title: str
    what_happened: str
    why_important: str
    affected_assets: list[str]
    watch_next: list[str]
    fiona_view: str
    raw_data: dict[str, Any] = field(default_factory=dict)
    impact_score: int = 1
    urgency_score: int = 1
    confidence_score: int = 1
    intelligence_score: int = 1
    conviction_score: int = 0
    market_direction: MarketDirection = MarketDirection.NEUTRAL
    level: AlertLevel = AlertLevel.B
    lifecycle_status: LifecycleStatus = LifecycleStatus.NEW
    push_decision: PushDecision = PushDecision.BRIEF_POOL
    event_family_id: str = ""
    dedupe_key: str = ""
    cooldown_minutes: int = 60
    evidence: list[str] = field(default_factory=list)
    intelligence_components: IntelligenceComponents = field(default_factory=IntelligenceComponents)

    def __post_init__(self) -> None:
        if self.created_at.tzinfo is None:
            self.created_at = self.created_at.replace(tzinfo=timezone.utc)
        if not self.event_family_id:
            self.event_family_id = self.default_family_id()
        if not self.dedupe_key:
            self.dedupe_key = self.default_dedupe_key()

    def default_family_id(self) -> str:
        assets = ",".join(sorted(asset.upper() for asset in self.affected_assets)) or "market"
        return f"{self.category.value}:{assets}:{self.title.lower()[:64]}"

    def default_dedupe_key(self) -> str:
        assets = ",".join(sorted(asset.upper() for asset in self.affected_assets)) or "market"
        return f"{self.category.value}:{assets}:{self.market_direction.value}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "created_at": self.created_at.astimezone(timezone.utc).isoformat(),
            "source": self.source,
            "category": self.category.value,
            "title": self.title,
            "what_happened": self.what_happened,
            "why_important": self.why_important,
            "affected_assets": self.affected_assets,
            "watch_next": self.watch_next,
            "fiona_view": self.fiona_view,
            "raw_data": self.raw_data,
            "impact_score": self.impact_score,
            "urgency_score": self.urgency_score,
            "confidence_score": self.confidence_score,
            "intelligence_score": self.intelligence_score,
            "conviction_score": self.conviction_score,
            "market_direction": self.market_direction.value,
            "level": self.level.value,
            "lifecycle_status": self.lifecycle_status.value,
            "push_decision": self.push_decision.value,
            "event_family_id": self.event_family_id,
            "dedupe_key": self.dedupe_key,
            "cooldown_minutes": self.cooldown_minutes,
            "evidence": self.evidence,
            "intelligence_components": self.intelligence_components.to_dict(),
        }


@dataclass
class EventMemoryRecord:
    event_family_id: str
    first_seen_at: datetime
    last_seen_at: datetime
    last_event_id: str
    last_level: AlertLevel
    last_intelligence_score: int
    lifecycle_status: LifecycleStatus
    update_count: int = 1
    last_pushed_at: datetime | None = None
    resolved_at: datetime | None = None
    evidence_seen: set[str] = field(default_factory=set)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_family_id": self.event_family_id,
            "first_seen_at": self.first_seen_at.astimezone(timezone.utc).isoformat(),
            "last_seen_at": self.last_seen_at.astimezone(timezone.utc).isoformat(),
            "last_event_id": self.last_event_id,
            "last_level": self.last_level.value,
            "last_intelligence_score": self.last_intelligence_score,
            "lifecycle_status": self.lifecycle_status.value,
            "update_count": self.update_count,
            "last_pushed_at": self.last_pushed_at.astimezone(timezone.utc).isoformat() if self.last_pushed_at else None,
            "resolved_at": self.resolved_at.astimezone(timezone.utc).isoformat() if self.resolved_at else None,
            "evidence_seen": sorted(self.evidence_seen),
        }


@dataclass
class NarrativeRecord:
    narrative_id: str
    name: str
    category: str
    assets: list[str]
    keywords: list[str]
    first_seen_at: datetime
    last_seen_at: datetime
    mention_count: int = 0
    source_count: int = 0
    event_count: int = 0
    avg_intelligence_score: float = 0
    momentum_score: int = 0
    confidence_score: int = 0
    narrative_score: int = 0
    funds_score: int = 50
    persistence_score: int = 0
    cross_market_score: int = 0
    direction: MarketDirection = MarketDirection.NEUTRAL
    status: NarrativeStatus = NarrativeStatus.WATCHLIST
    summary: str = ""
    false_reasons: list[str] = field(default_factory=list)
    event_ids: list[str] = field(default_factory=list)
    sources: set[str] = field(default_factory=set)

    def to_dict(self) -> dict[str, Any]:
        return {
            "narrative_id": self.narrative_id,
            "name": self.name,
            "category": self.category,
            "assets": self.assets,
            "keywords": self.keywords,
            "first_seen_at": self.first_seen_at.astimezone(timezone.utc).isoformat(),
            "last_seen_at": self.last_seen_at.astimezone(timezone.utc).isoformat(),
            "mention_count": self.mention_count,
            "source_count": self.source_count,
            "event_count": self.event_count,
            "avg_intelligence_score": round(self.avg_intelligence_score, 2),
            "momentum_score": self.momentum_score,
            "confidence_score": self.confidence_score,
            "narrative_score": self.narrative_score,
            "funds_score": self.funds_score,
            "persistence_score": self.persistence_score,
            "cross_market_score": self.cross_market_score,
            "direction": self.direction.value,
            "status": self.status.value,
            "summary": self.summary,
            "false_reasons": self.false_reasons,
            "event_ids": self.event_ids,
            "sources": sorted(self.sources),
        }
