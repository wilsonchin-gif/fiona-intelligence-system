from __future__ import annotations

import copy
import hashlib
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock, patch

from test_fiona_v3_1_gate2 import NOW, event, source, synthetic_regional_events
from app.fiona_global_coverage import evaluate_global_coverage
from app.fiona_source_registry import EventRegion, SourceRegistry
from app.fiona_shadow_audit import emit_occurrence_audits, selected_event_audits, safe_audit_text
from app.fiona_coverage_runtime import CoverageObservationStore, run_global_coverage_shadow, validate_global_coverage_runtime
from app.fiona_runtime import occurrence_result
from app.fiona_scheduler import ScheduledOccurrence
from app.fiona_briefing import FionaBriefKind


def fixtures():
    return {
        "balanced": synthetic_regional_events({EventRegion.US_EU: 8, EventRegion.GREATER_CHINA: 4, EventRegion.REST_OF_WORLD: 3}),
        "override": [event(title="Bank failure creates systemic crisis", materiality=98, override=True), *synthetic_regional_events({EventRegion.US_EU: 6, EventRegion.GREATER_CHINA: 3, EventRegion.REST_OF_WORLD: 3})],
        "syndicated": [event(source("a")), event(source("b"))],
        "empty": [],
    }


# Captured from unchanged 6ae7f6d before applying Gate 2.1.
BASELINES = {
    "balanced": (["cluster_c0894c7c6a0b0100a92e", "cluster_d70d14f45e5b8f1e3948", "cluster_feab6b5cf42623f18aa9", "cluster_5a2df9ac718642f508fa", "cluster_3e708d714fe10189ce57", "cluster_ca6bf6116b2bb1f542ae", "cluster_194e9a7fd49760fef398", "cluster_17e8d8e34ef55014e4f8", "cluster_83f02de453236267128d", "cluster_123c0d0ffcce6670aa9c"], "b762291e1c4c5534bf79c35ea0ae9a1ccfbc1ce737f25f7bd834c1c0ddbeef55"),
    "override": (["cluster_83ebd447ddc5de2e2946", "cluster_d70d14f45e5b8f1e3948", "cluster_feab6b5cf42623f18aa9", "cluster_c0894c7c6a0b0100a92e", "cluster_5a2df9ac718642f508fa", "cluster_83f02de453236267128d", "cluster_3e708d714fe10189ce57", "cluster_194e9a7fd49760fef398", "cluster_68d56b519a013a9fcad8", "cluster_123c0d0ffcce6670aa9c"], "f59fc6b9f767e2cac2f0f4858da159950ba69f8a6e50cf40c079fd03d35fdac3"),
    "syndicated": (["cluster_506dc5cfd4b5c322e1f4"], "400bfed7927b7dc8921131b7f0c9438f69cd1a8151f83f25dc35a9682fb2864c"),
    "empty": ([], "b5b27b7652c0d83b3ba394a530bf7df374af76526a737e035e5d4fc7243dfffa"),
}


