"""Bounded, read-only projections of completed Shadow selections."""
from __future__ import annotations

import hashlib
import json
import re
from enum import Enum
from collections import Counter
from typing import Any, Callable

from app.fiona_global_coverage import CoverageEvaluation, REGIONAL_TARGETS, base_ranking_score, eligibility_rejection

MAX_AUDIT_RECORDS = 50
MAX_IDENTITIES = 24
MAX_LOG_SELECTED_RECORDS = 10
MAX_REJECTED_RECORDS = 20
MAX_REJECTED_BYTES = 16000


def safe_contract(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {safe_audit_text(str(k), 64): safe_contract(v) for k, v in list(value.items())[:24]}
    if isinstance(value, (list, tuple)):
        return [safe_contract(v) for v in value[:24]]
    return safe_audit_text(value, 160) if isinstance(value, str) else value


def safe_audit_text(value: str, limit: int = 240) -> str:
    text = re.sub(r"https?://\S+|\b\w+://\S+", "[URL omitted]", str(value))
    text = re.sub(r"\b(?:bot)?\d{7,12}:[A-Za-z0-9_-]{20,}\b", "[redacted]", text)
    text = re.sub(r"\b(?:sk-[A-Za-z0-9_-]{12,}|gh[pousr]_[A-Za-z0-9_]{16,}|github_pat_[A-Za-z0-9_]+|AKIA[A-Z0-9]{16}|eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+)\b", "[redacted]", text)
    text = re.sub(r"(?i)\b(?:[A-Z_]*(?:token|secret|password|api_key|apikey))[\s]*[:=][\s]*(?:\"[^\"]*\"|'[^']*'|\S+)", "[redacted]", text)
    return " ".join(text.split())[:limit]


def selected_event_audits(evaluation: CoverageEvaluation) -> dict[str, Any]:
    selected = evaluation.selected_clusters
    original_ids = [cluster.cluster_id for cluster in selected]
    fingerprint = evaluation.evaluated_at.isoformat() + "|" + "|".join(c.cluster_id for c in selected)
    evaluation_id = "shadow_" + hashlib.sha256(fingerprint.encode()).hexdigest()[:24]
    records = []
    preceding: Counter = Counter()
    for rank, cluster in enumerate(selected[:MAX_AUDIT_RECORDS], 1):
        target = REGIONAL_TARGETS.get(cluster.event_region)
        prior_share = preceding[cluster.event_region] / max(1, rank - 1)
        base = base_ranking_score(cluster)
        adjustment = cluster.ranking_score - base
        signals = ["qualified_quality_floor", "existing_materiality_freshness_cross_market_ranking"]
        if cluster.material_override:
            signals.append("material_event_override")
        elif target is not None and adjustment > 0:
            signals.append("regional_balance_contribution")
        if int(cluster.source_tier) == 1:
            signals.append("tier_1_authority")
        if cluster.independent_source_count > 1:
            signals.append("independent_confirmation")
        sources = sorted({event.source_id for event in cluster.events})
        groups = sorted({event.independence_group for event in cluster.events if event.independence_group})
        records.append({
            "evaluation_id": evaluation_id,
            "evaluated_at": evaluation.evaluated_at.isoformat(),
            "occurrence_id": None,
            "rank": rank,
            "cluster_id": safe_audit_text(cluster.cluster_id, 80),
            "normalized_headline": safe_audit_text(cluster.normalized_headline),
            "event_region": cluster.event_region.value,
            "source_ids": [safe_audit_text(value, 64) for value in sources[:MAX_IDENTITIES]],
            "source_count": cluster.source_count,
            "independent_source_count": cluster.independent_source_count,
            "confirmation_sufficiency": (
                "multi_independent_confirmation" if cluster.independent_source_count >= 2
                else "authoritative_primary_source" if any(
                    event.source_provenance.source_type in {"Primary", "Official"}
                    for event in cluster.events
                ) else "single_secondary_source"
            ),
            "independence_groups": [safe_audit_text(value, 64) for value in groups[:MAX_IDENTITIES]],
            "source_tier": int(cluster.source_tier),
            "source_tiers": sorted({int(event.source_tier) for event in cluster.events}),
            "source_composition": [
                {"source_id": safe_audit_text(source_id, 64),
                 "tiers": sorted({int(event.source_tier) for event in cluster.events if event.source_id == source_id}),
                 "independence_groups": [safe_audit_text(group, 64) for group in sorted({event.independence_group for event in cluster.events if event.source_id == source_id and event.independence_group})[:2]]}
                for source_id in sources[:MAX_IDENTITIES]
            ],
            "identities_truncated": len(sources) > MAX_IDENTITIES or len(groups) > MAX_IDENTITIES,
            "materiality": cluster.materiality,
            "freshness": {"score": cluster.freshness_score, "stale": cluster.stale},
            "material_override": cluster.material_override,
            "override_reason": safe_audit_text(cluster.override_reason) if cluster.material_override else None,
            "selection_reason": signals,
            "score_components": {
                "materiality": cluster.materiality,
                "cross_market_impact": cluster.cross_market_impact,
                "freshness_score": cluster.freshness_score,
                "source_tier": int(cluster.source_tier),
                "independent_source_count": cluster.independent_source_count,
                "narrative_relevance": cluster.narrative_relevance,
                "quality_score": cluster.quality_score,
                "base_ranking_score": base,
                "ranking_score": cluster.ranking_score,
                "selection_adjustment": round(adjustment, 8),
                "adjustment_kind": "material_override" if cluster.material_override else "regional_balance",
            },
            "regional_target_context": {"target_share": target, "selected_before": rank - 1, "region_share_before": prior_share},
            **editorial_audit(cluster),
        })
        preceding[cluster.event_region] += 1
    selected_ids = set(original_ids)
    rejected = sorted((c for c in evaluation.clusters if c.cluster_id not in selected_ids),
                      key=lambda c: (-base_ranking_score(c), c.cluster_id))
    rejections = []
    rejected_bytes = 2
    for cluster in rejected[:MAX_REJECTED_RECORDS]:
        rejection = eligibility_rejection(cluster, evaluation.quality_floor) or ("ranking", "eligible_below_capacity_cutoff")
        record = {"cluster_id": safe_audit_text(cluster.cluster_id, 80),
                           "normalized_headline": safe_audit_text(cluster.normalized_headline, 180),
                           "rejection_stage": rejection[0], "reason": rejection[1],
                           "event_region": cluster.event_region.value, "materiality": cluster.materiality,
                           "evidence_quality": cluster.quality_score,
                           "base_ranking_score": round(base_ranking_score(cluster), 2)}
        cost = len(json.dumps(record, ensure_ascii=False).encode()) + 1
        if rejected_bytes + cost > MAX_REJECTED_BYTES:
            break
        rejections.append(record)
        rejected_bytes += cost
    return {"evaluation_id": evaluation_id, "selected_event_audits": records,
            "rejected_candidate_audits": rejections,
            "rejected_audit_omitted": max(0, len(rejected) - len(rejections)),
            "ranking_changed": original_ids != [cluster.cluster_id for cluster in evaluation.selected_clusters],
            "audit_records_omitted": max(0, len(selected) - MAX_AUDIT_RECORDS)}


def editorial_audit(cluster: Any) -> dict[str, Any]:
    decision = cluster.editorial
    if decision is None:
        return {"editorial_contract_status": "missing"}
    from dataclasses import asdict
    supported = [e for e in cluster.events if e.editorial and e.editorial.relevance.eligible]
    strongest = max(supported or cluster.events, key=lambda e: e.editorial.evidence_quality.value if e.editorial else 0)
    parts = dict(strongest.editorial.evidence_quality.components)
    parts["independent_corroboration"] = min(15, max(0, cluster.independent_source_count - 1) * 8)
    return safe_contract({
        "assertion_type": decision.assertion.assertion_type.value,
        "assertion_decision": asdict(decision.assertion),
        "financial_relevance_class": decision.relevance.relevance_class.value,
        "transmission_channels": decision.relevance.transmission_channels,
        "relevance_reason": decision.relevance.relevance_reason,
        "evidence_quality": {"value": cluster.quality_score, "components": parts,
                             "basis": decision.evidence_quality.evidence_status},
        "geography_decision": asdict(decision.geography),
        "novelty_decision": asdict(cluster.novelty),
        "override_eligibility": {"eligible": cluster.material_override, "reason": decision.override_reason},
        "final_selection_reason": "qualified_material_override" if cluster.material_override else "independent_editorial_gates_then_soft_regional_rank",
        "editorial_memory": decision.memory,
        "event_ids": [event.event_id for event in cluster.events[:MAX_IDENTITIES]],
        "published_at": [event.published_at.isoformat() if event.published_at else None for event in cluster.events[:MAX_IDENTITIES]],
        "category": cluster.category, "event_affected_markets": decision.event_affected_markets,
    })


def emit_occurrence_audits(run_status: dict[str, Any], occurrence_id: str,
                           emit: Callable[..., Any] = print) -> None:
    """Bind the authoritative occurrence only when its existing result is serialized."""
    try:
        shadow = run_status.get("coverage_shadow") or {}
        if shadow.get("evaluation_id"):
            metrics = {key: value for key, value in shadow.items() if key not in {
                "selected_event_audits", "rejected_candidate_audits", "source_health", "rolling_24h", "rolling_7d"
            }}
            emit(json.dumps({"event": "fionaGlobalCoverageShadow", "occurrence_id": occurrence_id,
                             "log_selected_records_omitted": max(0, len(shadow.get("selected_event_audits", []))-MAX_LOG_SELECTED_RECORDS),
                             **metrics, **{key: run_status[key] for key in (
                                 "configured_coverage_profile", "selection_authority",
                                 "coverage_fallback_used", "coverage_fallback_reason",
                                 "selected_cluster_count") if key in run_status}},
                            ensure_ascii=False, separators=(",", ":")), flush=True)
            health = [{key: item.get(key) for key in (
                "source_id", "status", "item_count", "normalized_count", "duration_ms", "error_category"
            )} for item in shadow.get("source_health", [])[:MAX_AUDIT_RECORDS]]
            for item in health:
                for key in ("source_id", "error_category"):
                    item[key] = safe_audit_text(item[key] or "", 80)
            emit(json.dumps({"event": "fionaShadowSourceHealth", "occurrence_id": occurrence_id,
                             "sources": health}, separators=(",", ":")), flush=True)
        for record in shadow.get("selected_event_audits", [])[:MAX_LOG_SELECTED_RECORDS]:
            payload = {**record, "occurrence_id": occurrence_id, "event": "fionaShadowSelectedEvent"}
            emit(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), flush=True)
        if shadow.get("rejected_candidate_audits"):
            emit(json.dumps({"event": "fionaShadowRejectedCandidates", "occurrence_id": occurrence_id,
                             "evaluation_id": shadow.get("evaluation_id"),
                             "candidates": shadow["rejected_candidate_audits"][:MAX_REJECTED_RECORDS],
                             "omitted": shadow.get("rejected_audit_omitted", 0)},
                            ensure_ascii=False, separators=(",", ":")), flush=True)
    except Exception:
        # Logging failure must not alter a completed delivery or ledger result.
        return


def scheduler_log_projection(value: Any) -> Any:
    """Only stdout is projected; archives, returned status and ledger are unchanged."""
    if isinstance(value, list):
        return [scheduler_log_projection(item) for item in value]
    if not isinstance(value, dict):
        return value
    return {
        key: ({name: item.get(name) for name in ("ok", "evaluation_id", "error_category")}
              if key == "coverage_shadow" and isinstance(item, dict)
              else scheduler_log_projection(item))
        for key, item in value.items()
    }
