"""Resolve Market News selection once, before presentation; never perform delivery."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable

from app.fiona_global_coverage import CoverageEvaluation, EventCluster, MATERIALITY_FLOOR, SourceHealthStatus
from app.fiona_source_registry import CoverageProfile
from app.fiona_types import EventCategory, FionaEvent


@dataclass(frozen=True)
class CoverageAuthority:
    configured_profile: CoverageProfile
    selection_authority: str
    shadow: dict[str, Any]
    clusters: tuple[EventCluster, ...] = ()
    fallback_used: bool = False
    fallback_reason: str | None = None

    def metrics(self) -> dict[str, Any]:
        return {
            "configured_coverage_profile": self.configured_profile.value,
            "selection_authority": self.selection_authority,
            "coverage_selection_authority": self.selection_authority,
            "coverage_fallback_used": self.fallback_used,
            "coverage_fallback_reason": self.fallback_reason,
            "selected_cluster_count": len(self.clusters),
        }


def resolve_coverage_authority(profile: CoverageProfile, evaluate: Callable[..., dict[str, Any]],
                               **kwargs: Any) -> CoverageAuthority:
    captured: list[CoverageEvaluation] = []
    try:
        shadow = evaluate(selection_sink=captured.append, **kwargs)
        if not isinstance(shadow, dict):
            raise ValueError("invalid_evaluation_result")
    except Exception:
        shadow = {"ok": False, "error_category": "coverage_engine_operational_failure"}
    if profile == CoverageProfile.LEGACY:
        return CoverageAuthority(profile, "legacy", shadow)
    if not shadow.get("ok") or len(captured) != 1:
        return CoverageAuthority(profile, "legacy", shadow, fallback_used=True,
                                 fallback_reason="coverage_engine_operational_failure")
    health = captured[0].source_health
    if health and not any(h.status in {SourceHealthStatus.OK, SourceHealthStatus.EMPTY} for h in health):
        return CoverageAuthority(profile, "legacy", shadow, fallback_used=True,
                                 fallback_reason="all_sources_unavailable")
    try:
        selected = tuple(captured[0].selected_clusters)
        valid = (len({c.cluster_id for c in selected}) == len(selected) and all(
            isinstance(c, EventCluster) and c.events and not c.stale
            and c.materiality >= MATERIALITY_FLOOR and c.freshness_score > 0
            and c.normalized_headline.strip() for c in selected
        ))
    except (AttributeError, TypeError, ValueError):
        valid = False
    # Empty, underweight editions are legitimate editorial outcomes, not failures.
    if not valid:
        return CoverageAuthority(profile, "legacy", shadow, fallback_used=True,
                                 fallback_reason="invalid_authoritative_selection")
    return CoverageAuthority(profile, "global_631", shadow, selected)


def coverage_events(authority: CoverageAuthority, now: datetime) -> list[FionaEvent]:
    """Presentation projection, not another Alert/Lifecycle/Scoring execution."""
    categories = {"macro_policy": EventCategory.MACRO, "regulation": EventCategory.REGULATION,
                  "rwa": EventCategory.RWA, "crypto": EventCategory.OTHER,
                  "market": EventCategory.OTHER}
    output = []
    for cluster in authority.clusters:
        representative = max(cluster.events, key=lambda e: e.materiality)
        provenance = representative.source_provenance
        primary = any(e.source_provenance.source_type in {"Primary", "Official"}
                      for e in cluster.events)
        # Evidence confidence is a conservative heuristic, not fact verification.
        confidence = 8 if primary or cluster.independent_source_count >= 2 else 6
        output.append(FionaEvent(
            event_id=cluster.cluster_id, created_at=now,
            source=", ".join(sorted({e.source_id for e in cluster.events})),
            category=categories.get(cluster.category, EventCategory.OTHER),
            title=cluster.normalized_headline, what_happened=cluster.normalized_headline,
            why_important="The reported development may change policy, liquidity, or market risk conditions; its market impact still requires confirmation.",
            affected_assets=list(representative.entities),
            watch_next=["Confirmation in the primary release and subsequent market reaction"],
            fiona_view="Treat the reported development as evidence to monitor, not a forecast of asset prices.",
            intelligence_score=cluster.materiality, confidence_score=confidence,
            conviction_score=confidence * 10,
            raw_data={"coverage_cluster_id": cluster.cluster_id,
                      "event_region": cluster.event_region.value,
                      "independent_source_count": cluster.independent_source_count,
                      "source_url": provenance.source_url, "source_name": provenance.source_name,
                      "source_language": provenance.original_language,
                      "original_title": provenance.original_title,
                      "original_text": provenance.original_text_snippet},
        ))
    return output
