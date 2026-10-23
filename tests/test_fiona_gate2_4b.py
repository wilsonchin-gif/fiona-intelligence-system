from __future__ import annotations

import copy
import json
import tempfile
import unittest
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

from test_fiona_v3_1_gate2 import NOW, event, source
from app.fiona_editorial import (
    AssertionType, NoveltyIndex, NoveltyStatus, RelevanceClass, affected_markets,
)
from app.fiona_global_coverage import (
    cluster_events, eligibility_rejection, evaluate_global_coverage, normalize_source_item,
)
from app.fiona_coverage_runtime import CoverageObservationStore, run_global_coverage_shadow, validate_global_coverage_runtime
from app.fiona_shadow_audit import emit_occurrence_audits, selected_event_audits
from app.fiona_source_registry import EventRegion, SourceRegistry, SourceTier, load_source_registry


@dataclass(frozen=True)
class Case:
    name: str
    title: str
    eligible: bool
    assertion: str
    relevance: str
    region: str
    override: bool = False
    novelty: str = "NEW_EVENT"
    reason: str = "Synthetic explicit event evidence; no live-source claim."


CASES = (
    Case("policy", "Fed cuts interest rates by 25 basis points", True, "ANNOUNCED_DECISION", "DIRECT", "US_EU"),
    Case("official", "SEC approves new capital requirements for banks", True, "ANNOUNCED_DECISION", "DIRECT", "US_EU"),
    Case("macro", "US inflation rises to 4 percent in a surprise release", True, "REPORTED_OBSERVATION", "DIRECT", "US_EU"),
    Case("stability", "Bank of England announces emergency liquidity injection", True, "ANNOUNCED_DECISION", "DIRECT", "US_EU", True),
    Case("liquidity", "Systemic banking crisis triggers emergency response", True, "REALIZED_EVENT", "DIRECT", "UNKNOWN", True),
    Case("geopolitical", "War breaks out with global energy supply disruption", True, "REALIZED_EVENT", "TRANSMITTED", "GLOBAL", True),
    Case("nba", "NBA player wants to play another season with Golden State Warriors", False, "UNKNOWN", "NOT_RELEVANT", "UNKNOWN"),
    Case("artwork", "Banknote imagery advisory group minutes", False, "UNKNOWN", "CONTEXT_ONLY", "US_EU"),
    Case("personnel", "Senior appointment at central bank", False, "UNKNOWN", "CONTEXT_ONLY", "UNKNOWN"),
    Case("campaign", "GOP Senate super PAC raises record campaign fundraising", False, "REPORTED_OBSERVATION", "NOT_RELEVANT", "US_EU"),
    Case("commentary", "Political commentary on media strategies", False, "UNKNOWN", "NOT_RELEVANT", "UNKNOWN"),
    Case("conditional", "The Fed could surprise markets with a rate cut", True, "CONDITIONAL_SCENARIO", "DIRECT", "US_EU"),
    Case("surprise", "Fed announces unexpected rate cut", True, "ANNOUNCED_DECISION", "DIRECT", "US_EU", True),
    Case("negative", "Fed did not cut interest rates", True, "REPORTED_OBSERVATION", "DIRECT", "US_EU"),
    Case("hotel", "Hotels cut room rates as occupancy falls", False, "REPORTED_OBSERVATION", "CONTEXT_ONLY", "UNKNOWN"),
    Case("rates", "ECB holds interest rates unchanged", True, "ANNOUNCED_DECISION", "DIRECT", "US_EU"),
    Case("gold", "Gold prices rise 2 percent", True, "REPORTED_OBSERVATION", "DIRECT", "UNKNOWN"),
    Case("bilateral", "US and China announce new trade agreement", True, "ANNOUNCED_DECISION", "TRANSMITTED", "GLOBAL"),
    Case("euchina", "EU imposes tariffs on China exports", True, "ANNOUNCED_DECISION", "TRANSMITTED", "GLOBAL"),
    Case("russia", "US announces sanctions against Russia", True, "ANNOUNCED_DECISION", "TRANSMITTED", "GLOBAL"),
    Case("crypto", "Bitcoin whipsaws as global crypto liquidations near 1 billion", True, "REPORTED_OBSERVATION", "DIRECT", "GLOBAL"),
    Case("unchanged", "ECB holds policy rates unchanged", False, "ANNOUNCED_DECISION", "DIRECT", "US_EU", novelty="UNCHANGED"),
    Case("followup", "ECB publishes revised inflation data", True, "REPORTED_OBSERVATION", "DIRECT", "US_EU", novelty="MATERIAL_UPDATE"),
    Case("periodic", "US CPI rises 3 percent September 2026", True, "REPORTED_OBSERVATION", "DIRECT", "US_EU", novelty="PERIODIC_NEW_OCCURRENCE"),
    Case("corroboration", "BOJ raises policy rates", True, "ANNOUNCED_DECISION", "DIRECT", "REST_OF_WORLD"),
    Case("syndication", "PBOC announces policy rate cut", True, "ANNOUNCED_DECISION", "DIRECT", "GREATER_CHINA"),
    Case("unknown_geo", "Bond yields rise 20 basis points", True, "REPORTED_OBSERVATION", "DIRECT", "UNKNOWN"),
    Case("unknown_relevance", "Unspecified local community development", False, "REPORTED_OBSERVATION", "UNKNOWN", "UNKNOWN"),
    Case("override", "SEC announces major regulatory ban", True, "ANNOUNCED_DECISION", "DIRECT", "US_EU", True),
    Case("weak_region", "China routine auction notice", False, "UNKNOWN", "CONTEXT_ONLY", "GREATER_CHINA"),
)