class ShadowEditorialAuditTests(unittest.TestCase):
    def setUp(self):
        self.network = patch("socket.socket.connect", side_effect=AssertionError("network forbidden"))
        self.network.start()
        self.addCleanup(self.network.stop)
        self.evaluation = evaluate_global_coverage(fixtures()["balanced"], evaluated_at=NOW)
        self.audit = selected_event_audits(self.evaluation)
        self.records = self.audit["selected_event_audits"]

    def test_selected_only_and_rank(self):
        self.assertEqual(len(self.records), 10)
        self.assertEqual([r["rank"] for r in self.records], list(range(1, 11)))

    def test_required_fields_match_cluster(self):
        for record, cluster in zip(self.records, self.evaluation.selected_clusters):
            for field, expected in {
                "cluster_id": cluster.cluster_id, "normalized_headline": cluster.normalized_headline,
                "event_region": cluster.event_region.value, "source_tier": int(cluster.source_tier),
                "source_count": cluster.source_count, "independent_source_count": cluster.independent_source_count,
                "materiality": cluster.materiality, "material_override": cluster.material_override,
            }.items():
                with self.subTest(field=field): self.assertEqual(record[field], expected)
            self.assertEqual(record["freshness"]["score"], cluster.freshness_score)
            self.assertIsNone(record["occurrence_id"])
            self.assertIsNone(record["override_reason"])

    def test_override_evidence(self):
        e = evaluate_global_coverage(fixtures()["override"], evaluated_at=NOW)
        r = selected_event_audits(e)["selected_event_audits"][0]
        self.assertTrue(r["material_override"])
        self.assertEqual(r["override_reason"], "test_material_event")
        self.assertIn("material_event_override", r["selection_reason"])
        self.assertEqual(r["score_components"]["selection_adjustment"], 100)

    def test_deterministic_reason_and_identity(self):
        self.assertEqual(self.audit, selected_event_audits(self.evaluation))

    def test_score_components_are_existing_values(self):
        for r, c in zip(self.records, self.evaluation.selected_clusters):
            s = r["score_components"]
            self.assertEqual(s["ranking_score"], c.ranking_score)
            self.assertEqual(s["quality_score"], c.quality_score)
            self.assertAlmostEqual(s["base_ranking_score"] + s["selection_adjustment"], c.ranking_score)
            self.assertEqual(s["cross_market_impact"], c.cross_market_impact)

    def test_before_after_fixed_ranking_and_aggregate_equivalence(self):
        for name, inputs in fixtures().items():
            with self.subTest(fixture=name):
                e = evaluate_global_coverage(inputs, evaluated_at=NOW)
                before = copy.deepcopy(e)
                audit = selected_event_audits(e)
                ids, digest = BASELINES[name]
                self.assertEqual([r["cluster_id"] for r in audit["selected_event_audits"]], ids)
                self.assertEqual(hashlib.sha256(json.dumps(e.metrics, sort_keys=True).encode()).hexdigest(), digest)
                self.assertEqual(e, before)
                self.assertFalse(audit["ranking_changed"])

    def test_no_article_snippet_url_or_private_payload(self):
        e = evaluate_global_coverage([event(summary="PRIVATE_ARTICLE_BODY_" * 100)], evaluated_at=NOW)
        rendered = json.dumps(selected_event_audits(e))
        self.assertNotIn("PRIVATE_ARTICLE_BODY", rendered)
        self.assertNotIn("news.example", rendered)
        self.assertNotIn("summary", rendered)

    def test_credentials_redacted_even_in_headline_or_identity(self):
        fake = "123456789:" + "x" * 35
        text = "Official release " + fake + " API_KEY=private-test-value https://user:pass@example.com?key=private"
        e = copy.deepcopy(self.evaluation)
        e.selected_clusters[0].normalized_headline = text
        rendered = json.dumps(selected_event_audits(e))
        for secret in [fake, "private-test-value", "user:pass", "?key=private"]:
            self.assertNotIn(secret, rendered)

    def test_log_injection_and_headline_limit(self):
        self.assertNotIn("\n", safe_audit_text("A\nB\rC"))
        self.assertLessEqual(len(safe_audit_text("Long " * 1000)), 240)

    def test_independence_distinguishes_syndication(self):
        snippet = "The Federal Reserve announced a new monetary policy decision affecting rates and global financial conditions."
        e = evaluate_global_coverage([event(source("a"), summary=snippet), event(source("b"), summary=snippet)], evaluated_at=NOW)
        r = selected_event_audits(e)["selected_event_audits"][0]
        self.assertEqual(r["source_count"], 2)
        self.assertEqual(r["independent_source_count"], 1)
        self.assertEqual(r["source_ids"], ["a", "b"])
        self.assertEqual(r["independence_groups"], ["a", "b"])
        self.assertNotIn("independent_confirmation", r["selection_reason"])

    def test_independent_reporting_is_visible(self):
        e = evaluate_global_coverage(fixtures()["syndicated"], evaluated_at=NOW)
        r = selected_event_audits(e)["selected_event_audits"][0]
        self.assertEqual(r["independent_source_count"], 2)
        self.assertIn("independent_confirmation", r["selection_reason"])

    def test_tier_one_single_source_not_falsely_confirmed(self):
        from app.fiona_source_registry import SourceTier
        e = evaluate_global_coverage([event(source(tier=SourceTier.TIER_1))], evaluated_at=NOW)
        r = selected_event_audits(e)["selected_event_audits"][0]
        self.assertIn("tier_1_authority", r["selection_reason"])
        self.assertNotIn("independent_confirmation", r["selection_reason"])

    def test_regional_adjustment_separate_from_override(self):
        for r in self.records:
            self.assertEqual(r["score_components"]["adjustment_kind"], "regional_balance")
            self.assertIn(r["regional_target_context"]["target_share"], [0.6, 0.3, 0.1])
            self.assertEqual(r["regional_target_context"]["selected_before"], r["rank"] - 1)

    def test_empty_evaluation_does_not_invent_event(self):
        audit = selected_event_audits(evaluate_global_coverage([], evaluated_at=NOW))
        self.assertEqual(audit["selected_event_audits"], [])
        self.assertFalse(audit["ranking_changed"])

    def test_structured_single_line_and_actual_occurrence_binding(self):
        calls = Mock()
        run = {"coverage_shadow": self.audit}
        before = copy.deepcopy(run)
        emit_occurrence_audits(run, "market_news:2026-09-04T00:00:00+08:00", calls)
        self.assertEqual(calls.call_count, 10)
        for call in calls.call_args_list:
            self.assertNotIn("\n", call.args[0])
            record = json.loads(call.args[0])
            self.assertEqual(record["occurrence_id"], "market_news:2026-09-04T00:00:00+08:00")
            self.assertEqual(record["event"], "fionaShadowSelectedEvent")
            self.assertLess(len(call.args[0].encode()), 8000)
        self.assertEqual(run, before)

    def test_logging_failure_cannot_fail_delivery(self):
        emit_occurrence_audits({"coverage_shadow": self.audit}, "actual", Mock(side_effect=OSError("stdout failed")))
        emit_occurrence_audits({"coverage_shadow": "malformed"}, "actual")

    def test_other_briefs_no_audit_log(self):
        calls = Mock()
        emit_occurrence_audits({"brief": "evening"}, "evening:actual", calls)
        calls.assert_not_called()

    def test_serializer_only_adds_logs_not_result_or_ledger(self):
        occurrence = ScheduledOccurrence.create(FionaBriefKind.MARKET_NEWS, NOW, NOW)
        run = {"coverage_shadow": self.audit, "brief_push": {"ok": True}}
        output = io.StringIO()
        with redirect_stdout(output):
            r = occurrence_result(occurrence, "success", True, "delivered", run)
        self.assertIs(r["run_status"], run)
        self.assertEqual(r["status"], "success")
        self.assertEqual(len(output.getvalue().splitlines()), 10)

    def test_runtime_store_and_zero_side_effects(self):
        spec = source("legacy", legacy=True)
        registry = SourceRegistry("3.1", (spec,))
        raw = [{"source_id": "legacy", "title": "Federal Reserve policy decision", "published_at": NOW}]
        with tempfile.TemporaryDirectory() as directory, patch("app.telegram_service.send_message") as tg:
            root = Path(directory)
            ledger = root / "fiona_scheduler_ledger.json"
            ledger.write_bytes(b"unchanged")
            result = run_global_coverage_shadow(raw, output_dir=root, evaluated_at=NOW, registry=registry, collect_expanded=False)
            self.assertTrue(result["selected_event_audits"])
            self.assertEqual(ledger.read_bytes(), b"unchanged")
            tg.assert_not_called()
            for field in ["telegram_api_calls", "scheduler_ledger_mutations", "formal_occurrences_created"]:
                self.assertEqual(result[field], 0)
            self.assertEqual(result["selection_authority"], "legacy")
            self.assertFalse(result["user_visible_content_changed"])
            store = CoverageObservationStore.load(root / "fiona_coverage_shadow_history.json")
            self.assertEqual(store.records[0]["selected_event_audits"], result["selected_event_audits"])

    def test_existing_history_clock_and_counts_preserved(self):
        from datetime import timedelta
        with tempfile.TemporaryDirectory() as directory:
            store = CoverageObservationStore(Path(directory) / "history.json")
            old = copy.deepcopy(self.evaluation)
            old.evaluated_at -= timedelta(days=1)
            store.record(old)
            start, count = store.observation_start_at, store.cumulative_qualified_clusters
            store.record(self.evaluation, self.audit)
            store.save()
            loaded = CoverageObservationStore.load(store.path)
            self.assertEqual(loaded.observation_start_at, start)
            self.assertEqual(loaded.cumulative_qualified_clusters, count)
            self.assertNotIn("selected_event_audits", loaded.records[0])

    def test_production_safe_validator_with_fixed_sources(self):
        registry = SourceRegistry("3.1", (source("legacy", legacy=True),))
        fake_fetch = lambda s, t: [{"title": "Federal Reserve policy decision", "published_at": NOW}]
        result = validate_global_coverage_runtime(registry=registry, fetcher=fake_fetch, evaluated_at=NOW)
        self.assertTrue(result["selected_event_audits"])
        self.assertFalse(result["ranking_changed"])
        for field in ["telegram_api_calls", "ledger_mutations", "formal_occurrences_created"]:
            self.assertEqual(result[field], 0)

    def test_detail_cap_does_not_cap_selection(self):
        e = copy.deepcopy(self.evaluation)
        e.selected_clusters *= 6
        audit = selected_event_audits(e)
        self.assertEqual(len(e.selected_clusters), 60)
        self.assertEqual(len(audit["selected_event_audits"]), 50)
        self.assertEqual(audit["audit_records_omitted"], 10)


if __name__ == "__main__":
    unittest.main()
