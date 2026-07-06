from __future__ import annotations

import unittest
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.fiona_briefing import FionaBriefKind
from app.fiona_contracts import (
    AlertContract,
    AlertStatus,
    AlertType,
    CauseStatus,
    EvidenceRecord,
    FionaEventV2Contract,
    FionaTag,
    PersistenceClass,
    Route,
    RouteDecision,
    ScoreRecord,
    ScoreStatus,
    SourceType,
    TagType,
    VerificationStatus,
    classify_material_changes,
    decide_verification,
    railway_json_memory_contract,
)
from app.fiona_runtime import due_brief_kinds
from app.fiona_types import EventCategory, FionaEvent, MarketDirection


NOW = datetime(2026, 7, 5, 7, 30, tzinfo=ZoneInfo("Asia/Manila"))


def v1_event() -> FionaEvent:
    return FionaEvent(
        event_id="btc_1",
        created_at=NOW,
        source="unit_test",
        category=EventCategory.PRICE,
        title="BTC price move",
        what_happened="BTC moved.",
        why_important="It affects crypto risk appetite.",
        affected_assets=["BTC", "ETH"],
        watch_next=["ETF flow confirmation"],
        fiona_view="This remains a confirmation watch.",
        impact_score=8,
        urgency_score=7,
        confidence_score=6,
        market_direction=MarketDirection.NEUTRAL,
        evidence=["price_move"],
    )


class FionaPhase0AContractsTest(unittest.TestCase):
    def test_event_v2_optional_fields_and_backward_compatibility(self) -> None:
        contract = FionaEventV2Contract.from_v1_event(v1_event())

        self.assertEqual(contract.schema_version, "2.0")
        self.assertEqual(contract.event_id, "btc_1")
        self.assertEqual(contract.event_type, "price")
        self.assertEqual(contract.assets, ["BTC", "ETH"])
        self.assertEqual(contract.verification_status, VerificationStatus.UNVERIFIED)
        self.assertEqual(contract.source_count, 1)
        self.assertEqual(contract.risk_score.value, None)
        self.assertEqual(contract.risk_score.status, ScoreStatus.UNAVAILABLE)

    def test_confirmed_fact_rule_a_three_independent_sources(self) -> None:
        decision = decide_verification(
            [
                EvidenceRecord("fed", "Federal Reserve", SourceType.PRIMARY, independence_group="fed"),
                EvidenceRecord("bbg", "Bloomberg", SourceType.MAJOR_MEDIA, independence_group="bloomberg"),
                EvidenceRecord("reuters", "Reuters", SourceType.MAJOR_MEDIA, independence_group="reuters"),
            ]
        )

        self.assertEqual(decision.status, VerificationStatus.CONFIRMED)
        self.assertEqual(decision.rule, "Confirmed Fact Rule A")
        self.assertEqual(decision.independent_source_count, 3)

    def test_confirmed_fact_rule_b_primary_plus_authoritative(self) -> None:
        decision = decide_verification(
            [
                EvidenceRecord("sec", "SEC", SourceType.PRIMARY, independence_group="sec"),
                EvidenceRecord("issuer", "Issuer Filing Desk", SourceType.AUTHORITATIVE, independence_group="issuer"),
            ]
        )

        self.assertEqual(decision.status, VerificationStatus.CONFIRMED)
        self.assertEqual(decision.rule, "Confirmed Fact Rule B")

    def test_insufficient_and_duplicate_sources_are_not_confirmed(self) -> None:
        duplicate_decision = decide_verification(
            [
                EvidenceRecord("wire_a", "Wire A", SourceType.MAJOR_MEDIA, independence_group="syndicated_wire"),
                EvidenceRecord("wire_b", "Wire B", SourceType.MAJOR_MEDIA, independence_group="syndicated_wire"),
            ]
        )
        single_decision = decide_verification([EvidenceRecord("anon", "Anonymous", SourceType.ANONYMOUS)])

        self.assertEqual(duplicate_decision.status, VerificationStatus.UNVERIFIED)
        self.assertEqual(duplicate_decision.independent_source_count, 1)
        self.assertEqual(single_decision.status, VerificationStatus.UNVERIFIED)

    def test_score_value_is_null_when_data_is_insufficient(self) -> None:
        score = ScoreRecord(value=88, status=ScoreStatus.INSUFFICIENT_DATA, data_support="missing official ETF net flow")

        self.assertIsNone(score.value)
        self.assertEqual(score.status, ScoreStatus.INSUFFICIENT_DATA)

    def test_multi_route_contract(self) -> None:
        contract = FionaEventV2Contract(
            event_id="route_1",
            title="Routing test",
            event_type="macro",
            detected_at=NOW,
            routes=[
                RouteDecision(Route.WATCH, "Needs confirmation", 72, NOW),
                RouteDecision(Route.DAILY, "Useful for daily context", 81, NOW),
            ],
        )

        self.assertEqual([route.route for route in contract.routes], [Route.WATCH, Route.DAILY])

    def test_material_change_classification(self) -> None:
        previous = AlertContract(
            alert_type=AlertType.MARKET_ANOMALY,
            status=AlertStatus.DEVELOPING,
            cause_status=CauseStatus.UNKNOWN,
            risk_level=4,
            impact_scope=("BTC",),
            lifecycle_status="NEW",
            price_regime="range",
            flow_direction="neutral",
        )
        current = AlertContract(
            alert_type=AlertType.MARKET_ANOMALY,
            status=AlertStatus.UPDATED,
            cause_status=CauseStatus.KNOWN,
            verification_status=VerificationStatus.PROBABLE,
            risk_level=7,
            impact_scope=("BTC", "ETH", "SOL"),
            lifecycle_status="ONGOING",
            price_regime="breakdown",
            flow_direction="outflow",
            official_response="exchange_status_update",
        )

        changes = classify_material_changes(previous, current)

        self.assertIn("risk level change", changes)
        self.assertIn("impact expansion", changes)
        self.assertIn("cause confirmation", changes)
        self.assertIn("cross-market contagion", changes)
        self.assertIn("lifecycle change", changes)

    def test_railway_json_memory_is_ephemeral(self) -> None:
        contract = railway_json_memory_contract("Alert History")

        self.assertEqual(contract.persistence_class, PersistenceClass.EPHEMERAL)
        self.assertFalse(contract.railway_redeploy_safe)

    def test_tag_canonicalization_and_telegram_hashtag_normalization(self) -> None:
        btc = FionaTag("", "BTC / Bitcoin", TagType.ASSET, aliases=("比特币", "Bitcoin"))
        cn_risk = FionaTag("", "宏观 风险!", TagType.RISK)
        numeric = FionaTag("2026 CPI", "2026 CPI", TagType.EVENT)

        self.assertEqual(btc.canonical_id, "asset_btc_bitcoin")
        self.assertEqual(btc.telegram_hashtag, "#asset_btc_bitcoin")
        self.assertEqual(cn_risk.canonical_id, "risk_宏观_风险")
        self.assertEqual(cn_risk.telegram_hashtag, "#risk")
        self.assertEqual(numeric.telegram_hashtag, "#event_2026_cpi")


