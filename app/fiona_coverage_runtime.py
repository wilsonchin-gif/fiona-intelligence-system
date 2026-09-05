from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Sequence

from app.fiona_global_coverage import (
    CoverageEvaluation,
    NormalizedCoverageEvent,
    SourceFetcher,
    SourceHealth,
    SourceHealthStatus,
    collect_sources,
    evaluate_global_coverage,
    fetch_source_items,
    normalize_source_item,
)
from app.fiona_source_registry import (
    SourceRegistry,
    coverage_profile_from_env,
    load_source_registry,
    validate_registry,
)
from app.fiona_shadow_audit import selected_event_audits


COVERAGE_STATE_NAME = "fiona_coverage_shadow_history.json"
COVERAGE_STATE_SCHEMA_VERSION = "3.1"
COVERAGE_RETENTION_DAYS = 21


@dataclass
class CoverageObservationStore:
    path: Path
    records: list[dict[str, Any]] = field(default_factory=list)
    load_error: str | None = None

    @classmethod
    def load(cls, path: Path) -> CoverageObservationStore:
        store = cls(path=path)
        if not path.exists():
            return store
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            records = payload.get("records", []) if isinstance(payload, dict) else []
            store.records = [record for record in records if isinstance(record, dict)]
        except (OSError, ValueError, TypeError) as exc:
            store.load_error = type(exc).__name__
        return store

    def record(self, evaluation: CoverageEvaluation, audit: dict[str, Any] | None = None) -> None:
        now = evaluation.evaluated_at.astimezone(timezone.utc)
        cutoff = now - timedelta(days=COVERAGE_RETENTION_DAYS)
        retained = [
            record
            for record in self.records
            if (_record_time(record) or now) >= cutoff
        ]
        retained.append(
            {
                "evaluated_at": now.isoformat(),
                **(audit or {}),
                "metrics": evaluation.metrics,
                "source_health": [health.to_dict() for health in evaluation.source_health],
                "qualified_cluster_members": [
                    sorted({event.event_id for event in cluster.events})
                    for cluster in evaluation.qualified_clusters
                ],
            }
        )
        self.records = retained

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": COVERAGE_STATE_SCHEMA_VERSION,
            "persistence": "ephemeral_on_railway_without_volume",
            "records": self.records,
        }
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self.path)

    def rolling_summary(self, now: datetime, hours: int) -> dict[str, Any]:
        cutoff = now.astimezone(timezone.utc) - timedelta(hours=hours)
        records = [record for record in self.records if (_record_time(record) or cutoff) >= cutoff]
        return aggregate_coverage_records(records, window_hours=hours)

    @property
    def observation_start_at(self) -> str | None:
        times = [value for record in self.records for value in [_record_time(record)] if value is not None]
        return min(times).isoformat() if times else None

    @property
    def cumulative_qualified_clusters(self) -> int:
        groups: list[set[str]] = []
        for record in self.records:
            for members in record.get("qualified_cluster_members", []):
                keys = set(members)
                if not keys:
                    continue
                overlapping = [group for group in groups if group & keys]
                for group in overlapping:
                    keys.update(group)
                    groups.remove(group)
                groups.append(keys)
        return len(groups)


