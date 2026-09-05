"""Bounded, read-only projections of completed Shadow selections."""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from typing import Any, Callable

from app.fiona_global_coverage import CoverageEvaluation, REGIONAL_TARGETS, base_ranking_score

MAX_AUDIT_RECORDS = 50
MAX_IDENTITIES = 24


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
        })
        preceding[cluster.event_region] += 1
    return {"evaluation_id": evaluation_id, "selected_event_audits": records,
            "ranking_changed": original_ids != [cluster.cluster_id for cluster in evaluation.selected_clusters],
            "audit_records_omitted": max(0, len(selected) - MAX_AUDIT_RECORDS)}


def emit_occurrence_audits(run_status: dict[str, Any], occurrence_id: str,
                           emit: Callable[..., Any] = print) -> None:
    """Bind the authoritative occurrence only when its existing result is serialized."""
    try:
        shadow = run_status.get("coverage_shadow") or {}
        for record in shadow.get("selected_event_audits", [])[:MAX_AUDIT_RECORDS]:
            payload = {**record, "occurrence_id": occurrence_id, "event": "fionaShadowSelectedEvent"}
            emit(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), flush=True)
    except Exception:
        # Logging failure must not alter a completed delivery or ledger result.
        return