CASE_REASONS = {
    "policy": "An actual rate action is financial; ordinary cuts are not automatically exceptional.",
    "official": "Traceable single-source capital regulation need not have a second publisher.",
    "macro": "A reported inflation measurement with surprise language has direct macro relevance.",
    "stability": "Announced emergency liquidity action is material before a price response occurs.",
    "liquidity": "Reported systemic banking crisis has an explicit stability channel.",
    "geopolitical": "Realized war and energy disruption support an early-warning transmission channel.",
    "nba": "Player-season news has no business result or supported financial channel.",
    "artwork": "Currency artwork administration is not monetary policy.",
    "personnel": "Routine personnel news lacks material financial evidence.",
    "campaign": "Political campaign receipts are not capital-market flow evidence.",
    "commentary": "Media-style commentary supplies no financial development.",
    "conditional": "A rate scenario may inform expectations but cannot claim a realized surprise.",
    "surprise": "A traceable actual unexpected decision may earn material override.",
    "negative": "A negative rate statement is an observation, not an executed cut.",
    "hotel": "Hotel room prices are not policy interest rates.",
    "rates": "An actual hold is a decision even when no rate changes.",
    "gold": "Whole-word gold and observed price movement identify commodities.",
    "bilateral": "A bilateral announcement preserves both jurisdictions.",
    "euchina": "Tariff imposition is an announced trade measure across EU and China.",
    "russia": "US policy issuer and Russian target must remain distinct.",
    "crypto": "Global liquidation evidence is not assigned a publisher's home region.",
    "unchanged": "Same selected facts are not a new editorial development.",
    "followup": "Explicit revised quantitative evidence can update the same cluster.",
    "periodic": "A named new release period is a separate occurrence, not retrieval refresh.",
    "corroboration": "Independent reports strengthen evidence, not economic importance.",
    "syndication": "Shared ownership does not count as independent corroboration.",
    "unknown_geo": "A market observation can be relevant without invented country attribution.",
    "unknown_relevance": "Source identity alone cannot prove financial relevance.",
    "override": "A supported material regulatory ban may override a regional target.",
    "weak_region": "An underweight region cannot rescue routine filler.",
}
CASES = tuple(replace(c, reason=CASE_REASONS[c.name]) for c in CASES)


def history(evaluation):
    return [{"evaluated_at": evaluation.evaluated_at.isoformat(), **selected_event_audits(evaluation)}]


def compare_retained_titles():
    """Selected-subset experiment: empty snippets and explicitly synthetic URL/time evidence."""
    fixture = json.loads((Path(__file__).parent/"fixtures/gate2_4b_historical_selected.json").read_text())
    registry = load_source_registry()
    prior, results = [], []
    for date in sorted({row["key"].split("/")[0] for row in fixture["records"]}):
        rows = [row for row in fixture["records"] if row["key"].startswith(date)]
        now = datetime.fromisoformat(rows[0]["evaluated_at"])
        events = [normalize_source_item({"title": row["headline"], "summary": "", "url": "https://fixture.invalid/"+row["cluster_id"], "published_at": now,
                                         "evidence_origin": "RECONSTRUCTED_ASSUMPTION"}, registry.by_id(row["source_id"]), retrieved_at=now) for row in rows]
        evaluation = evaluate_global_coverage(events, evaluated_at=now, editorial_history=prior)
        clusters = {c.normalized_headline: c for c in evaluation.clusters}
        for row in rows:
            c = clusters[row["headline"]]
            results.append({"key": row["key"], "headline": row["headline"], "label": row["editorial_label"],
                            "old_eligible": True, "new_eligible": eligibility_rejection(c) is None,
                            "old_M": row["old_materiality"], "new_M": c.materiality,
                            "old_Q": row["old_quality"], "new_Q": c.quality_score,
                            "old_region": row["old_region"], "new_region": c.event_region.value,
                            "old_override": row["old_override"], "new_override": c.material_override,
                            "assertion": c.editorial.assertion.assertion_type.value,
                            "relevance": c.editorial.relevance.relevance_class.value,
                            "old_novelty": "NOT_EVALUATED", "new_novelty": c.novelty.status.value,
                            "reason": eligibility_rejection(c)})
        prior.append({"evaluated_at": now.isoformat(), **selected_event_audits(evaluation)})
    return results