def _record_time(record: dict[str, Any]) -> datetime | None:
    try:
        value = datetime.fromisoformat(str(record.get("evaluated_at", "")).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def aggregate_coverage_records(records: Sequence[dict[str, Any]], *, window_hours: int) -> dict[str, Any]:
    regional = Counter()
    tier = Counter()
    candidates = 0
    qualified = 0
    selected = 0
    material_overrides = 0
    duplicates = 0
    stale = 0
    diversity: list[int] = []
    independence: list[int] = []
    gaps = Counter()
    for record in records:
        metrics = record.get("metrics") or {}
        candidates += int(metrics.get("candidate_events", 0))
        qualified += int(metrics.get("qualified_clusters", 0))
        selected_count = int(metrics.get("selected_shadow_clusters", 0))
        selected += selected_count
        material_overrides += int(metrics.get("material_override_count", 0))
        duplicates += int(metrics.get("duplicate_rejection_count", 0))
        stale += int(metrics.get("stale_rejection_count", 0))
        diversity.append(int(metrics.get("source_diversity", 0)))
        independence.append(int(metrics.get("independent_source_diversity", 0)))
        for key, value in (metrics.get("regional_selected_counts") or {}).items():
            regional[key] += int(value)
        tier_counts = metrics.get("tier_selected_counts") or {}
        for key, value in tier_counts.items():
            tier[str(key)] += int(value)
        for region in metrics.get("underweight_regions", []):
            gaps[str(region)] += 1
    regional_total = sum(regional.values())
    tier_total = sum(tier.values())
    return {
        "window_hours": window_hours,
        "evaluation_count": len(records),
        "candidate_events": candidates,
        "qualified_clusters": qualified,
        "selected_shadow_clusters": selected,
        "regional_selected_share": {
            key: round(value / regional_total, 4) if regional_total else 0.0
            for key, value in sorted(regional.items())
        },
        "tier1_share": round(tier.get("1", 0) / tier_total, 4) if tier_total else 0.0,
        "source_diversity_average": round(sum(diversity) / len(diversity), 2) if diversity else 0.0,
        "independent_source_diversity_average": (
            round(sum(independence) / len(independence), 2) if independence else 0.0
        ),
        "material_override_count": material_overrides,
        "coverage_gap_evaluations": dict(sorted(gaps.items())),
        "duplicate_rejection_count": duplicates,
        "stale_rejection_count": stale,
    }


def normalize_legacy_candidates(
    raw_items: Sequence[dict[str, Any]],
    registry: SourceRegistry,
    *,
    retrieved_at: datetime,
) -> list[NormalizedCoverageEvent]:
    by_name = {source.name: source for source in registry.legacy_sources()}
    events: list[NormalizedCoverageEvent] = []
    for raw in raw_items:
        source_id = str(raw.get("source_id") or "")
        try:
            source = registry.by_id(source_id) if source_id else by_name[str(raw.get("source") or "")]
        except (KeyError, TypeError):
            continue
        event = normalize_source_item(raw, source, retrieved_at=retrieved_at)
        if event is not None:
            events.append(event)
    return events


def _legacy_health(
    events: Sequence[NormalizedCoverageEvent],
    registry: SourceRegistry,
    evaluated_at: datetime,
    failures: dict[str, str],
) -> list[SourceHealth]:
    counts = Counter(event.source_id for event in events)
    invalid = Counter(event.source_id for event in events if event.published_at is None)
    return [
        SourceHealth(
            source_id=source.source_id,
            status=(
                SourceHealthStatus.HTTP_ERROR if source.source_id in failures
                else SourceHealthStatus.OK if counts[source.source_id] else SourceHealthStatus.EMPTY
            ),
            retrieved_at=evaluated_at,
            item_count=counts[source.source_id],
            normalized_count=counts[source.source_id],
            invalid_timestamp_count=invalid[source.source_id],
            error_category=failures.get(source.source_id, "" if counts[source.source_id] else "no_candidate_observed"),
        )
        for source in registry.legacy_sources()
    ]


def run_global_coverage_shadow(
    legacy_items: Sequence[dict[str, Any]],
    *,
    output_dir: Path,
    evaluated_at: datetime,
    logger: Callable[[dict[str, Any]], None] | None = None,
    registry: SourceRegistry | None = None,
    collect_expanded: bool = True,
    fetcher: SourceFetcher = fetch_source_items,
    legacy_failures: dict[str, str] | None = None,
) -> dict[str, Any]:
    source_registry = registry or load_source_registry()
    profile = coverage_profile_from_env(warning_logger=logger)
    legacy_events = normalize_legacy_candidates(
        legacy_items,
        source_registry,
        retrieved_at=evaluated_at,
    )
    expanded_events: list[NormalizedCoverageEvent] = []
    expanded_health: list[SourceHealth] = []
    if collect_expanded:
        expanded_events, expanded_health = collect_sources(
            source_registry.shadow_only_sources(),
            retrieved_at=evaluated_at,
            fetcher=fetcher,
        )
    health = _legacy_health(legacy_events, source_registry, evaluated_at, legacy_failures or {}) + expanded_health
    evaluation = evaluate_global_coverage(
        [*legacy_events, *expanded_events],
        evaluated_at=evaluated_at,
        source_health=health,
    )
    store = CoverageObservationStore.load(output_dir / COVERAGE_STATE_NAME)
    audit = selected_event_audits(evaluation)
    store.record(evaluation, audit)
    store.save()
    result = {
        "ok": True,
        "mode": "coverage_shadow",
        "coverage_profile": profile.value,
        "shadow_profile": "global_631_shadow",
        "selection_authority": "legacy",
        "user_visible_content_changed": False,
        **audit,
        **evaluation.metrics,
        "source_health": [item.to_dict() for item in health],
        "rolling_24h": store.rolling_summary(evaluated_at, 24),
        "rolling_7d": store.rolling_summary(evaluated_at, 24 * 7),
        "observation_start_at": store.observation_start_at,
        "cumulative_qualified_clusters": store.cumulative_qualified_clusters,
        "observation_target_days": 14,
        "observation_target_qualified_clusters": 100,
        "state_persistence": "ephemeral_on_railway_without_volume",
        "telegram_api_calls": 0,
        "scheduler_ledger_mutations": 0,
        "formal_occurrences_created": 0,
    }
    if logger is not None:
        logger({"event": "fionaGlobalCoverageShadow", **result})
    return result


def run_global_coverage_shadow_safe(*args: Any, **kwargs: Any) -> dict[str, Any]:
    logger = kwargs.get("logger")
    try:
        return run_global_coverage_shadow(*args, **kwargs)
    except Exception as exc:  # noqa: BLE001 - Shadow must never affect legacy delivery.
        result = {
            "ok": False,
            "mode": "coverage_shadow",
            "selection_authority": "legacy",
            "user_visible_content_changed": False,
            "error_category": "coverage_shadow_failed",
            "error": type(exc).__name__,
            "telegram_api_calls": 0,
            "scheduler_ledger_mutations": 0,
            "formal_occurrences_created": 0,
        }
        if callable(logger):
            try:
                logger({"event": "fionaGlobalCoverageShadow", **result})
            except Exception:
                pass
        return result


def validate_global_coverage_runtime(
    *,
    registry: SourceRegistry | None = None,
    fetcher: SourceFetcher = fetch_source_items,
    evaluated_at: datetime | None = None,
) -> dict[str, Any]:
    now = evaluated_at or datetime.now(timezone.utc)
    source_registry = registry or load_source_registry()
    registry_result = validate_registry(source_registry)
    events, health = collect_sources(
        source_registry.shadow_sources(),
        retrieved_at=now,
        fetcher=fetcher,
    )
    evaluation = evaluate_global_coverage(events, evaluated_at=now, source_health=health)
    metrics = evaluation.metrics
    result = {
        "ok": bool(registry_result["ok"] and events),
        "mode": "coverage_validation",
        **selected_event_audits(evaluation),
        "coverage_profile": "global_631_shadow",
        "candidate_events": metrics["candidate_events"],
        "qualified_clusters": metrics["qualified_clusters"],
        "regional_distribution": metrics["regional_selected_share"],
        "tier_distribution": {
            "tier1": metrics["tier1_share"],
            "tier2": metrics["tier2_share"],
            "tier3": metrics["tier3_share"],
        },
        "source_diversity": metrics["source_diversity"],
        "independent_source_diversity": metrics["independent_source_diversity"],
        "material_overrides": metrics["material_override_count"],
        "duplicates_rejected": metrics["duplicate_rejection_count"],
        "stale_rejected": metrics["stale_rejection_count"],
        "unknown_region_share": metrics["unknown_region_share"],
        "selected_shadow_clusters": metrics["selected_shadow_clusters"],
        "regional_candidate_counts": metrics["regional_candidate_counts"],
        "regional_gap_reason": metrics["regional_gap_reason"],
        "source_registry": registry_result,
        "source_health": [item.to_dict() for item in health],
        "telegram_api_calls": 0,
        "ledger_mutations": 0,
        "formal_occurrences_created": 0,
        "temporary_files_remaining": 0,
    }
    return result
