from __future__ import annotations

import copy
import hashlib
import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, patch

from app.fiona_briefing import BRIEF_SCHEDULES, FionaBriefKind
from app.fiona_coverage_runtime import (
    CoverageObservationStore,
    normalize_legacy_candidates,
    run_global_coverage_shadow,
    run_global_coverage_shadow_safe,
    validate_global_coverage_runtime,
)
from app.fiona_global_coverage import (
    FreshnessStatus,
    SourceHealthStatus,
    cluster_events,
    collect_source,
    evaluate_global_coverage,
    infer_event_region,
    normalize_source_item,
    parse_json_payload,
    parse_rss_payload,
    rank_coverage_clusters,
)
from app.fiona_locale import contains_cjk
from app.fiona_market_news_delivery import TelegramMediaMode, expected_image_size
from app.fiona_runtime import run_once
from app.fiona_scheduler import ACTION_DEFER, ACTION_SEND, ACTION_SUPPRESS
from app.fiona_source_registry import (
    CoverageProfile,
    EventRegion,
    SourceRegistry,
    SourceSpec,
    SourceTier,
    coverage_profile_from_env,
    load_source_registry,
    source_spec_from_dict,
    validate_registry,
)
from app.fiona_surface_validation import (
    build_en_us_user_surface_outputs,
    en_us_fixture_snapshot,
)


NOW = datetime(2026, 9, 3, 12, 0, tzinfo=timezone.utc)


def source(
    source_id: str = "source_a",
    *,
    region: EventRegion = EventRegion.US_EU,
    tier: SourceTier = SourceTier.TIER_2,
    group: str | None = None,
    enabled: bool = True,
    legacy: bool = False,
    shadow: bool = True,
    language: str = "en-US",
    source_type: str = "MajorMedia",
) -> SourceSpec:
    return SourceSpec(
        source_id=source_id,
        name=source_id.replace("_", " ").title(),
        publisher=source_id.replace("_", " ").title(),
        publisher_region=region,
        default_event_region=region,
        language=language,
        tier=tier,
        independence_group=group or source_id,
        source_type=source_type,
        markets=("equities",),
        content_categories=("market",),
        retrieval_method="rss",
        endpoint=f"https://example.com/{source_id}.xml",
        enabled=enabled,
        legacy_enabled=legacy,
        shadow_enabled=shadow,
        market_bucket="us" if legacy else "",
    )


def event(
    source_spec: SourceSpec | None = None,
    *,
    title: str = "Federal Reserve policy decision changes market liquidity",
    summary: str = "The policy decision affects rates, equities and the dollar.",
    url: str | None = None,
    published_at: datetime | str | None = NOW,
    materiality: int | None = None,
    cross_market: int | None = None,
    override: bool | None = None,
):
    spec = source_spec or source()
    raw = {
        "title": title,
        "summary": summary,
        "url": url or f"https://news.example/{spec.source_id}/{hashlib.sha256(title.encode()).hexdigest()[:16]}",
        "published_at": published_at.isoformat() if isinstance(published_at, datetime) else published_at,
    }
    normalized = normalize_source_item(raw, spec, retrieved_at=NOW)
    assert normalized is not None
    changes = {}
    if materiality is not None:
        changes["materiality"] = materiality
    if cross_market is not None:
        changes["cross_market_impact"] = cross_market
    if override is not None:
        changes["material_override"] = override
        changes["override_reason"] = "test_material_event" if override else ""
    return replace(normalized, **changes) if changes else normalized