class EditorialContractTests(unittest.TestCase):
    def setUp(self):
        self.network = patch("socket.socket.connect", side_effect=AssertionError("network forbidden"))
        self.network.start()
        self.addCleanup(self.network.stop)

    def test_quality_independent_of_materiality(self):
        a = event(title="Fed cuts interest rates", summary="", materiality=45)
        b = replace(a, materiality=95)
        self.assertEqual(cluster_events([a])[0][0].quality_score, cluster_events([b])[0][0].quality_score)

    def test_authority_does_not_create_financial_relevance(self):
        a = event(source(source_type="Official", tier=SourceTier.TIER_1), title="Basketball player joins Warriors next season", summary="")
        self.assertFalse(evaluate_global_coverage([a], evaluated_at=NOW).selected_clusters)

    def test_source_market_priors_never_inflate_impact(self):
        s = source()
        title = "Gold prices rise 2 percent"
        a = event(s, title=title, summary="")
        b = event(replace(s, markets=("equities", "rates", "fx", "crypto")), title=title, summary="")
        self.assertEqual(a.markets, ("commodities",))
        self.assertEqual(a.cross_market_impact, b.cross_market_impact)
        self.assertNotEqual(a.editorial.source_supported_markets, b.editorial.source_supported_markets)

    def test_boundaries(self):
        for title in ("Golden State Warriors", "feds warn of criminal conduct", "Hotels cut room rates"):
            self.assertNotIn("rates", affected_markets(title))
        self.assertNotIn("commodities", affected_markets("Golden State Warriors"))
        for title in ("Gold prices rise", "policy rates", "bond yields", "interest-rate expectations", "monetary policy", "market liquidity"):
            self.assertTrue(affected_markets(title) or event(title=title, summary="").editorial.relevance.eligible)

    def test_expectation_is_not_discarded_or_overridden(self):
        a = event(title="Analysts expect a Fed rate cut", summary="")
        e = evaluate_global_coverage([a], evaluated_at=NOW)
        self.assertEqual(a.editorial.assertion.assertion_type, AssertionType.EXPECTATION)
        self.assertTrue(e.selected_clusters)
        self.assertFalse(e.selected_clusters[0].material_override)
        self.assertLess(a.materiality, 75)

    def test_negation_cannot_be_realized_cut(self):
        a = event(title="Fed did not announce an emergency rate cut", summary="")
        self.assertEqual(a.editorial.assertion.assertion_type, AssertionType.REPORTED_OBSERVATION)
        self.assertFalse(a.material_override)
        self.assertLess(a.materiality, 75)

    def test_generic_rates_and_future_announcement_distinct(self):
        a = event(title="Fed announced a future rate decision date", summary="")
        self.assertFalse(a.material_override)
        self.assertLess(a.materiality, 75)

    def test_override_requires_traceable_current_evidence(self):
        for kwargs in ({"url": ""}, {"published_at": None}, {"published_at": NOW-timedelta(days=8)}):
            raw = {"title": "Fed announces unexpected rate cut", "published_at": NOW, "url": "https://example.com/decision", **kwargs}
            a = normalize_source_item(raw, source(), retrieved_at=NOW)
            self.assertFalse(a.material_override)

    def test_high_materiality_and_region_cannot_rescue_irrelevance(self):
        a = event(title="China routine personnel appointment", summary="", materiality=100, override=True)
        self.assertFalse(evaluate_global_coverage([a], evaluated_at=NOW).selected_clusters)

    def test_auction_with_measured_surprise_can_qualify(self):
        a = event(title="US Treasury auction result shows unexpected yield spike of 25 basis points", summary="")
        self.assertTrue(evaluate_global_coverage([a], evaluated_at=NOW).selected_clusters)

    def test_actual_past_tense_trade_actions_remain_eligible(self):
        for title in ("US announced sanctions against Russia", "EU imposed tariffs on China exports", "US waived sanctions against Russia"):
            a = event(title=title, summary="")
            self.assertEqual(a.editorial.assertion.assertion_type, AssertionType.ANNOUNCED_DECISION)
            self.assertTrue(evaluate_global_coverage([a], evaluated_at=NOW).selected_clusters)

    def test_hospitality_corporate_finance_is_not_room_rate_news(self):
        a = event(title="Hotel company issued bonds as yields rise", summary="")
        self.assertTrue(evaluate_global_coverage([a], evaluated_at=NOW).selected_clusters)

    def test_administrative_subject_with_measured_market_impact_is_not_banned(self):
        a = event(title="CEO appointment triggers shares plunge 10 percent", summary="")
        self.assertTrue(evaluate_global_coverage([a], evaluated_at=NOW).selected_clusters)

    def test_selected_count_is_maximum_not_quota(self):
        a = event(title="Fed cuts rates", summary="")
        e = evaluate_global_coverage([a, event(title="Unspecified community update", summary="")], evaluated_at=NOW)
        self.assertEqual(len(e.selected_clusters), 1)
        self.assertEqual(e.metrics["selection_shortfall_reason"], "insufficient_independently_eligible_events")

    def test_more_than_ten_overrides_still_maximum_ten(self):
        pool = [event(source(f"source{i}"), title=f"Fed announces unexpected rate cut issuer {i}", url=f"https://example.com/{i}") for i in range(15)]
        # Distinct domains/subjects, not re-syndications of a single event.
        clusters, _ = cluster_events(pool)
        copies = [replace(clusters[0], cluster_id=f"c{i}") for i in range(15)]
        from app.fiona_global_coverage import rank_coverage_clusters
        self.assertEqual(len(rank_coverage_clusters(copies)[1]), 10)

    def test_bab_al_mandeb_speaker_not_primary_location(self):
        a = event(title="China urges opening Bab al-Mandeb shipping route", summary="")
        g = a.editorial.geography
        self.assertEqual(g.primary_event_jurisdiction, EventRegion.REST_OF_WORLD)
        self.assertIn(EventRegion.GREATER_CHINA, g.secondary_affected_regions)
        self.assertEqual(g.canonical_editorial_region, EventRegion.GLOBAL)

    def test_lowercase_us_pronoun_not_american_jurisdiction(self):
        a = event(title="Analysts tell us bond yields rise", summary="")
        self.assertEqual(a.event_region, EventRegion.UNKNOWN)

    def test_publisher_does_not_supply_geography(self):
        for region in EventRegion:
            a = event(source(region=region), title="Bond yields rise", summary="")
            self.assertEqual(a.event_region, EventRegion.UNKNOWN)

    def test_global_background_word_does_not_erase_policy_jurisdiction(self):
        a = event(title="Fed holds policy rates amid global tightening", summary="")
        self.assertEqual(a.event_region, EventRegion.US_EU)

    def test_central_bank_primary_actor_survives_secondary_market_reference(self):
        a = event(title="PBOC cuts policy rates as US stocks rise", summary="")
        self.assertEqual(a.editorial.geography.primary_event_jurisdiction, EventRegion.GREATER_CHINA)
        self.assertIn(EventRegion.US_EU, a.editorial.geography.secondary_affected_regions)

    def test_novelty_rejects_unchanged_across_restart_and_new_publisher(self):
        first = evaluate_global_coverage([event(title="ECB holds policy rates unchanged", summary="The policy rate is 3 percent.")], evaluated_at=NOW)
        records = history(first)
        with tempfile.TemporaryDirectory() as directory:
            store = CoverageObservationStore(Path(directory)/"shadow.json", records)
            store.save()
            loaded = CoverageObservationStore.load(store.path)
            a = event(source("independent_newspaper"), title="ECB holds policy rates unchanged", summary="The policy rate is 3 percent.")
            a = replace(a, retrieved_at=NOW+timedelta(hours=4))
            later = evaluate_global_coverage([a], evaluated_at=NOW+timedelta(hours=4), editorial_history=loaded.records)
        self.assertEqual(later.clusters[0].novelty.status, NoveltyStatus.UNCHANGED)
        self.assertFalse(later.selected_clusters)

    def test_material_followup_same_cluster_allowed(self):
        title = "ECB publishes revised inflation data"
        first = evaluate_global_coverage([event(title=title, summary="Inflation is 3 percent.")], evaluated_at=NOW)
        a = event(title=title, summary="Inflation is revised to 4 percent.")
        later = evaluate_global_coverage([a], evaluated_at=NOW+timedelta(hours=4), editorial_history=history(first))
        self.assertEqual(first.clusters[0].cluster_id, later.clusters[0].cluster_id)
        self.assertEqual(later.clusters[0].novelty.status, NoveltyStatus.MATERIAL_UPDATE)
        self.assertTrue(later.selected_clusters)

    def test_wording_change_alone_not_material_followup(self):
        first = evaluate_global_coverage([event(title="ECB holds rates", summary="Policy rate is 3 percent.")], evaluated_at=NOW)
        later = evaluate_global_coverage([event(title="ECB holds rates", summary="The policy rate remains 3 percent, as previously stated.")], evaluated_at=NOW+timedelta(hours=4), editorial_history=history(first))
        self.assertEqual(later.clusters[0].novelty.status, NoveltyStatus.UNKNOWN)
        self.assertFalse(later.selected_clusters)

    def test_periodic_new_release_is_not_suppressed(self):
        first = evaluate_global_coverage([event(title="US CPI rises 3 percent September 2026", summary="")], evaluated_at=NOW)
        later = evaluate_global_coverage([event(title="US CPI rises 3 percent October 2026", summary="")], evaluated_at=NOW+timedelta(hours=4), editorial_history=history(first))
        self.assertEqual(later.clusters[0].novelty.status, NoveltyStatus.PERIODIC_NEW_OCCURRENCE)
        self.assertTrue(later.selected_clusters)

    def test_weekly_explicit_date_is_a_distinct_release(self):
        first = evaluate_global_coverage([event(title="US weekly payroll data rises October 16 2026", summary="")], evaluated_at=NOW)
        later = evaluate_global_coverage([event(title="US weekly payroll data rises October 23 2026", summary="")], evaluated_at=NOW+timedelta(hours=4), editorial_history=history(first))
        self.assertEqual(later.clusters[0].novelty.status, NoveltyStatus.PERIODIC_NEW_OCCURRENCE)

    def test_generic_official_titles_do_not_merge_different_central_banks(self):
        a = event(source("boj_whatsnew", source_type="Official"), title="Monetary Policy Decision", summary="")
        b = event(source("rbi_press", source_type="Official"), title="Monetary Policy Decision", summary="")
        first = evaluate_global_coverage([a], evaluated_at=NOW)
        later = evaluate_global_coverage([b], evaluated_at=NOW+timedelta(hours=4), editorial_history=history(first))
        self.assertEqual(later.clusters[0].novelty.status, NoveltyStatus.NEW_EVENT)

    def test_negative_or_conditional_outcome_is_not_material_update(self):
        first = evaluate_global_coverage([event(title="ECB holds rates", summary="Policy is unchanged.")], evaluated_at=NOW)
        for summary in ("The risk is not resolved.", "The issue could be resolved."):
            later = evaluate_global_coverage([event(title="ECB holds rates", summary=summary)], evaluated_at=NOW+timedelta(hours=4), editorial_history=history(first))
            self.assertNotEqual(later.clusters[0].novelty.status, NoveltyStatus.MATERIAL_UPDATE)

    def test_confirmation_changes_quality_not_materiality(self):
        a = event(source("primary"), title="ECB holds rates", summary="Official release.")
        b = event(source("independent"), title="ECB holds rates", summary="Independent reporting.")
        single = cluster_events([a])[0][0]
        double = cluster_events([a,b])[0][0]
        self.assertEqual(single.materiality, double.materiality)
        self.assertGreater(double.quality_score, single.quality_score)
        record = selected_event_audits(evaluate_global_coverage([a,b], evaluated_at=NOW))["selected_event_audits"][0]
        self.assertEqual(record["evidence_quality"]["value"], min(100, sum(record["evidence_quality"]["components"].values())))

    def test_corrupt_history_preserved_and_important_event_not_blocked(self):
        s = source("official", legacy=True, source_type="Official")
        with tempfile.TemporaryDirectory() as directory, patch.dict("os.environ", {}, clear=True):
            path = Path(directory)/"fiona_coverage_shadow_history.json"
            path.write_text("CORRUPT", encoding="utf-8")
            result = run_global_coverage_shadow([{"source_id": s.source_id, "title": "Fed cuts rates", "url": "https://example.com/decision", "published_at": NOW}], output_dir=Path(directory), evaluated_at=NOW, registry=SourceRegistry("3.1", (s,)), collect_expanded=False)
            self.assertTrue(result["ok"])
            self.assertEqual(path.read_text(), "CORRUPT")
            self.assertEqual(result["novelty_history_status"], "unavailable_preserved")
            self.assertTrue(result["selected_event_audits"])
            self.assertEqual(result["selected_event_audits"][0]["novelty_decision"]["status"], "UNKNOWN")

    def test_history_expiry_future_records_and_old_schema(self):
        a = event(title="Fed cuts rates", summary="")
        first = evaluate_global_coverage([a], evaluated_at=NOW)
        for records in ([{"evaluated_at": (NOW+timedelta(days=1)).isoformat(), **selected_event_audits(first)}],
                        [{"evaluated_at": NOW.isoformat(), "selected_event_audits": [{"normalized_headline": a.normalized_headline}]}]):
            self.assertTrue(evaluate_global_coverage([a], evaluated_at=NOW, editorial_history=records).selected_clusters)
        self.assertFalse(NoveltyIndex(history(first), NOW+timedelta(days=22)).by_family)

    def test_malformed_history_identity_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"shadow.json"
            content = json.dumps({"records": [{"evaluated_at": NOW.isoformat(), "selected_event_audits": [{"editorial_memory": {"family_key": []}}]}]})
            path.write_text(content)
            store = CoverageObservationStore.load(path)
            self.assertIsNotNone(store.load_error)
            with self.assertRaises(ValueError):
                store.save()
            self.assertEqual(path.read_text(), content)

    def test_malformed_url_does_not_produce_override(self):
        # Feed normalization still owns canonical-URL validation; evidence itself fails closed.
        from app.fiona_editorial import assess_event
        a = assess_event("Fed announces unexpected rate cut", "", source(), "http://[bad", NOW, NOW)
        self.assertEqual(a.evidence_quality.components["traceability"], 0)
        self.assertFalse(a.override_eligible)

    def test_selected_rejected_audit_bounded_sanitized_and_nonmutating(self):
        pool = [event(source(f"bad{i}"), title=f"NBA player {i} leaves Warriors next season", summary="PRIVATE_BODY"*100) for i in range(40)]
        e = evaluate_global_coverage(pool, evaluated_at=NOW)
        before = copy.deepcopy(e)
        audit = selected_event_audits(e)
        self.assertEqual(e, before)
        self.assertLessEqual(len(audit["rejected_candidate_audits"]), 20)
        self.assertNotIn("PRIVATE_BODY", json.dumps(audit))
        self.assertLess(len(json.dumps(audit).encode()), 20000)
        emit = Mock()
        emit_occurrence_audits({"coverage_shadow": audit}, "fixture-not-occurrence", emit)
        self.assertTrue(any(json.loads(c.args[0])["event"] == "fionaShadowRejectedCandidates" for c in emit.call_args_list))

    def test_validator_has_no_state_or_delivery(self):
        s = source("sec", source_type="Official", legacy=True)
        def fetch(_source, _timeout):
            return [{"title": "SEC approves new capital requirements", "url": "https://example.com/release", "published_at": NOW}]
        with patch("app.fiona_state.atomic_write_json", side_effect=AssertionError("no state writes")), patch("app.telegram_service.send_message", side_effect=AssertionError("no telegram")):
            result = validate_global_coverage_runtime(registry=SourceRegistry("3.1", (s,)), fetcher=fetch, evaluated_at=NOW)
        self.assertTrue(result["ok"])
        self.assertEqual(result["telegram_api_calls"], 0)
        self.assertEqual(result["ledger_mutations"], 0)
        self.assertEqual(result["formal_occurrences_created"], 0)

    def test_historical_retained_fields_are_not_complete_replay(self):
        fixture = json.loads((Path(__file__).parent/"fixtures/gate2_4b_historical_selected.json").read_text())
        self.assertEqual(len(fixture["records"]), 70)
        self.assertIn("original_summary", fixture["missing_fields"])
        registry = load_source_registry()
        for row in fixture["records"]:
            if row["editorial_label"] != "INCORRECT":
                continue
            s = registry.by_id(row["source_id"])
            a = event(s, title=row["headline"], summary="")
            selected = evaluate_global_coverage([a], evaluated_at=NOW).selected_clusters
            if row["old_override"]:
                self.assertFalse(a.material_override)
            else:
                self.assertFalse(selected, row["headline"])

    def test_all_retained_good_titles_still_qualify_in_declared_experiment(self):
        comparison = compare_retained_titles()
        good = [row for row in comparison if row["label"] == "GOOD"]
        self.assertEqual(len(comparison), 70)
        self.assertEqual(len(good), 8)
        self.assertTrue(all(row["new_eligible"] for row in good))


