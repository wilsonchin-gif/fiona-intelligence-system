from __future__ import annotations

import copy
import io
import json
import tempfile
import unittest
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from unittest.mock import Mock, patch

from test_fiona_v3_1_gate2 import NOW, event, source, synthetic_regional_events
from app.fiona_coverage_authority import coverage_events, resolve_coverage_authority
from app.fiona_coverage_runtime import run_global_coverage_shadow
from app.fiona_global_coverage import (
    cluster_events, collect_source, evaluate_global_coverage, infer_event_region,
    materiality_for, rank_coverage_clusters, SourceHealthStatus,
)
from app.fiona_source_registry import CoverageProfile, EventRegion, SourceRegistry, SourceTier, coverage_profile_from_env
from app.fiona_shadow_audit import emit_occurrence_audits, scheduler_log_projection, selected_event_audits
from app.fiona_runtime import build_payload, run_once
from app.fiona_surface_validation import en_us_fixture_snapshot


class EditorialRegionTests(unittest.TestCase):
    def check(self, title, expected, publisher=EventRegion.GREATER_CHINA):
        self.assertEqual(infer_event_region(title, "", source(region=publisher)), expected)

    def test_ukraine_from_china_publisher(self):
        self.check("At least 33 dead in Russian bomb blast in east Ukraine stronghold", EventRegion.REST_OF_WORLD)

    def test_pboc_from_global_publisher(self):
        self.check("PBOC announces policy rate cut", EventRegion.GREATER_CHINA, EventRegion.GLOBAL)

    def test_hk_from_us_publisher(self):
        self.check("Hong Kong regulator introduces capital requirements", EventRegion.GREATER_CHINA, EventRegion.US_EU)

    def test_ecb_from_asia_publisher(self):
        self.check("ECB holds policy rates unchanged", EventRegion.US_EU)

    def test_boj_from_europe_publisher(self):
        self.check("BOJ raises interest rates", EventRegion.REST_OF_WORLD, EventRegion.US_EU)

    def test_sec_from_global_publisher(self):
        self.check("US SEC announces enforcement action", EventRegion.US_EU, EventRegion.GLOBAL)

    def test_unresolved_remains_unknown(self):
        for publisher in EventRegion:
            self.check("Unspecified development", EventRegion.UNKNOWN, publisher)

    def test_publisher_never_overrides(self):
        for publisher in EventRegion:
            self.check("Japan changes monetary policy", EventRegion.REST_OF_WORLD, publisher)

    def test_official_jurisdiction_identity(self):
        official = source("hkma", source_type="Official", tier=SourceTier.TIER_1)
        self.assertEqual(infer_event_region("Release of official statistics", "", official), EventRegion.GREATER_CHINA)

    def test_global_cross_region_not_quota_assigned(self):
        self.check("Global energy supply disruption", EventRegion.GLOBAL)
        self.check("China and United States tariff negotiations", EventRegion.GLOBAL)