def synthetic_regional_events(
    counts: dict[EventRegion, int],
    *,
    materiality: int = 50,
    tier: SourceTier = SourceTier.TIER_2,
):
    events = []
    unique_markers = (
        "liquidity",
        "inflation",
        "employment",
        "banking",
        "technology",
        "energy",
        "housing",
        "trade",
        "currency",
        "credit",
        "manufacturing",
        "consumer",
    )
    labels = {
        EventRegion.US_EU: "United States",
        EventRegion.GREATER_CHINA: "China",
        EventRegion.REST_OF_WORLD: "Japan",
        EventRegion.GLOBAL: "Global",
        EventRegion.UNKNOWN: "Undetermined",
    }
    for region, count in counts.items():
        for index in range(count):
            spec = source(f"{region.value.lower()}_{index}", region=region, tier=tier)
            item = event(
                spec,
                title=f"{labels[region]} {unique_markers[index % len(unique_markers)]} development",
                summary=f"Evidence concerns {unique_markers[index % len(unique_markers)]} conditions in {labels[region]}.",
                materiality=materiality,
                override=False,
            )
            events.append(
                replace(
                    item,
                    category="market",
                    cross_market_impact=50,
                    narrative_relevance=50,
                    freshness_score=100,
                )
            )
    return events


class SourceRegistryTests(unittest.TestCase):
    def test_01_source_registry_loads(self) -> None:
        registry = load_source_registry()
        self.assertGreaterEqual(len(registry.sources), 15)
        self.assertEqual(registry.schema_version, "3.1")

    def test_02_unique_source_id(self) -> None:
        ids = [item.source_id for item in load_source_registry().sources]
        self.assertEqual(len(ids), len(set(ids)))

    def test_03_valid_region(self) -> None:
        self.assertTrue(all(isinstance(item.default_event_region, EventRegion) for item in load_source_registry().sources))

    def test_04_valid_tier(self) -> None:
        self.assertTrue(all(item.tier in {SourceTier.TIER_1, SourceTier.TIER_2, SourceTier.TIER_3} for item in load_source_registry().sources))

    def test_05_valid_language(self) -> None:
        self.assertTrue(all(item.language and item.language != "und" for item in load_source_registry().sources))

    def test_06_valid_independence_group(self) -> None:
        self.assertTrue(all(item.independence_group for item in load_source_registry().sources))

    def test_07_disabled_source_ignored(self) -> None:
        registry = SourceRegistry("3.1", (source(enabled=False),))
        self.assertEqual(registry.shadow_sources(), ())

    def test_08_missing_metadata_handled(self) -> None:
        item = source_spec_from_dict({"source_id": "minimal", "name": "Minimal", "enabled": False})
        self.assertEqual(item.publisher_region, EventRegion.UNKNOWN)
        self.assertEqual(item.tier, SourceTier.UNKNOWN)
        self.assertEqual(item.language, "und")

    def test_09_source_timeout_safe(self) -> None:
        def timeout(_: SourceSpec, __: int):
            raise TimeoutError("bounded timeout")

        events, health = collect_source(source(), retrieved_at=NOW, fetcher=timeout)
        self.assertEqual(events, [])
        self.assertEqual(health.status, SourceHealthStatus.TIMEOUT)

    def test_10_empty_response_safe(self) -> None:
        events, health = collect_source(source(), retrieved_at=NOW, fetcher=lambda _s, _t: [])
        self.assertEqual(events, [])
        self.assertEqual(health.status, SourceHealthStatus.EMPTY)

    def test_11_invalid_timestamp_safe(self) -> None:
        raw = [{"title": "Valid event with bad timestamp", "url": "https://example.com/a", "published_at": "not-a-date"}]
        events, health = collect_source(source(), retrieved_at=NOW, fetcher=lambda _s, _t: raw)
        self.assertIsNone(events[0].published_at)
        self.assertEqual(events[0].freshness, FreshnessStatus.UNKNOWN)
        self.assertEqual(health.invalid_timestamp_count, 1)


class ProvenanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.spec = source(
            "global_media",
            region=EventRegion.GLOBAL,
            language="zh-CN",
        )
        self.item = normalize_source_item(
            {
                "title": "中国人民银行公布新的流动性安排",
                "summary": "政策将在公开市场操作中实施。",
                "url": "https://example.com/cn-policy?utm_source=test",
                "published_at": NOW.isoformat(),
            },
            self.spec,
            retrieved_at=NOW,
            normalized_headline="PBOC announces a new liquidity arrangement",
            normalized_fact="The measure applies to open-market operations.",
        )
        assert self.item is not None

    def test_12_original_title_preserved(self) -> None:
        self.assertEqual(self.item.source_provenance.original_title, "中国人民银行公布新的流动性安排")

    def test_13_original_language_preserved(self) -> None:
        self.assertEqual(self.item.source_provenance.original_language, "zh-CN")

    def test_14_source_url_preserved(self) -> None:
        self.assertIn("utm_source=test", self.item.source_provenance.source_url)
        self.assertNotIn("utm_source", self.item.canonical_url)

    def test_15_publisher_region_preserved(self) -> None:
        self.assertEqual(self.item.source_provenance.publisher_region, EventRegion.GLOBAL)

    def test_16_event_region_independent_from_publisher_region(self) -> None:
        self.assertEqual(self.item.event_region, EventRegion.GREATER_CHINA)
        self.assertNotEqual(self.item.event_region, self.item.source_provenance.publisher_region)

    def test_17_english_normalization_does_not_destroy_provenance(self) -> None:
        self.assertEqual(self.item.normalized_headline, "PBOC announces a new liquidity arrangement")
        self.assertTrue(contains_cjk(self.item.source_provenance.original_title))


class ClusteringTests(unittest.TestCase):
    def test_18_exact_duplicate_collapses(self) -> None:
        left = event(source("one"), url="https://wire.example/story?utm_source=a")
        right = event(source("two"), url="https://wire.example/story?utm_source=b")
        clusters, diagnostics = cluster_events([left, right])
        self.assertEqual(len(clusters), 1)
        self.assertEqual(diagnostics.duplicate_rejection_count, 1)

    def test_19_same_source_duplicate_collapses(self) -> None:
        spec = source("same")
        left = event(spec, url="https://example.com/1")
        right = event(spec, title="Federal Reserve policy decision changes market liquidity today", url="https://example.com/2")
        clusters, diagnostics = cluster_events([left, right])
        self.assertEqual(len(clusters), 1)
        self.assertEqual(diagnostics.duplicate_rejection_count, 1)

    def test_20_syndicated_duplicate_collapses(self) -> None:
        left = event(source("wire_a", group="shared_wire"), url="https://a.example/story")
        right = event(source("wire_b", group="shared_wire"), url="https://b.example/story")
        clusters, diagnostics = cluster_events([left, right])
        self.assertEqual(len(clusters), 1)
        self.assertEqual(diagnostics.syndication_rejection_count, 1)

    def test_21_independent_confirmation_preserved(self) -> None:
        left = event(source("official", group="official"), url="https://a.example/story")
        right = event(source("media", group="media"), url="https://b.example/story")
        clusters, _ = cluster_events([left, right])
        self.assertEqual(clusters[0].source_count, 2)
        self.assertEqual(clusters[0].independent_source_count, 2)

    def test_22_unrelated_stories_remain_separate(self) -> None:
        left = event(title="Federal Reserve changes its balance sheet policy")
        right = event(source("other"), title="Technology company announces a new chip design")
        clusters, _ = cluster_events([left, right])
        self.assertEqual(len(clusters), 2)

    def test_23_deterministic_cluster_id(self) -> None:
        items = [event(source("a")), event(source("b"))]
        first, _ = cluster_events(items)
        second, _ = cluster_events(items)
        self.assertEqual([item.cluster_id for item in first], [item.cluster_id for item in second])

    def test_24_cluster_result_stable_across_ordering(self) -> None:
        items = [event(source("a")), event(source("b")), event(source("c"), title="Unrelated energy market event")]
        first, _ = cluster_events(items)
        second, _ = cluster_events(list(reversed(items)))
        self.assertEqual([item.cluster_id for item in first], [item.cluster_id for item in second])