class EvidenceAwareCorrectionTests(unittest.TestCase):
    """All source statements below are synthetic controls, never historical recovery."""

    def setUp(self):
        self.network = patch("socket.socket.connect", side_effect=AssertionError("network forbidden"))
        self.network.start()
        self.addCleanup(self.network.stop)
        self.official = source("bok_press", source_type="Official", tier=SourceTier.TIER_1)
        self.summary = "The Bank of Korea reported GDP contracted 2.0 percent; inflation rose to 5.0 percent; bank liquidity fell 15 percent."

    def assessment(self, title="Recent Economic Developments", summary=None, **kwargs):
        a = event(self.official, title=title, summary=self.summary if summary is None else summary, **kwargs)
        return a, evaluate_global_coverage([a], evaluated_at=NOW)

    def test_generic_empty_is_unknown_not_nonfinancial(self):
        a, e = self.assessment(summary="")
        self.assertEqual(a.editorial.assertion.assertion_type, AssertionType.UNKNOWN)
        self.assertEqual(a.editorial.relevance.relevance_class, RelevanceClass.UNKNOWN)
        self.assertFalse(e.selected_clusters)

    def test_generic_with_observations_qualifies(self):
        a, e = self.assessment()
        self.assertEqual(a.editorial.assertion.assertion_type, AssertionType.REPORTED_OBSERVATION)
        self.assertEqual(a.editorial.relevance.relevance_class, RelevanceClass.DIRECT)
        self.assertTrue(e.selected_clusters)
        self.assertIn("source_claim:financial", a.editorial.assertion.evidence_references)
        self.assertIsNone(a.editorial.assertion.event_time)
        commodity, c = self.assessment(title="Market developments", summary="Gold prices rose 2 percent.")
        self.assertEqual(commodity.editorial.relevance.relevance_class, RelevanceClass.DIRECT)
        self.assertTrue(c.selected_clusters)

    def test_same_summary_explicit_and_generic_titles_are_consistent(self):
        a, e = self.assessment()
        b, f = self.assessment(title="Bank of Korea reports GDP contraction and inflation surge")
        self.assertEqual(a.editorial.assertion.assertion_type, b.editorial.assertion.assertion_type)
        self.assertEqual(a.editorial.relevance.relevance_class, b.editorial.relevance.relevance_class)
        self.assertLessEqual(abs(a.materiality-b.materiality), 5)
        self.assertTrue(e.selected_clusters and f.selected_clusters)

    def test_incidental_finance_words_do_not_qualify(self):
        for snippet in ("The market is a metaphor. Gold is the team's nickname.",
                        "GDP is an acronym discussed in a classroom.",
                        "A player shared a market story with Golden State Warriors.",
                        "The paper published a glossary of inflation.", "The word market appears in a speech.",
                        "CPI is 3 letters.", "GDP is an acronym discussed in 2026."):
            with self.subTest(snippet=snippet):
                a, e = self.assessment(title="Community update", summary=snippet)
                self.assertIn(a.editorial.relevance.relevance_class, {RelevanceClass.UNKNOWN, RelevanceClass.NOT_RELEVANT})
                self.assertFalse(e.selected_clusters)

    def test_speculative_body_cannot_authenticate_headline_decision(self):
        a, _ = self.assessment(title="Fed announces unexpected rate cut", summary="Analysts expect the Fed could cut interest rates next year; no decision is confirmed.")
        self.assertIn(a.editorial.assertion.assertion_type, {AssertionType.EXPECTATION, AssertionType.CONDITIONAL_SCENARIO})
        self.assertFalse(a.material_override)
        self.assertLessEqual(a.materiality, 60)

    def test_scenario_context_spans_sentences_without_becoming_decision(self):
        a, _ = self.assessment(title="Fed announces unexpected rate cut", summary="Analysts speculate in a hypothetical scenario. The Fed cuts interest rates next quarter.")
        self.assertEqual(a.editorial.assertion.assertion_type, AssertionType.CONDITIONAL_SCENARIO)
        self.assertFalse(a.material_override)

    def test_denial_prevents_false_rate_cut_and_override(self):
        for snippet in ("The Federal Reserve did not cut interest rates.", "The Fed held policy rates unchanged at 4 percent."):
            a, _ = self.assessment(title="Fed announces unexpected rate cut", summary=snippet)
            self.assertNotEqual(a.editorial.assertion.assertion_type, AssertionType.REALIZED_EVENT)
            self.assertTrue(a.editorial.assertion.negation_markers)
            self.assertFalse(a.material_override)

    def test_reverse_contradiction_is_conservative(self):
        a, e = self.assessment(title="Fed did not cut interest rates", summary="The Fed announced an emergency rate cut.")
        self.assertEqual(a.editorial.assertion.assertion_type, AssertionType.UNKNOWN)
        self.assertFalse(a.material_override)
        self.assertFalse(e.selected_clusters)

    def test_unrelated_observation_cannot_authorize_headline_override(self):
        a, _ = self.assessment(title="Fed announces unexpected rate cut", summary="GDP contracted 2 percent.")
        self.assertFalse(a.material_override)
        self.assertEqual(a.materiality, 70)

    def test_specific_transmission_supported_by_body(self):
        a, e = self.assessment(title="European energy-security developments", summary="An attack disrupted oil supply and shipping costs rose 20 percent.")
        self.assertEqual(a.editorial.relevance.relevance_class, RelevanceClass.TRANSMITTED)
        self.assertTrue(a.editorial.relevance.transmission_channels)
        self.assertTrue(e.selected_clusters)

    def test_opportunity_title_does_not_ban_actual_banking_development(self):
        a, e = self.assessment(title="New opportunities for banks", summary="The central bank launched a settlement platform and issued bonds worth 2 billion.")
        self.assertEqual(a.editorial.relevance.relevance_class, RelevanceClass.DIRECT)
        self.assertTrue(e.selected_clusters)

    def test_publisher_market_priors_do_not_rescue_unknown(self):
        for typ in ("Official", "MajorMedia"):
            a = event(source(source_type=typ), title="Community update", summary="No details supplied.")
            self.assertEqual(a.editorial.relevance.relevance_class, RelevanceClass.UNKNOWN)
            self.assertFalse(evaluate_global_coverage([a], evaluated_at=NOW).selected_clusters)

    def test_missing_publication_time_not_invented(self):
        a, e = self.assessment(published_at=None)
        self.assertIsNone(a.published_at)
        self.assertIsNone(a.editorial.assertion.event_time)
        self.assertFalse(e.selected_clusters)

    def test_false_positive_boundaries_with_incidental_summary(self):
        titles = ("NBA player joins Golden State Warriors", "GOP Senate super PAC raises campaign fundraising",
                  "Political commentary on media strategies", "Banknote imagery advisory group minutes",
                  "Hotels cut room rates", "feds warn of criminal conduct")
        for title in titles:
            with self.subTest(title=title):
                a, e = self.assessment(title=title, summary="The story mentions the word market and the nickname Gold.")
                self.assertFalse(e.selected_clusters)
                self.assertFalse(a.material_override)

    def test_design_meeting_is_not_rate_decision_from_body_word_overlap(self):
        a, e = self.assessment(title="Banknote imagery advisory group minutes", summary="The committee held a design meeting mentioning policy rates.")
        self.assertFalse(e.selected_clusters)
        self.assertFalse(a.material_override)

    def test_political_campaign_receipts_not_corporate_revenue(self):
        a, e = self.assessment(title="GOP Senate super PAC raises campaign fundraising", summary="Campaign fundraising revenue rose 15 percent.")
        self.assertEqual(a.editorial.relevance.relevance_class, RelevanceClass.NOT_RELEVANT)
        self.assertFalse(e.selected_clusters)

    def test_confirmed_generic_headline_defect_through_real_rss_legacy_path(self):
        from app import wilson
        from app.fiona_coverage_runtime import normalize_legacy_candidates
        s = source("fixture_official", source_type="Official", legacy=True)
        registry = SourceRegistry("3.1", (s,))
        rss = f'<rss><channel><item><title>Recent Economic Developments</title><description>{self.summary}</description><link>https://fixture.invalid/report</link><pubDate>{NOW.isoformat()}</pubDate></item></channel></rss>'.encode()
        with patch.object(wilson, "load_source_registry", return_value=registry), patch.object(wilson, "http_bytes", return_value=rss), patch.dict(wilson.RUN_CACHE, {}, clear=True):
            wilson.fetch_news()
            raw = wilson.latest_news_candidates()
            normalized = normalize_legacy_candidates(raw, registry, retrieved_at=NOW)
        self.assertEqual(normalized[0].source_provenance.original_text_snippet, self.summary)
        evaluation = evaluate_global_coverage(normalized, evaluated_at=NOW)
        audit = selected_event_audits(evaluation)
        self.assertTrue(evaluation.selected_clusters)
        self.assertEqual(audit["selected_event_audits"][0]["financial_relevance_class"], "DIRECT")
        self.assertNotIn(self.summary, json.dumps(audit))

    def test_expanded_adapter_description_reaches_representative(self):
        from app.fiona_global_coverage import collect_source, parse_rss_payload
        rss = f'<rss><channel><item><title>Recent Economic Developments</title><description>{self.summary}</description><link>https://fixture.invalid/report</link><pubDate>{NOW.isoformat()}</pubDate></item></channel></rss>'.encode()
        events, _ = collect_source(self.official, retrieved_at=NOW, fetcher=lambda *_: parse_rss_payload(rss))
        e = evaluate_global_coverage(events, evaluated_at=NOW)
        self.assertTrue(e.selected_clusters)
        self.assertEqual(e.selected_clusters[0].editorial.assertion.assertion_type, AssertionType.REPORTED_OBSERVATION)

    def test_same_cluster_new_measured_development(self):
        title = "KOSPI stocks plunge"
        first = evaluate_global_coverage([event(title=title, summary="KOSPI stocks plunged 3 percent.")], evaluated_at=NOW)
        a = event(title=title, summary="KOSPI stocks plunged 7 percent.")
        later = evaluate_global_coverage([a], evaluated_at=NOW+timedelta(hours=4), editorial_history=history(first))
        self.assertEqual(first.clusters[0].cluster_id, later.clusters[0].cluster_id)
        self.assertEqual(later.clusters[0].novelty.status, NoveltyStatus.MATERIAL_UPDATE)
        self.assertTrue(later.selected_clusters)

    def test_tiny_unexplained_numeric_edit_not_automatically_material(self):
        title = "KOSPI stocks plunge"
        first = evaluate_global_coverage([event(title=title, summary="KOSPI stocks plunged 3 percent.")], evaluated_at=NOW)
        e = evaluate_global_coverage([event(title=title, summary="KOSPI stocks plunged 3.001 percent.")], evaluated_at=NOW, editorial_history=history(first))
        self.assertEqual(e.clusters[0].novelty.status, NoveltyStatus.UNKNOWN)
        self.assertFalse(e.selected_clusters)

    def test_explicit_small_macro_revision_not_lost_to_numeric_noise_filter(self):
        title = "ECB publishes revised inflation data"
        first = evaluate_global_coverage([event(title=title, summary="Inflation is 3 percent.")], evaluated_at=NOW)
        e = evaluate_global_coverage([event(title=title, summary="Inflation is revised to 3.1 percent.")], evaluated_at=NOW, editorial_history=history(first))
        self.assertEqual(e.clusters[0].novelty.status, NoveltyStatus.MATERIAL_UPDATE)
        self.assertTrue(e.selected_clusters)

    def test_new_independent_circuit_breaker_session_qualifies(self):
        title = "KOSPI triggers circuit breaker"
        a = event(self.official, title=title, summary="During the September 3 2026 trading session, KOSPI triggered a circuit breaker after stocks plunged 8 percent.")
        b = normalize_source_item({"title": title, "summary": "During the September 4 2026 trading session, KOSPI triggered a circuit breaker after stocks plunged 8 percent.",
                                   "url": "https://fixture.invalid/new-session", "published_at": NOW+timedelta(days=1)},
                                  self.official, retrieved_at=NOW+timedelta(days=1))
        first = evaluate_global_coverage([a], evaluated_at=NOW)
        later = evaluate_global_coverage([b], evaluated_at=NOW+timedelta(days=1), editorial_history=history(first))
        self.assertEqual(later.clusters[0].novelty.status, NoveltyStatus.PERIODIC_NEW_OCCURRENCE)
        self.assertTrue(later.selected_clusters)

    def test_generic_economic_report_new_explicit_release_period(self):
        a = event(self.official, title="Recent Economic Developments (September 2026)", summary=self.summary)
        b = event(self.official, title="Recent Economic Developments (October 2026)", summary=self.summary)
        first = evaluate_global_coverage([a], evaluated_at=NOW)
        e = evaluate_global_coverage([b], evaluated_at=NOW, editorial_history=history(first))
        self.assertEqual(e.clusters[0].novelty.status, NoveltyStatus.PERIODIC_NEW_OCCURRENCE)
        self.assertTrue(e.selected_clusters)

    def test_new_fetch_time_alone_does_not_create_novelty(self):
        a = event(title="ECB holds rates", summary="ECB held policy rates at 3 percent.")
        first = evaluate_global_coverage([a], evaluated_at=NOW)
        b = replace(a, retrieved_at=NOW+timedelta(hours=4))
        later = evaluate_global_coverage([b], evaluated_at=NOW+timedelta(hours=4), editorial_history=history(first))
        self.assertEqual(later.clusters[0].novelty.status, NoveltyStatus.UNCHANGED)
        self.assertFalse(later.selected_clusters)

    def test_incomplete_reconstruction_is_unknown_not_proven_unchanged(self):
        raw = {"title":"KOSPI triggers circuit breaker", "summary":"", "url":"https://fixture.invalid/a", "published_at":NOW,
               "evidence_origin":"RECONSTRUCTED_ASSUMPTION"}
        a = normalize_source_item(raw, self.official, retrieved_at=NOW)
        first = evaluate_global_coverage([a], evaluated_at=NOW)
        later = evaluate_global_coverage([a], evaluated_at=NOW+timedelta(hours=4), editorial_history=history(first))
        self.assertEqual(later.clusters[0].novelty.status, NoveltyStatus.UNKNOWN)
        self.assertEqual(later.clusters[0].novelty.reason, "incomplete_event_identity_evidence")
        self.assertFalse(later.selected_clusters)

    def test_same_title_new_publication_time_not_sufficient_for_new_session(self):
        a = event(title="KOSPI triggers circuit breaker", summary="")
        first = evaluate_global_coverage([a], evaluated_at=NOW)
        b = event(title=a.normalized_headline, summary="", published_at=NOW+timedelta(days=1))
        later = evaluate_global_coverage([b], evaluated_at=NOW+timedelta(days=1), editorial_history=history(first))
        self.assertEqual(later.clusters[0].novelty.status, NoveltyStatus.UNKNOWN)
        self.assertFalse(later.selected_clusters)

    def test_genuine_followup_policy_decision_same_cluster(self):
        title = "ECB Policy Decision"
        first = evaluate_global_coverage([event(title=title, summary="ECB held policy rates at 3 percent.")], evaluated_at=NOW)
        later = evaluate_global_coverage([event(title=title, summary="ECB cut policy rates to 2 percent.")], evaluated_at=NOW+timedelta(hours=4), editorial_history=history(first))
        self.assertEqual(first.clusters[0].cluster_id, later.clusters[0].cluster_id)
        self.assertEqual(later.clusters[0].novelty.status, NoveltyStatus.MATERIAL_UPDATE)
        self.assertTrue(later.selected_clusters)

    def test_speech_repeated_tomorrow_with_same_source_evidence_suppressed(self):
        a = event(title="ECB policy statement", summary="ECB held policy rates at 3 percent.")
        first = evaluate_global_coverage([a], evaluated_at=NOW)
        later = evaluate_global_coverage([replace(a, retrieved_at=NOW+timedelta(days=1))], evaluated_at=NOW+timedelta(days=1), editorial_history=history(first))
        self.assertEqual(later.clusters[0].novelty.status, NoveltyStatus.UNCHANGED)
        self.assertFalse(later.selected_clusters)

    def test_old_editorial_memory_cannot_assert_complete_factual_identity(self):
        a = event(title="ECB holds rates", summary="ECB held policy rates at 3 percent.")
        first = evaluate_global_coverage([a], evaluated_at=NOW)
        records = history(first)
        records[0]["selected_event_audits"][0]["editorial_memory"].pop("identity_evidence_complete")
        e = evaluate_global_coverage([a], evaluated_at=NOW, editorial_history=records)
        self.assertEqual(e.clusters[0].novelty.status, NoveltyStatus.UNKNOWN)

    def test_previous_editorial_version_loads_without_resetting_history(self):
        first = evaluate_global_coverage([event(title="ECB holds rates", summary="ECB held policy rates at 3 percent.")], evaluated_at=NOW)
        records = history(first)
        memory = records[0]["selected_event_audits"][0]["editorial_memory"]
        memory["schema_version"] = "gate2.4b"
        memory.pop("identity_evidence_complete")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"shadow.json"
            path.write_text(json.dumps({"editorial_state_version":"gate2.4b", "records":records}))
            loaded = CoverageObservationStore.load(path)
            self.assertIsNone(loaded.load_error)
            self.assertEqual(loaded.records, records)
        e = evaluate_global_coverage([event(title="ECB holds rates", summary="ECB held policy rates at 3 percent.")], evaluated_at=NOW, editorial_history=loaded.records)
        self.assertEqual(e.clusters[0].novelty.status, NoveltyStatus.UNKNOWN)

    def test_unsupported_resolution_does_not_establish_material_update(self):
        first = evaluate_global_coverage([event(title="ECB holds rates", summary="The policy rate is 3 percent.")], evaluated_at=NOW)
        e = evaluate_global_coverage([event(title="ECB holds rates", summary="An unrelated issue was resolved.")], evaluated_at=NOW, editorial_history=history(first))
        self.assertEqual(e.clusters[0].novelty.status, NoveltyStatus.UNKNOWN)

    def test_speculative_numeric_change_not_material_update(self):
        title = "ECB policy decision"
        first = evaluate_global_coverage([event(title=title, summary="ECB held policy rates at 3 percent.")], evaluated_at=NOW)
        e = evaluate_global_coverage([event(title=title, summary="Analysts expect ECB could cut policy rates to 2 percent.")], evaluated_at=NOW, editorial_history=history(first))
        self.assertEqual(e.clusters[0].novelty.status, NoveltyStatus.UNKNOWN)
        self.assertFalse(e.selected_clusters)

    def test_unanchored_teaser_not_a_new_financial_development(self):
        a, e = self.assessment(title="Analysis: Everyone expects the Fed to hold rates in October. Kevin Warsh could surprise us all", summary="")
        self.assertEqual(a.editorial.relevance.relevance_class, RelevanceClass.CONTEXT_ONLY)
        self.assertFalse(e.selected_clusters)
        # Concrete conditional intelligence remains possible without a blacklist.
        b = event(title="Fed could surprise markets with a rate cut", summary="")
        self.assertTrue(evaluate_global_coverage([b], evaluated_at=NOW).selected_clusters)

    def test_known_incorrect_retained_titles_do_not_reenter(self):
        incorrect = [r for r in compare_retained_titles() if r["label"] == "INCORRECT"]
        self.assertEqual(len(incorrect), 7)
        self.assertFalse(any(r["new_eligible"] for r in incorrect))

    def test_safe_validator_and_selection_bridge_no_delivery_or_persistence(self):
        from contextlib import ExitStack
        from app.fiona_coverage_authority import resolve_coverage_authority, coverage_events
        from app.fiona_source_registry import CoverageProfile, coverage_profile_from_env
        blocked = ("app.fiona_state.atomic_write_json", "app.fiona_memory.FionaMemory.save",
                   "app.fiona_scheduler.SchedulerLedger.save", "app.fiona_coverage_runtime.CoverageObservationStore.save",
                   "app.telegram_service.telegram_request", "app.telegram_service.telegram_classified_request")
        with ExitStack() as stack:
            guards = [stack.enter_context(patch(name, side_effect=AssertionError("production side effect forbidden"))) for name in blocked]
            registry = load_source_registry()
            def fetch(spec, timeout):
                return [{"title": "Recent Economic Developments", "summary": self.summary,
                         "published_at": NOW, "url": "https://fixture.invalid/"+spec.source_id}]
            result = validate_global_coverage_runtime(registry=registry, fetcher=fetch, evaluated_at=NOW)
            self.assertTrue(result["ok"])
            self.assertTrue(result["selected_event_audits"])
            def evaluator(selection_sink):
                a = event(self.official, title="Recent Economic Developments", summary=self.summary)
                e = evaluate_global_coverage([a], evaluated_at=NOW)
                selection_sink(e)
                return {"ok": True}
            legacy = resolve_coverage_authority(CoverageProfile.LEGACY, evaluator)
            glob = resolve_coverage_authority(CoverageProfile.GLOBAL_631, evaluator)
            self.assertEqual(legacy.selection_authority, "legacy")
            self.assertFalse(legacy.clusters)
            self.assertEqual(glob.selection_authority, "global_631")
            self.assertTrue(coverage_events(glob, NOW))
            self.assertEqual(coverage_profile_from_env({}), CoverageProfile.LEGACY)
            for guard in guards:
                guard.assert_not_called()