class EditorialMaterialityTests(unittest.TestCase):
    def score(self, title, tier=SourceTier.TIER_1):
        return materiality_for(title, "", source(tier=tier), "macro_policy", ("rates", "equities"))

    def test_rate_decision_high(self):
        self.assertGreaterEqual(self.score("Bank rate maintained at 3.75 percent")[0], 75)

    def test_hotel_room_rates_are_not_monetary_policy(self):
        score = materiality_for("China hotel room rates disappoint during golden week", "Hotel operators lower room rates amid a tourism boom.", source(), "macro_policy", ("equities", "fx"))[0]
        self.assertLess(score, 60)

    def test_fed_cuts_rates_is_actual_policy_action(self):
        self.assertGreaterEqual(self.score("Fed cuts rates by a quarter point")[0], 75)

    def test_financial_rate_context_not_lost(self):
        for title in ("Interest rates maintained unchanged", "Policy rates hold steady", "Treasury yields surge as rate expectations shift", "Mortgage rates jump to a two-decade high"):
            with self.subTest(title=title):
                self.assertGreaterEqual(self.score(title)[0], 65)

    def test_hospitality_price_variants_do_not_become_policy_rates(self):
        for title in ("Hotels cut room rates as occupancy falls", "Hospitality pricing drops amid tourism boom", "China hotel rates lower despite holiday travel"):
            with self.subTest(title=title):
                self.assertLess(self.score(title)[0], 60)

    def test_inflation_surprise_high(self):
        self.assertGreaterEqual(self.score("US inflation surprise raises liquidity risks")[0], 80)

    def test_systemic_financial_event_high(self):
        self.assertGreaterEqual(self.score("Systemic financial crisis triggers emergency response")[0], 90)

    def test_geopolitical_market_shock_high(self):
        self.assertGreaterEqual(self.score("War breaks out with global energy supply disruption")[0], 90)

    def test_calendar_low(self):
        self.assertLess(self.score("Monetary Policy Committee dates for 2027")[0], 40)

    def test_personnel_low(self):
        self.assertLess(self.score("Senior appointment at central bank")[0], 40)

    def test_educational_fraud_low(self):
        self.assertLess(self.score("Scam alert related to banks")[0], 40)

    def test_tier_is_not_materiality(self):
        for title in ("Routine appointment", "Policy rate decision", "Unspecified notice"):
            self.assertEqual(self.score(title, SourceTier.TIER_1)[0], self.score(title, SourceTier.TIER_3)[0])

    def test_floor_rejects_regional_filler(self):
        pool = [event(source("hkma", region=EventRegion.GREATER_CHINA, tier=SourceTier.TIER_1),
                      title="Scam alert related to banks", summary="")]
        self.assertEqual(evaluate_global_coverage(pool, evaluated_at=NOW).selected_clusters, [])

    def test_educational_copy_cannot_borrow_systemic_boilerplate(self):
        self.assertEqual(materiality_for("Fraud awareness educational notice", "Avoid a bank run and systemic financial risk.", source(), "macro_policy", ("rates",))[0], 18)

    def test_regional_adjustment_is_bounded(self):
        from app.fiona_global_coverage import base_ranking_score
        e = evaluate_global_coverage(synthetic_regional_events({EventRegion.US_EU: 10, EventRegion.GREATER_CHINA: 10, EventRegion.REST_OF_WORLD: 10}), evaluated_at=NOW)
        for c in e.selected_clusters:
            self.assertGreaterEqual(c.ranking_score-base_ranking_score(c), -1.200001)
            self.assertLessEqual(c.ranking_score-base_ranking_score(c), 4.800001)

    def test_regional_weight_cannot_bridge_material_gap(self):
        strong = event(title="United States liquidity repricing", materiality=80, override=False)
        weak = event(source("other", region=EventRegion.GREATER_CHINA), title="China liquidity repricing", materiality=50, override=False)
        e = evaluate_global_coverage([strong, weak], evaluated_at=NOW, limit=1)
        self.assertEqual(e.selected_clusters[0].events[0].event_id, strong.event_id)

    def test_equal_quality_keeps_dynamic_631(self):
        e = evaluate_global_coverage(synthetic_regional_events({EventRegion.US_EU: 10, EventRegion.GREATER_CHINA: 10, EventRegion.REST_OF_WORLD: 10}), evaluated_at=NOW)
        self.assertEqual(e.metrics["regional_selected_counts"]["US_EU"], 6)
        self.assertEqual(e.metrics["regional_selected_counts"]["GREATER_CHINA"], 3)
        self.assertEqual(e.metrics["regional_selected_counts"]["REST_OF_WORLD"], 1)

    def test_no_hard_quota(self):
        e = evaluate_global_coverage(synthetic_regional_events({EventRegion.REST_OF_WORLD: 10}), evaluated_at=NOW)
        self.assertEqual(len(e.selected_clusters), 10)

    def test_override_representative_cases(self):
        for title in ("ECB emergency rate cut", "Systemic banking crisis", "War breaks out", "SEC major regulatory ban"):
            with self.subTest(title=title):
                # The score-only helper lacks provenance/time and must not authorize delivery priority.
                self.assertGreaterEqual(self.score(title)[0], 85)
                a = event(source(source_type="Official", tier=SourceTier.TIER_1), title=title, summary="")
                self.assertTrue(a.editorial.override_eligible)
                self.assertEqual(a.override_reason, "supported_current_material_financial_event")

    def test_override_can_exceed_regional_target(self):
        e = evaluate_global_coverage([event(title="BOJ emergency rate hike", summary="")], evaluated_at=NOW)
        self.assertTrue(e.selected_clusters[0].material_override)
        self.assertEqual(e.metrics["regional_selected_share"]["REST_OF_WORLD"], 1)

    def test_weak_cannot_override(self):
        e = evaluate_global_coverage([event(title="Routine appointment", materiality=18, override=True)], evaluated_at=NOW)
        self.assertFalse(e.selected_clusters)

    def test_override_cannot_bypass_validity(self):
        for item in (event(published_at=NOW-timedelta(days=20), override=True),
                     event(published_at=None, override=True),
                     replace(event(override=True), normalized_headline="")):
            with self.subTest(item=item.freshness):
                self.assertFalse(evaluate_global_coverage([item], evaluated_at=NOW).selected_clusters)