class RegionTests(unittest.TestCase):
    def global_source(self) -> SourceSpec:
        return source("global", region=EventRegion.GLOBAL)

    def test_25_us_event(self) -> None:
        self.assertEqual(infer_event_region("Federal Reserve policy update", "", self.global_source()), EventRegion.US_EU)

    def test_26_ecb_event(self) -> None:
        self.assertEqual(infer_event_region("ECB rate decision", "", self.global_source()), EventRegion.US_EU)

    def test_27_pboc_event(self) -> None:
        self.assertEqual(infer_event_region("PBOC liquidity operation", "", self.global_source()), EventRegion.GREATER_CHINA)

    def test_28_hk_event(self) -> None:
        self.assertEqual(infer_event_region("HKMA updates Hong Kong rules", "", self.global_source()), EventRegion.GREATER_CHINA)

    def test_29_taiwan_event(self) -> None:
        self.assertEqual(infer_event_region("Taiwan central bank statement", "", self.global_source()), EventRegion.GREATER_CHINA)

    def test_30_boj_event(self) -> None:
        self.assertEqual(infer_event_region("Bank of Japan policy review", "", self.global_source()), EventRegion.REST_OF_WORLD)

    def test_31_india_event(self) -> None:
        self.assertEqual(infer_event_region("Reserve Bank of India decision", "", self.global_source()), EventRegion.REST_OF_WORLD)

    def test_32_global_publisher_does_not_determine_event_region(self) -> None:
        spec = source("global_publisher", region=EventRegion.GLOBAL)
        self.assertEqual(infer_event_region("BOJ reviews monetary policy", "", spec), EventRegion.REST_OF_WORLD)

    def test_33_unknown_stays_unknown_without_evidence(self) -> None:
        spec = source("unknown", region=EventRegion.UNKNOWN)
        self.assertEqual(infer_event_region("Company publishes quarterly update", "", spec), EventRegion.UNKNOWN)