class FionaSchedulerDeliverySimulationTest(unittest.TestCase):
    def simulate(self, start: datetime, days: int = 1, interval_minutes: int = 240) -> dict[FionaBriefKind, int]:
        seen = {kind: 0 for kind in FionaBriefKind}
        current = start
        end = start + timedelta(days=days)
        while current < end:
            for kind in due_brief_kinds(current):
                seen[kind] += 1
            current += timedelta(minutes=interval_minutes)
        return seen

    def test_240_minute_polling_from_midnight_misses_non_midnight_tasks(self) -> None:
        seen = self.simulate(datetime(2026, 7, 5, 0, 0, tzinfo=ZoneInfo("Asia/Manila")), days=7)

        self.assertEqual(seen[FionaBriefKind.MARKET_NEWS], 7)
        self.assertEqual(seen[FionaBriefKind.MORNING], 0)
        self.assertEqual(seen[FionaBriefKind.EVENING], 0)
        self.assertEqual(seen[FionaBriefKind.DAILY], 0)
        self.assertEqual(seen[FionaBriefKind.WEEKLY], 0)

    def test_start_time_controls_delivery_with_current_due_window(self) -> None:
        morning_hit = self.simulate(datetime(2026, 7, 5, 7, 20, tzinfo=ZoneInfo("Asia/Manila")))
        all_missed = self.simulate(datetime(2026, 7, 5, 6, 2, tzinfo=ZoneInfo("Asia/Manila")))

        self.assertEqual(morning_hit[FionaBriefKind.MORNING], 1)
        self.assertTrue(all(count == 0 for count in all_missed.values()))


if __name__ == "__main__":
    unittest.main()