class EditorialIndependenceTests(unittest.TestCase):
    def official(self):
        return source("official", source_type="Official", tier=SourceTier.TIER_1)

    def test_official_and_independent_media_one_cluster(self):
        a = event(self.official(), title="ECB rate decision holds rates unchanged", summary="Official vote announced.")
        b = event(source("media"), title="ECB rate decision leaves rates unchanged", summary="Independent reporting on the decision.")
        clusters, _ = cluster_events([a, b])
        self.assertEqual(len(clusters), 1)
        self.assertEqual(clusters[0].independent_source_count, 2)

    def test_syndication_no_confirmation_inflation(self):
        snippet = "The central bank monetary policy decision was reported in an identical syndicated copy distributed widely." * 2
        c, _ = cluster_events([event(self.official(), summary=snippet), event(source("media"), summary=snippet)])
        self.assertEqual(c[0].independent_source_count, 1)

    def test_same_owner_no_inflation(self):
        c, _ = cluster_events([event(source("one", group="owner")), event(source("two", group="owner"))])
        self.assertEqual(c[0].independent_source_count, 1)

    def test_unrelated_similar_events_separate(self):
        c, _ = cluster_events([event(title="ECB raises policy rate", summary="Euro area decision"),
                               event(source("boj"), title="BOJ raises policy rate", summary="Japan decision")])
        self.assertEqual(len(c), 2)

    def test_primary_single_source_valid_and_visible(self):
        e = evaluate_global_coverage([event(self.official())], evaluated_at=NOW)
        r = selected_event_audits(e)["selected_event_audits"][0]
        self.assertEqual(r["confirmation_sufficiency"], "authoritative_primary_source")

    def test_secondary_is_not_primary(self):
        e = evaluate_global_coverage([event(source(tier=SourceTier.TIER_1))], evaluated_at=NOW)
        self.assertEqual(selected_event_audits(e)["selected_event_audits"][0]["confirmation_sufficiency"], "single_secondary_source")

    def test_multi_confirmation_is_visible(self):
        e = evaluate_global_coverage([event(self.official()), event(source("independent"))], evaluated_at=NOW)
        self.assertEqual(selected_event_audits(e)["selected_event_audits"][0]["confirmation_sufficiency"], "multi_independent_confirmation")


class BoundedLoggingTests(unittest.TestCase):
    def evaluation(self):
        pool = synthetic_regional_events({EventRegion.US_EU: 10, EventRegion.GREATER_CHINA: 10, EventRegion.REST_OF_WORLD: 10})
        return evaluate_global_coverage(pool * 20, evaluated_at=NOW)

    def test_aggregate_and_selected_bounded(self):
        e = self.evaluation()
        calls = Mock()
        emit_occurrence_audits({"coverage_shadow": {**e.metrics, **selected_event_audits(e), "source_health": []}}, "real", calls)
        rows = [json.loads(c.args[0]) for c in calls.call_args_list]
        self.assertEqual(len(rows), 13)
        self.assertEqual(sum(r["event"] == "fionaGlobalCoverageShadow" for r in rows), 1)
        self.assertEqual(sum(r["event"] == "fionaShadowSelectedEvent" for r in rows), 10)
        self.assertEqual(rows[0]["candidate_events"], 600)

    def test_no_candidate_body_credentials(self):
        marker = "PRIVATE_SOURCE_BODY_" * 100
        e = evaluate_global_coverage([event(summary=marker)], evaluated_at=NOW)
        calls = Mock()
        emit_occurrence_audits({"coverage_shadow": {**e.metrics, **selected_event_audits(e)}}, "real", calls)
        log = "".join(c.args[0] for c in calls.call_args_list)
        self.assertNotIn(marker, log)
        self.assertNotIn("news.example", log)
        self.assertNotIn("original_text", log)

    def test_cycle_projection_does_not_mutate_archive(self):
        original = {"occurrence_results": [{"run_status": {"coverage_shadow": {**selected_event_audits(self.evaluation()), "ok": True}}}]}
        before = copy.deepcopy(original)
        result = scheduler_log_projection(original)
        self.assertEqual(original, before)
        self.assertNotIn("normalized_headline", json.dumps(result))

    def test_log_credentials_redacted(self):
        fake = "123456789:" + "x"*35
        e = self.evaluation()
        e.selected_clusters[0].normalized_headline = "Release " + fake + " API_KEY=fake-private-value"
        calls = Mock()
        emit_occurrence_audits({"coverage_shadow": selected_event_audits(e)}, "real", calls)
        output = "".join(c.args[0] for c in calls.call_args_list)
        self.assertNotIn(fake, output)
        self.assertNotIn("fake-private-value", output)

    def test_selected_logs_cap_without_truncating_archive(self):
        e = self.evaluation()
        e.selected_clusters *= 4
        audit = selected_event_audits(e)
        calls = Mock()
        emit_occurrence_audits({"coverage_shadow": audit}, "real", calls)
        self.assertEqual(calls.call_count, 13)
        self.assertEqual(len(audit["selected_event_audits"]), 40)