class RankingTests(unittest.TestCase):
    def test_34_target_favors_approximately_631_when_quality_equal(self) -> None:
        events = synthetic_regional_events(
            {EventRegion.US_EU: 10, EventRegion.GREATER_CHINA: 10, EventRegion.REST_OF_WORLD: 10}
        )
        result = evaluate_global_coverage(events, evaluated_at=NOW)
        self.assertEqual(result.metrics["regional_selected_counts"]["US_EU"], 6)
        self.assertEqual(result.metrics["regional_selected_counts"]["GREATER_CHINA"], 3)
        self.assertEqual(result.metrics["regional_selected_counts"]["REST_OF_WORLD"], 1)

    def test_35_allocation_is_not_hard_quota(self) -> None:
        normal = synthetic_regional_events({EventRegion.US_EU: 2, EventRegion.GREATER_CHINA: 1}, materiality=42)
        material_row = synthetic_regional_events({EventRegion.REST_OF_WORLD: 6}, materiality=78)
        result = evaluate_global_coverage([*normal, *material_row], evaluated_at=NOW)
        self.assertGreater(result.metrics["regional_selected_counts"]["REST_OF_WORLD"], 1)

    def test_36_material_override_works(self) -> None:
        ordinary = event(source("ordinary"), materiality=80, override=False)
        override_event = event(source("override", region=EventRegion.REST_OF_WORLD), title="BOJ emergency intervention", materiality=90, override=True)
        clusters, _ = cluster_events([ordinary, override_event])
        _, selected, _ = rank_coverage_clusters(clusters, limit=1)
        self.assertIn(next(item for item in clusters if item.material_override), selected)

    def test_37_low_quality_region_not_artificially_filled(self) -> None:
        strong = synthetic_regional_events({EventRegion.US_EU: 10}, materiality=55)
        weak = synthetic_regional_events({EventRegion.GREATER_CHINA: 10}, materiality=1, tier=SourceTier.TIER_3)
        result = evaluate_global_coverage([*strong, *weak], evaluated_at=NOW)
        self.assertEqual(result.metrics["regional_selected_counts"]["GREATER_CHINA"], 0)
        self.assertEqual(result.metrics["regional_gap_reason"]["GREATER_CHINA"], "no_qualified_event")

    def test_38_stale_event_rejected(self) -> None:
        stale = event(published_at=NOW - timedelta(days=10), materiality=90, override=False)
        result = evaluate_global_coverage([stale], evaluated_at=NOW)
        self.assertEqual(result.selected_clusters, [])
        self.assertEqual(result.metrics["stale_rejection_count"], 1)

    def test_39_tier1_contributes_higher_authority(self) -> None:
        tier1 = event(source("tier1", tier=SourceTier.TIER_1), title="Official market operation alpha", materiality=50, override=False)
        tier3 = event(source("tier3", tier=SourceTier.TIER_3), title="Specialist market observation beta", materiality=50, override=False)
        clusters, _ = cluster_events([tier1, tier3])
        _, selected, _ = rank_coverage_clusters(clusters, limit=1)
        self.assertEqual(selected[0].source_tier, SourceTier.TIER_1)

    def test_40_duplicate_count_does_not_inflate_confirmation(self) -> None:
        spec = source("duplicate")
        items = [event(spec, url=f"https://example.com/{index}") for index in range(3)]
        clusters, _ = cluster_events(items)
        self.assertEqual(clusters[0].independent_source_count, 1)

    def test_41_independence_contributes_to_confirmation(self) -> None:
        one_cluster, _ = cluster_events([event(source("solo"), materiality=50, override=False)])
        confirmed_cluster, _ = cluster_events([
            event(source("first", group="first"), materiality=50, override=False),
            event(source("second", group="second"), materiality=50, override=False),
        ])
        self.assertGreater(confirmed_cluster[0].quality_score, one_cluster[0].quality_score)

    def test_42_cross_market_material_event_promoted(self) -> None:
        broad = event(source("broad"), title="Broad liquidity transmission event", materiality=50, cross_market=100, override=False)
        narrow = event(source("narrow"), title="Narrow single market event", materiality=50, cross_market=10, override=False)
        clusters, _ = cluster_events([broad, narrow])
        _, selected, _ = rank_coverage_clusters(clusters, limit=1)
        self.assertEqual(selected[0].cross_market_impact, 100)

    def test_43_deterministic_ranking(self) -> None:
        items = synthetic_regional_events({EventRegion.US_EU: 8, EventRegion.GREATER_CHINA: 5, EventRegion.REST_OF_WORLD: 3})
        first = evaluate_global_coverage(items, evaluated_at=NOW)
        second = evaluate_global_coverage(items, evaluated_at=NOW)
        self.assertEqual([item.cluster_id for item in first.selected_clusters], [item.cluster_id for item in second.selected_clusters])

    def test_44_same_inputs_same_result_across_order(self) -> None:
        items = synthetic_regional_events({EventRegion.US_EU: 8, EventRegion.GREATER_CHINA: 5, EventRegion.REST_OF_WORLD: 3})
        first = evaluate_global_coverage(items, evaluated_at=NOW)
        second = evaluate_global_coverage(list(reversed(items)), evaluated_at=NOW)
        self.assertEqual([item.cluster_id for item in first.selected_clusters], [item.cluster_id for item in second.selected_clusters])