def case_test(case):
    def run(self):
        official = source("boe_news" if case.name == "artwork" else "fixture_official", source_type="Official", tier=SourceTier.TIER_1)
        a = event(official, title=case.title, summary="Inflation is revised to 4 percent." if case.name == "followup" else "")
        prior = []
        pool = [a]
        if case.name in {"unchanged", "followup", "periodic"}:
            previous = a if case.name == "unchanged" else event(official, title=case.title.replace("September", "August") if case.name == "periodic" else case.title, summary="Inflation is 3 percent." if case.name == "followup" else "")
            prior = history(evaluate_global_coverage([previous], evaluated_at=NOW-timedelta(minutes=5)))
        if case.name in {"corroboration", "syndication"}:
            partner = source("independent", group=official.independence_group if case.name == "syndication" else "other_owner")
            pool.append(event(partner, title=case.title, summary="Independent reporting."))
        e = evaluate_global_coverage(pool, evaluated_at=NOW, editorial_history=prior)
        self.assertEqual(bool(e.selected_clusters), case.eligible, case.reason)
        self.assertEqual(a.editorial.assertion.assertion_type.value, case.assertion)
        self.assertEqual(a.editorial.relevance.relevance_class.value, case.relevance)
        self.assertEqual(a.event_region.value, case.region)
        self.assertEqual(a.material_override, case.override)
        self.assertEqual(e.clusters[0].novelty.status.value, case.novelty)
    return run


for fixture_case in CASES:
    setattr(EditorialContractTests, "test_corpus_"+fixture_case.name, case_test(fixture_case))


if __name__ == "__main__":
    unittest.main()