class CoverageAuthorityTests(unittest.TestCase):
    def setUp(self):
        self.e = evaluate_global_coverage([event()], evaluated_at=NOW)

    def evaluator(self, **kwargs):
        kwargs["selection_sink"](self.e)
        return {"ok": True, **self.e.metrics, **selected_event_audits(self.e)}

    def test_legacy_authority_exact(self):
        a = resolve_coverage_authority(CoverageProfile.LEGACY, self.evaluator)
        self.assertEqual(a.selection_authority, "legacy")
        self.assertFalse(a.fallback_used)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            baseline = build_payload(en_us_fixture_snapshot(), NOW, root/"a.json", "market-news", "en-US")
            actual = build_payload(en_us_fixture_snapshot(), NOW, root/"b.json", "market-news", "en-US", a)
            self.assertEqual(baseline.brief.render_text(), actual.brief.render_text())
            self.assertEqual([e.to_dict() for e in baseline.events], [e.to_dict() for e in actual.events])

    def test_global_authority_consumed(self):
        a = resolve_coverage_authority(CoverageProfile.GLOBAL_631, self.evaluator)
        with tempfile.TemporaryDirectory() as directory:
            payload = build_payload(en_us_fixture_snapshot(), NOW, Path(directory)/"memory.json", "market-news", "en-US", a)
        self.assertEqual([e.event_id for e in payload.events], [c.cluster_id for c in self.e.selected_clusters])
        self.assertEqual(a.metrics()["selection_authority"], "global_631")
        self.assertEqual(a.metrics()["selected_cluster_count"], 1)

    def test_invalid_profile_legacy(self):
        self.assertEqual(coverage_profile_from_env({"FIONA_COVERAGE_PROFILE": "bad"}), CoverageProfile.LEGACY)

    def test_operational_failure_once(self):
        failed = Mock(side_effect=TimeoutError("private endpoint omitted"))
        a = resolve_coverage_authority(CoverageProfile.GLOBAL_631, failed)
        failed.assert_called_once()
        self.assertEqual(a.selection_authority, "legacy")
        self.assertTrue(a.fallback_used)
        self.assertEqual(a.fallback_reason, "coverage_engine_operational_failure")

    def test_malformed_result_fallback(self):
        for result in (None, {"ok": True}, {"ok": False}):
            with self.subTest(result=result):
                self.assertTrue(resolve_coverage_authority(CoverageProfile.GLOBAL_631, Mock(return_value=result)).fallback_used)

    def test_empty_underweight_not_failure(self):
        self.e = evaluate_global_coverage([], evaluated_at=NOW)
        a = resolve_coverage_authority(CoverageProfile.GLOBAL_631, self.evaluator)
        self.assertEqual(a.selection_authority, "global_631")
        self.assertFalse(a.fallback_used)

    def test_one_source_timeout_not_fallback(self):
        registry = SourceRegistry("3.1", (source("good", legacy=True), source("hkma", source_type="Official")))
        def timeout(_s, _t):
            raise TimeoutError("bounded")
        with tempfile.TemporaryDirectory() as directory:
            a = resolve_coverage_authority(CoverageProfile.GLOBAL_631, run_global_coverage_shadow,
                legacy_items=[{"source_id": "good", "title": "Federal Reserve policy decision", "published_at": NOW}],
                output_dir=Path(directory), evaluated_at=NOW, registry=registry, fetcher=timeout)
        self.assertFalse(a.fallback_used)
        self.assertEqual(a.selection_authority, "global_631")
        self.assertIn("timeout", [h["status"] for h in a.shadow["source_health"]])

    def test_complete_source_outage_is_operational_failure(self):
        from app.fiona_global_coverage import SourceHealth
        self.e = evaluate_global_coverage([], evaluated_at=NOW,
            source_health=[SourceHealth("hkma", SourceHealthStatus.TIMEOUT, NOW)])
        a = resolve_coverage_authority(CoverageProfile.GLOBAL_631, self.evaluator)
        self.assertTrue(a.fallback_used)
        self.assertEqual(a.fallback_reason, "all_sources_unavailable")

    def test_bad_selection_fallback(self):
        self.e.selected_clusters[0].stale = True
        a = resolve_coverage_authority(CoverageProfile.GLOBAL_631, self.evaluator)
        self.assertTrue(a.fallback_used)
        self.assertEqual(a.fallback_reason, "invalid_authoritative_selection")

    def test_global_projection_is_not_alert_execution(self):
        a = resolve_coverage_authority(CoverageProfile.GLOBAL_631, self.evaluator)
        with patch("app.fiona_engine.FionaAlertEngine.process", side_effect=AssertionError("no second engine")):
            self.assertEqual(len(coverage_events(a, NOW)), 1)

    def test_runtime_single_pipeline_and_safe_profiles(self):
        for profile in ("legacy", "global_631"):
            with self.subTest(profile=profile), tempfile.TemporaryDirectory() as directory, \
                 patch.dict("os.environ", {"FIONA_COVERAGE_PROFILE": profile, "FIONA_OUTPUT_LOCALE": "en-US", "FIONA_MARKET_NEWS_MODE": "image"}), \
                 patch("app.fiona_runtime.run_global_coverage_shadow_safe", side_effect=self.evaluator) as evaluator, \
                 patch("app.fiona_runtime.telegram_send_message") as text, \
                 patch("app.fiona_runtime.telegram_send_photo") as photo, \
                 patch("app.fiona_runtime.telegram_send_document") as document:
                root = Path(directory)
                ledger = root/"fiona_scheduler_ledger.json"
                ledger.write_bytes(b"UNCHANGED")
                status = run_once(root, "market-news", False, "UTC", lambda _: en_us_fixture_snapshot())
                self.assertTrue(status["ok"], status["errors"])
                evaluator.assert_called_once()
                for sender in (text, photo, document): sender.assert_not_called()
                self.assertEqual(status["selection_authority"], profile)
                self.assertFalse(status["coverage_fallback_used"])
                self.assertEqual(ledger.read_bytes(), b"UNCHANGED")
                self.assertEqual(list(root.glob("*occurrence*")), [])

    def test_send_uses_one_existing_renderer_path(self):
        with tempfile.TemporaryDirectory() as directory, \
             patch.dict("os.environ", {"FIONA_COVERAGE_PROFILE": "global_631", "FIONA_OUTPUT_LOCALE": "en-US", "FIONA_ALERT_ENABLED": "0"}), \
             patch("app.fiona_runtime.run_global_coverage_shadow_safe", side_effect=self.evaluator), \
             patch("app.fiona_runtime.push_market_news", return_value={"ok": True}) as delivery, \
             patch("app.fiona_runtime.push_text") as extra:
            status = run_once(Path(directory), "market-news", True, "UTC", lambda _: en_us_fixture_snapshot())
        self.assertTrue(status["ok"])
        delivery.assert_called_once()
        extra.assert_not_called()

    def test_runtime_failure_uses_legacy_once(self):
        with tempfile.TemporaryDirectory() as directory, \
             patch.dict("os.environ", {"FIONA_COVERAGE_PROFILE": "global_631", "FIONA_OUTPUT_LOCALE": "en-US", "FIONA_ALERT_ENABLED": "0"}), \
             patch("app.fiona_runtime.run_global_coverage_shadow_safe", return_value={"ok": False}) as evaluator, \
             patch("app.fiona_runtime.push_market_news", return_value={"ok": True}) as delivery, \
             patch("app.fiona_runtime.push_text") as extra:
            status = run_once(Path(directory), "market-news", True, "UTC", lambda _: en_us_fixture_snapshot())
        self.assertTrue(status["ok"])
        self.assertEqual(status["selection_authority"], "legacy")
        self.assertTrue(status["coverage_fallback_used"])
        self.assertEqual(status["coverage_fallback_reason"], "coverage_engine_operational_failure")
        evaluator.assert_called_once()
        delivery.assert_called_once()
        extra.assert_not_called()

    def test_global_engine_not_called_twice_by_presentation(self):
        from app.fiona_market_news_image import build_market_news_view_model
        with tempfile.TemporaryDirectory() as directory, \
             patch.dict("os.environ", {"FIONA_COVERAGE_PROFILE": "global_631", "FIONA_OUTPUT_LOCALE": "en-US"}), \
             patch("app.fiona_runtime.run_global_coverage_shadow_safe", side_effect=self.evaluator) as evaluator, \
             patch("app.fiona_runtime.build_market_news_view_model", wraps=build_market_news_view_model) as model:
            status = run_once(Path(directory), "market-news", False, "UTC", lambda _: en_us_fixture_snapshot())
        self.assertTrue(status["ok"])
        evaluator.assert_called_once()
        model.assert_called_once()

    def test_duplicate_authoritative_ids_fail_validation(self):
        self.e.selected_clusters *= 2
        a = resolve_coverage_authority(CoverageProfile.GLOBAL_631, self.evaluator)
        self.assertTrue(a.fallback_used)
        self.assertEqual(a.fallback_reason, "invalid_authoritative_selection")

    def test_other_briefs_do_not_enter_coverage(self):
        for brief in ("morning", "evening", "daily", "weekly"):
            with self.subTest(brief=brief), tempfile.TemporaryDirectory() as directory, \
                 patch.dict("os.environ", {"FIONA_COVERAGE_PROFILE": "global_631", "FIONA_OUTPUT_LOCALE": "en-US"}), \
                 patch("app.fiona_runtime.run_global_coverage_shadow_safe") as evaluator:
                status = run_once(Path(directory), brief, False, "UTC", lambda _: en_us_fixture_snapshot())
                self.assertTrue(status["ok"], status["errors"])
                evaluator.assert_not_called()

    def test_profile_does_not_change_other_brief_content(self):
        for brief in ("morning", "evening", "daily", "weekly"):
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                with patch.dict("os.environ", {"FIONA_COVERAGE_PROFILE": "legacy"}):
                    a = build_payload(en_us_fixture_snapshot(), NOW, root/"a.json", brief, "en-US")
                with patch.dict("os.environ", {"FIONA_COVERAGE_PROFILE": "global_631"}):
                    b = build_payload(en_us_fixture_snapshot(), NOW, root/"b.json", brief, "en-US")
                self.assertEqual(a.brief.render_text(), b.brief.render_text())
                self.assertEqual(a.alert_messages, b.alert_messages)

    def test_actual_renderer_both_profiles_no_external_side_effects(self):
        from app.fiona_market_news_image import build_market_news_view_model, compose_market_news_caption
        from app.fiona_market_news_delivery import render_for_media, validate_market_news_png, TelegramMediaMode
        from app.fiona_locale import contains_cjk
        for profile in CoverageProfile:
            with self.subTest(profile=profile), tempfile.TemporaryDirectory() as directory, \
                 patch("app.telegram_service.send_photo_with_caption") as tg:
                root = Path(directory)
                authority = resolve_coverage_authority(profile, self.evaluator)
                payload = build_payload(en_us_fixture_snapshot(), NOW, root/"memory.json", "market-news", "en-US", authority)
                vm = build_market_news_view_model(payload.snapshot, payload.events, payload.narratives, NOW, "en-US")
                caption = compose_market_news_caption(vm)
                self.assertFalse(contains_cjk(caption))
                png = render_for_media(vm, root/"validation.png", TelegramMediaMode.PHOTO)
                valid = validate_market_news_png(png, expected_size=(1440, 1800))
                self.assertEqual((valid.width, valid.height), (1440, 1800))
                self.assertLess(valid.size_bytes, 1500000)
                tg.assert_not_called()
                self.assertFalse((root/"fiona_scheduler_ledger.json").exists())

    def test_hkma_timeout_bound_and_isolation(self):
        seen = []
        def timeout(spec, seconds):
            seen.append(seconds)
            raise TimeoutError("isolated")
        events, health = collect_source(source("hkma"), retrieved_at=NOW, fetcher=timeout)
        self.assertEqual(seen, [12])
        self.assertFalse(events)
        self.assertEqual(health.status, SourceHealthStatus.TIMEOUT)


if __name__ == "__main__":
    unittest.main()