class ShadowIsolationTests(unittest.TestCase):
    def registry(self) -> SourceRegistry:
        return SourceRegistry(
            "3.1",
            (
                source("legacy", legacy=True),
                source("expanded", region=EventRegion.REST_OF_WORLD, tier=SourceTier.TIER_1),
            ),
        )

    def legacy_item(self) -> dict:
        return {
            "source_id": "legacy",
            "source": "Legacy",
            "title": "Federal Reserve policy decision changes market liquidity",
            "summary": "Rates and equities respond.",
            "url": "https://example.com/legacy-event",
            "published_at": NOW,
        }

    def run_shadow(self, output: Path, fetcher=None):
        kwargs = {}
        if fetcher is not None:
            kwargs["fetcher"] = fetcher
        return run_global_coverage_shadow(
            [self.legacy_item()],
            output_dir=output,
            evaluated_at=NOW,
            registry=self.registry(),
            **kwargs,
        )

    def test_45_legacy_remains_user_visible(self) -> None:
        raw = [self.legacy_item()]
        original = copy.deepcopy(raw)
        with tempfile.TemporaryDirectory() as tmpdir:
            result = run_global_coverage_shadow(
                raw, output_dir=Path(tmpdir), evaluated_at=NOW,
                registry=self.registry(), fetcher=lambda _s, _t: [],
            )
        self.assertEqual(raw, original)
        self.assertEqual(result["selection_authority"], "legacy")

    def test_46_shadow_engine_executes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self.run_shadow(Path(tmpdir), fetcher=lambda _s, _t: [])
        self.assertTrue(result["ok"])
        self.assertEqual(result["mode"], "coverage_shadow")

    def test_47_shadow_does_not_alter_brief(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, patch(
            "app.fiona_runtime.run_global_coverage_shadow_safe",
            return_value={"ok": True, "selection_authority": "legacy"},
        ):
            status = run_once(
                output_dir=Path(tmpdir),
                brief="market-news",
                send=False,
                timezone_name="UTC",
                snapshot_builder=lambda _: en_us_fixture_snapshot(),
            )
            text = (Path(status["output_dir"]) / "fiona_telegram.md").read_text(encoding="utf-8")
        self.assertIn("Fiona Market News", text)

    def test_48_shadow_does_not_send_telegram(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, patch("app.fiona_runtime.telegram_send_message") as sender:
            run_once(
                output_dir=Path(tmpdir),
                brief="market-news",
                send=False,
                timezone_name="UTC",
                snapshot_builder=lambda _: en_us_fixture_snapshot(),
            )
        sender.assert_not_called()

    def test_49_shadow_does_not_mutate_scheduler_ledger(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            ledger = Path(tmpdir) / "fiona_scheduler_ledger.json"
            ledger.write_text("sentinel", encoding="utf-8")
            self.run_shadow(Path(tmpdir), fetcher=lambda _s, _t: [])
            self.assertEqual(ledger.read_text(encoding="utf-8"), "sentinel")

    def test_50_shadow_does_not_create_occurrence(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self.run_shadow(Path(tmpdir), fetcher=lambda _s, _t: [])
            names = {item.name for item in Path(tmpdir).iterdir()}
        self.assertEqual(result["formal_occurrences_created"], 0)
        self.assertNotIn("fiona_scheduler_ledger.json", names)

    def test_51_shadow_metrics_generated(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self.run_shadow(Path(tmpdir), fetcher=lambda _s, _t: [])
        for key in ("candidate_events", "qualified_clusters", "regional_selected_share", "rolling_24h", "rolling_7d"):
            self.assertIn(key, result)

    def test_52_source_failure_does_not_affect_legacy_delivery(self) -> None:
        def fail(_: SourceSpec, __: int):
            raise TimeoutError("source down")

        with tempfile.TemporaryDirectory() as tmpdir:
            result = self.run_shadow(Path(tmpdir), fetcher=fail)
        self.assertTrue(result["ok"])
        self.assertEqual(result["candidate_events"], 1)
        self.assertIn("timeout", {item["status"] for item in result["source_health"]})


class Gate1AndProductionRegressionTests(unittest.TestCase):
    def test_53_native_photo_passes(self) -> None:
        self.assertEqual(expected_image_size(TelegramMediaMode.PHOTO), (1440, 1800))

    def test_54_en_us_passes(self) -> None:
        outputs = build_en_us_user_surface_outputs(missing=False)
        self.assertTrue(all(not contains_cjk(value) for value in outputs.values()))

    def test_55_market_news_passes(self) -> None:
        self.assertIn("Fiona Global Intelligence", build_en_us_user_surface_outputs()["market_news"])

    def test_56_morning_passes(self) -> None:
        self.assertIn("Fiona Morning", build_en_us_user_surface_outputs()["morning"])

    def test_57_evening_passes(self) -> None:
        self.assertIn("Fiona Evening", build_en_us_user_surface_outputs()["evening"])

    def test_58_daily_passes(self) -> None:
        self.assertIn("Fiona Daily", build_en_us_user_surface_outputs()["daily"])

    def test_59_weekly_passes(self) -> None:
        self.assertIn("Fiona Weekly", build_en_us_user_surface_outputs()["weekly"])

    def test_60_alert_passes(self) -> None:
        self.assertIn("Fiona Alert", build_en_us_user_surface_outputs()["alert_critical"])

    def test_61_scheduler_unchanged(self) -> None:
        expected = {
            FionaBriefKind.MARKET_NEWS: "00:00:00",
            FionaBriefKind.MORNING: "07:30:00",
            FionaBriefKind.EVENING: "20:30:00",
            FionaBriefKind.DAILY: "22:30:00",
            FionaBriefKind.WEEKLY: "21:00:00",
        }
        self.assertEqual({kind: item.send_time.isoformat() for kind, item in BRIEF_SCHEDULES.items()}, expected)

    def test_62_ledger_unchanged(self) -> None:
        validation = validate_global_coverage_runtime(
            registry=SourceRegistry("3.1", (source(),)),
            fetcher=lambda _s, _t: [{"title": "Federal Reserve policy decision", "url": "https://example.com/a", "published_at": NOW.isoformat()}],
            evaluated_at=NOW,
        )
        self.assertEqual(validation["ledger_mutations"], 0)

    def test_63_arbitration_unchanged(self) -> None:
        self.assertEqual((ACTION_SEND, ACTION_DEFER, ACTION_SUPPRESS), ("send", "defer", "suppress"))

    def test_64_cadence_unchanged(self) -> None:
        with patch.dict("os.environ", {"FIONA_CADENCE_MODE": "legacy"}, clear=False):
            coverage_profile_from_env()
            self.assertEqual(__import__("os").environ["FIONA_CADENCE_MODE"], "legacy")

    def test_65_delta_remains_off(self) -> None:
        with patch.dict("os.environ", {"FIONA_4H_DELTA_MODE": "off"}, clear=False):
            coverage_profile_from_env()
            self.assertEqual(__import__("os").environ["FIONA_4H_DELTA_MODE"], "off")

    def test_66_registry_and_legacy_default_release_gate(self) -> None:
        registry_result = validate_registry(load_source_registry())
        self.assertTrue(registry_result["ok"])
        self.assertEqual(coverage_profile_from_env({}), CoverageProfile.LEGACY)


class EvidenceSafetyRegressionTests(unittest.TestCase):
    def test_shadow_outcome_does_not_change_legacy_payload_bytes(self) -> None:
        texts = []
        with patch.dict("os.environ", {"FIONA_OUTPUT_LOCALE": "en-US"}), patch(
            "app.fiona_runtime.now_in_timezone", return_value=NOW
        ), patch("app.fiona_runtime.telegram_send_message") as sender:
            for result in ({"ok": True, "selected": ["new_shadow_event"]}, {"ok": False}):
                with tempfile.TemporaryDirectory() as tmp, patch(
                    "app.fiona_runtime.run_global_coverage_shadow_safe", return_value=result
                ):
                    status = run_once(
                        output_dir=Path(tmp), brief="market-news", send=False,
                        timezone_name="UTC", snapshot_builder=lambda _: en_us_fixture_snapshot(),
                    )
                    self.assertTrue(status["ok"])
                    texts.append((Path(status["output_dir"]) / "fiona_telegram.md").read_bytes())
            sender.assert_not_called()
        self.assertEqual(texts[0], texts[1])

    def test_missing_article_links_do_not_merge_entire_feed(self) -> None:
        items = [
            normalize_source_item({"title": title, "published_at": NOW}, source(), retrieved_at=NOW)
            for title in ("Housing supply expands", "Energy demand contracts")
        ]
        self.assertTrue(all(item.canonical_url == "" for item in items))
        clusters, _ = cluster_events(items)
        self.assertEqual(len(clusters), 2)

    def test_html_response_is_not_an_empty_feed(self) -> None:
        with self.assertRaises(ValueError):
            parse_rss_payload(b"<html><body>Access denied</body></html>")

    def test_json_schema_drift_is_not_no_news(self) -> None:
        spec = replace(source(), retrieval_method="json", json_records_path=("result", "records"))
        with self.assertRaises(ValueError):
            parse_json_payload(b'{"result": {"changed": []}}', spec)
        self.assertEqual(parse_json_payload(b'{"result": {"records": []}}', spec), [])

    def test_exact_url_does_not_create_independent_confirmation(self) -> None:
        items = [event(source("a"), url="https://original.example/story"), event(source("b"), url="https://original.example/story")]
        clusters, _ = cluster_events(items)
        self.assertEqual(clusters[0].independent_source_count, 1)
        self.assertEqual(clusters[0].source_count, 2)

    def test_syndicated_copy_across_owners_is_not_independent(self) -> None:
        snippet = "The Federal Reserve announced a new monetary policy decision affecting rates and global financial conditions."
        clusters, diagnostics = cluster_events([event(source("a"), summary=snippet), event(source("b"), summary=snippet)])
        self.assertEqual(clusters[0].independent_source_count, 1)
        self.assertEqual(diagnostics.syndication_rejection_count, 1)

    def test_annual_same_title_releases_do_not_merge(self) -> None:
        clusters, _ = cluster_events([
            event(source("a"), url="https://official.example/releases/2026"),
            event(source("a"), url="https://official.example/releases/2025", published_at=NOW - timedelta(days=365)),
        ])
        self.assertEqual(len(clusters), 2)

    def test_original_invalid_date_does_not_become_current(self) -> None:
        item = normalize_source_item({"title": "Official release", "published_at": NOW, "original_published_at": "invalid"}, source(), retrieved_at=NOW)
        self.assertIsNone(item.published_at)
        self.assertEqual(item.freshness, FreshnessStatus.UNKNOWN)

    def test_warning_and_warsh_do_not_trigger_systemic_override(self) -> None:
        self.assertFalse(event(title="Kevin Warsh warns about the outlook", summary="An ordinary interview.").material_override)

    def test_security_does_not_match_sec_region_keyword(self) -> None:
        spec = source("unknown", region=EventRegion.UNKNOWN)
        self.assertEqual(infer_event_region("Security software update", "", spec), EventRegion.UNKNOWN)

    def test_singapore_is_row_not_greater_china(self) -> None:
        self.assertEqual(infer_event_region("Singapore monetary policy", "", source(region=EventRegion.GREATER_CHINA)), EventRegion.REST_OF_WORLD)

    def test_repeated_evaluation_does_not_inflate_observation_count(self) -> None:
        evaluation = evaluate_global_coverage([event()], evaluated_at=NOW)
        with tempfile.TemporaryDirectory() as tmp:
            store = CoverageObservationStore(Path(tmp) / "coverage.json")
            store.record(evaluation)
            store.record(evaluation)
            self.assertEqual(store.cumulative_qualified_clusters, 1)

    def test_new_confirmation_preserves_observation_identity(self) -> None:
        first = event(source("a"))
        second = event(source("b"))
        with tempfile.TemporaryDirectory() as tmp:
            store = CoverageObservationStore(Path(tmp) / "coverage.json")
            store.record(evaluate_global_coverage([first], evaluated_at=NOW))
            store.record(evaluate_global_coverage([first, second], evaluated_at=NOW))
            self.assertEqual(store.cumulative_qualified_clusters, 1)

    def test_shadow_log_failure_is_contained(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = run_global_coverage_shadow_safe([], output_dir=Path(tmp), evaluated_at=NOW, collect_expanded=False, logger=Mock(side_effect=OSError("log unavailable")))
        self.assertFalse(result["ok"])
        self.assertEqual(result["selection_authority"], "legacy")

    def test_invalid_profile_warns_and_falls_back(self) -> None:
        logs = []
        self.assertEqual(coverage_profile_from_env({"FIONA_COVERAGE_PROFILE": "invalid"}, logs.append), CoverageProfile.LEGACY)
        self.assertEqual(logs[0]["fallback_profile"], "legacy")

    def test_registry_is_the_only_legacy_source_authority(self) -> None:
        from app.config import load_sources
        from app.fiona_source_registry import DEFAULT_SOURCE_REGISTRY
        registered = load_source_registry().legacy_sources()
        self.assertEqual([item.url for item in load_sources(DEFAULT_SOURCE_REGISTRY)], [item.endpoint for item in registered])


if __name__ == "__main__":
    unittest.main()
