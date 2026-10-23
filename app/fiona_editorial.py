"""Deterministic editorial qualifications; no collectors, delivery or state writes."""
from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass, replace
from datetime import datetime
from enum import Enum
from typing import Any, Iterable, Sequence
from urllib.parse import urlsplit

from app.fiona_source_registry import EventRegion, SourceSpec, SourceTier


EDITORIAL_VERSION = "gate2.4b.1"


class RelevanceClass(str, Enum):
    DIRECT = "DIRECT"
    TRANSMITTED = "TRANSMITTED"
    CONTEXT_ONLY = "CONTEXT_ONLY"
    NOT_RELEVANT = "NOT_RELEVANT"
    UNKNOWN = "UNKNOWN"


class AssertionType(str, Enum):
    REALIZED_EVENT = "REALIZED_EVENT"
    ANNOUNCED_DECISION = "ANNOUNCED_DECISION"
    REPORTED_OBSERVATION = "REPORTED_OBSERVATION"
    EXPECTATION = "EXPECTATION"
    CONDITIONAL_SCENARIO = "CONDITIONAL_SCENARIO"
    SPECULATION = "SPECULATION"
    UNKNOWN = "UNKNOWN"


class NoveltyStatus(str, Enum):
    UNCHANGED = "UNCHANGED"
    MATERIAL_UPDATE = "MATERIAL_UPDATE"
    NEW_EVENT = "NEW_EVENT"
    PERIODIC_NEW_OCCURRENCE = "PERIODIC_NEW_OCCURRENCE"
    UNKNOWN = "UNKNOWN"


def text(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", value.casefold())).strip()


def matches(value: str, pattern: str) -> bool:
    return bool(re.search(r"\b(?:" + pattern + r")\b", text(value)))


def fingerprint(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()[:24]


@dataclass(frozen=True)
class AssertionDecision:
    assertion_type: AssertionType
    actor: str | None = None
    action: str | None = None
    object: str | None = None
    event_time: str | None = None
    effective_time: str | None = None
    conditional_markers: tuple[str, ...] = ()
    negation_markers: tuple[str, ...] = ()
    evidence_references: tuple[str, ...] = ("headline",)
    verification_status: str = "Unverified"


@dataclass(frozen=True)
class RelevanceDecision:
    relevance_class: RelevanceClass
    transmission_channels: tuple[str, ...]
    supporting_evidence: tuple[str, ...]
    relevance_reason: str
    administrative: bool = False

    @property
    def eligible(self) -> bool:
        return self.relevance_class == RelevanceClass.DIRECT or (
            self.relevance_class == RelevanceClass.TRANSMITTED and bool(self.transmission_channels)
        )


@dataclass(frozen=True)
class GeographyDecision:
    primary_event_jurisdiction: EventRegion
    secondary_affected_regions: tuple[EventRegion, ...]
    participating_jurisdictions: tuple[EventRegion, ...]
    geographic_evidence: tuple[str, ...]
    canonical_editorial_region: EventRegion
    reason: str


@dataclass(frozen=True)
class EvidenceQuality:
    value: int
    components: dict[str, int]
    evidence_status: str
    reason: str


@dataclass(frozen=True)
class NoveltyDecision:
    status: NoveltyStatus = NoveltyStatus.UNKNOWN
    reason: str = "history_not_supplied"
    previous_selected_at: str | None = None


@dataclass(frozen=True)
class EditorialAssessment:
    assertion: AssertionDecision
    relevance: RelevanceDecision
    geography: GeographyDecision
    evidence_quality: EvidenceQuality
    source_supported_markets: tuple[str, ...]
    event_affected_markets: tuple[str, ...]
    materiality: int
    cross_market_impact: int
    narrative_relevance: int
    override_eligible: bool
    override_reason: str
    memory: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


MONETARY = r"fed|federal reserve|fomc|ecb|boj|pboc|bank of england|central bank|reserve bank|bank rate|policy rates?|interest rates?|monetary policy|央行|利率"
POLICY_ACTION = r"cuts?|hikes?|raises?|lowers?|holds?|maintains?|maintained|unchanged|rate decision|policy decision|降息|加息"
MACRO = r"inflation|consumer prices?|cpi|ppi|gdp|gross domestic product|payrolls?|unemployment|jobless claims|employment data|通胀|失业"
EXCEPTIONAL = r"emergency rate (?:cut|hike|decision)|unexpected rate (?:cut|hike|decision)|emergency liquidity injection|systemic (?:financial|banking) (?:risk|crisis)|bank run|sovereign default|capital controls|trading halt|exchange halt|circuit breaker|major (?:hack|cyberattack|regulatory ban)|global energy supply disruption|war breaks out|declares war"
ADMIN = r"calendar|committee dates|meeting dates|future rate decision|upcoming rate decision|decision date|appointments?|personnel|scam alert|fraud awareness|educational|housekeeping|procedural|coupon interest|weekly statistical|turnover data|diversity at|student loan|interest payment|tender results|underwriting auction|reminds public|stay alert|phishing scams|regular review|extension of period|banknote (?:imagery|artwork|design)|premature redemption|supervisory dialogue|financial regulatory dialogue"
AUCTION = r"auction (?:result|results|notice|calendar)|(?:result|results) (?:of|conversion)|full auction result"
ABNORMAL = r"unexpected|surprise|surges?|plunges?|spikes?|record (?:high|low)|weak demand|liquidity (?:shortage|crisis)|bid to cover|yield (?:jump|spike)|failed auction"
OBSERVATION = r"rises?|falls?|drops?|jumps?|surges?|slips?|tumbles?|plunges?|whipsaws?|hits?|hit|near|triggers?|reports?|reported|shows?|publishes?|released|changes?|releases?|grows?|growth|slowdown|flows?|outflows?|inflows?|repricing|disruption|risks?|decision|development|conditions|issues|issued|withholds|takes off"
NONFINANCIAL = r"(?:nba|basketball|football|soccer|warriors) (?:player|star|season)|(?:play|player|leaves|season|retire|retirement).*(?:warriors|basketball|football|soccer)|super pac|campaign (?:donations|fundraising)|gop senate|media strategies|study in contrasts|human rights award|bugging suspect|wiretapping suspect"


def _headline_assertion(title: str) -> AssertionDecision:
    headline = text(title)
    conditional = tuple(w for w in ("if", "could", "may", "might", "would", "potential") if matches(title, w))
    negative = tuple(w for w in ("did not", "has not", "will not", "no rate cut", "denies") if matches(title, w))
    actors = re.search(r"\b(federal reserve|fed|ecb|boj|pboc|sec|bank of england|treasury|china|eu|us)\b", headline)
    action = re.search(r"\b(announces?|announced|approves?|approved|imposes?|imposed|waives?|waived|restricts?|restricted|cuts?|hikes?|holds?|raises?|lowers?|reports?|publishes?)\b", headline)
    if negative:
        kind = AssertionType.REPORTED_OBSERVATION
    elif matches(title, r"rumou?r|unconfirmed|speculation|speculates?"):
        kind = AssertionType.SPECULATION
    elif matches(headline.split(" as ")[0], r"(?:bond|treasury|mortgage).*?(?:yields?|rates?).*?(?:surge|jump|rise|fall|drop)"):
        kind = AssertionType.REPORTED_OBSERVATION
    elif matches(title, r"expects?|expected|expectations|forecast|predicts?|weighs|plans? to|will (?:cut|hike|announce)|next year|will be"):
        kind = AssertionType.EXPECTATION
    elif conditional:
        kind = AssertionType.CONDITIONAL_SCENARIO
    elif matches(title, r"announces?|announced|approves?|approved|imposes?|imposed|waives?|waived|restricts?|restricted|rate decision|policy decision|opening remarks|policy statement|mou") or (
        matches(title, MONETARY) and matches(title, POLICY_ACTION)
    ):
        kind = AssertionType.ANNOUNCED_DECISION
    elif matches(title, EXCEPTIONAL):
        kind = AssertionType.REALIZED_EVENT
    elif matches(title, OBSERVATION) or action:
        kind = AssertionType.REPORTED_OBSERVATION
    else:
        kind = AssertionType.UNKNOWN
    return AssertionDecision(kind, actors.group(0) if actors else None,
                             action.group(0) if action else None,
                             conditional_markers=conditional, negation_markers=negative)


def policy_action_claim(value: str) -> bool:
    return matches(value, r"(?:cuts?|cut|hikes?|held|holds?|raised|raises?|lowers?|lowered) (?:the )?(?:(?:policy|interest|bank) )?rates?|(?:policy|interest|bank) rates? (?:were |was )?(?:cut|held|raised|lowered|unchanged)")


def summary_claims(summary: str) -> tuple[str, ...]:
    """Bounded source claims, not keyword bags or publisher coverage priors."""
    units = re.split(r"[;\n]+|(?<=[.!?])\s+(?=[A-Z])", summary[:1200])[:12]
    claims = []
    for unit in units:
        if matches(unit, r"metaphor|nickname|fictional|wordplay|to fame|not (?:financial|economic)|no financial (?:impact|implications)|mentions? the word|subscribe|read more"):
            continue
        if matches(unit, r"campaign fundraising|campaign donations|super pac") and not matches(unit, r"government bonds|bank liquidity|capital requirements|fiscal policy"):
            continue
        if matches(unit, r"room rates|hotel rates|hospitality pricing") and not matches(unit, r"earnings|revenue|profits?|bonds?|share price"):
            continue
        monetary = matches(unit, MONETARY) and matches(unit, r"rates?|cut|hike|holds?|held|liquidity|capital")
        subject = monetary or matches(unit, MACRO + r"|bank liquidity|capital requirements?|bond yields?|treasury yields?|policy rates?|interest rates?|rate cut|rate hike|no cut|rates (?:unchanged|remain)|stocks?|shares?|equities|kospi|nasdaq|earnings|revenue|profits?|bonds?|etf|bitcoin|crypto|(?:gold|silver|oil) prices?|oil supply|shipping costs|financial stability|settlement (?:platform|system)|trading halt|circuit breaker")
        financial_quantity = re.search(r"\d+(?:\.\d+)?\s*(?:%|percent\b|basis points\b|bps\b|million\b|billion\b|trillion\b|points?\b|dollars?\b)|\$\s*\d", unit, re.IGNORECASE)
        measurement = bool(financial_quantity) and matches(unit, r"reports?|reported|published|recorded|remains?|is|are")
        predicate = measurement or policy_action_claim(unit) or matches(unit, r"rose|risen|rises?|fell|falls?|contracted|grew|surged|plunged|triggered|halted|announces?|announced|approves?|approved|revised|launched|issued|defaulted|suspended|disrupted|reduced|increased|expects?|forecast|could|may|might|would|speculation|unconfirmed|rumou?r|unchanged")
        if subject and predicate:
            claims.append(unit.strip())
    return tuple(claims)


def _summary_assertion(claim: str) -> AssertionDecision:
    decision = _headline_assertion(claim)
    if decision.assertion_type == AssertionType.UNKNOWN and matches(
            claim, r"contracted|grew|rose|fell|surged|plunged|triggered|halted|recorded|revised|launched|issued|defaulted|is|are|remains?"):
        decision = replace(decision, assertion_type=AssertionType.REPORTED_OBSERVATION,
                           action="reported_measurement")
    if policy_action_claim(claim) and not (
            decision.conditional_markers or decision.negation_markers or decision.assertion_type in {
                AssertionType.EXPECTATION, AssertionType.SPECULATION}):
        decision = replace(decision, assertion_type=AssertionType.ANNOUNCED_DECISION)
    if matches(claim, r"next (?:quarter|month|week)|tomorrow") and not decision.negation_markers:
        decision = replace(decision, assertion_type=AssertionType.EXPECTATION)
    return replace(decision, evidence_references=("source_claim:financial",))


def assertion_for(title: str, summary: str = "") -> AssertionDecision:
    headline = _headline_assertion(title[:500])
    claims = summary_claims(summary)
    if not claims:
        return headline
    decisions = [_summary_assertion(claim) for claim in claims]
    if matches(summary[:1200], r"hypothetical scenario|illustrative scenario|analysts speculate|not an actual decision"):
        return replace(headline, assertion_type=AssertionType.CONDITIONAL_SCENARIO,
                       conditional_markers=("source_scenario_context",), evidence_references=("source_claim:scenario",))
    # A denial/hold cannot authenticate an asserted cut, nor can a forecast.
    rate_action = matches(title, MONETARY) and matches(title, r"cuts?|hikes?|raises?|lowers?")
    rate_denial = any(matches(claim, MONETARY + r"|rates?") and (
        matches(claim, r"did not|has not|no (?:rate )?cut|not cut|unchanged|holds?|held")
    ) for claim in claims)
    if rate_action and rate_denial:
        return replace(headline, assertion_type=AssertionType.REPORTED_OBSERVATION,
                       action="contradicted_rate_action", negation_markers=("source_contradicts_headline",),
                       evidence_references=("headline", "source_claim:contradiction"))
    if headline.negation_markers and any(d.assertion_type == AssertionType.ANNOUNCED_DECISION and not d.negation_markers for d in decisions):
        return replace(headline, assertion_type=AssertionType.UNKNOWN,
                       evidence_references=("headline", "source_claim:contradiction"))
    uncertain = [d for d in decisions if d.assertion_type in {
        AssertionType.EXPECTATION, AssertionType.CONDITIONAL_SCENARIO, AssertionType.SPECULATION}]
    factual = [d for d in decisions if d.assertion_type in {
        AssertionType.ANNOUNCED_DECISION, AssertionType.REPORTED_OBSERVATION, AssertionType.REALIZED_EVENT}]
    if uncertain and not factual:
        return replace(uncertain[0], actor=headline.actor or uncertain[0].actor)
    if headline.assertion_type in {AssertionType.EXPECTATION, AssertionType.CONDITIONAL_SCENARIO, AssertionType.SPECULATION}:
        return headline
    if factual:
        # Mixed source claims are not independent confirmation or permission to override.
        chosen = factual[0]
        if uncertain:
            return replace(headline, assertion_type=AssertionType.UNKNOWN,
                           evidence_references=("headline", "source_claim:mixed"))
        return replace(chosen, actor=headline.actor or chosen.actor)
    return headline


def affected_markets(title: str, summary: str = "") -> tuple[str, ...]:
    evidence = f"{title} {summary}"
    patterns = {
        "crypto": r"bitcoin|btc|ethereum|eth|crypto|stablecoins?|blockchain|tokenized|tokenization|defi",
        "equities": r"stocks?|equities|equity|nasdaq|s p 500|kospi|shares|listed company|earnings|profit",
        "rates": MONETARY + r"|bond yields?|treasury yields?|mortgage rates?|bonds?|treasuries|repo|liquidity injection",
        "fx": r"dollar|yen|yuan|euro|sterling|currency|fx|dxy|renminbi",
        "commodities": r"commodities|commodity|oil|gold|silver|energy supply|timberland",
    }
    return tuple(key for key, pattern in patterns.items() if matches(evidence, pattern))


def relevance_for(title: str, summary: str = "") -> RelevanceDecision:
    evidence = f"{title} {summary}"
    claims = summary_claims(summary)
    supported_summary = " ".join(claims)
    business_evidence = matches(title, r"earnings|profit|revenue|share price|bond default") or matches(
        supported_summary, r"earnings|profit|revenue|share price|issued bonds|bond default")
    if matches(title, NONFINANCIAL) and not business_evidence:
        return RelevanceDecision(RelevanceClass.NOT_RELEVANT, (), ("headline:nonfinancial_subject",), "no_supported_financial_transmission")
    if claims:
        specific_transmission = matches(supported_summary, r"oil supply|shipping costs|financial stability|bank liquidity") and matches(
            title, r"war|conflict|attack|sanctions|policy|regulation|energy|security")
        kind = RelevanceClass.TRANSMITTED if specific_transmission else RelevanceClass.DIRECT
        channels = ("documented_financial_risk",) if specific_transmission else affected_markets(supported_summary) or ("macro_evidence",)
        return RelevanceDecision(kind, channels, ("source_claim:financial",), "specific_financial_evidence_in_source_claim")
    teaser = re.search(r"\b(?:could|may|might) (?:surprise|shock|stun)\b(.*)", text(title))
    if teaser and not matches(teaser.group(1), MACRO + r"|rate cut|rate hike|policy decision|earnings|default|liquidity|tariff"):
        return RelevanceDecision(RelevanceClass.CONTEXT_ONLY, (), ("headline:unanchored_scenario",), "speculative_teaser_without_specific_development")
    unusual_auction = matches(title, AUCTION) and matches(evidence, ABNORMAL) and bool(re.search(r"\d", evidence))
    routine_termination = matches(title, r"termination of enforcement actions") and not matches(
        evidence, r"systemic|financial stability|capital requirements|billion.*deposits")
    administrative = matches(title, ADMIN) or (matches(title, AUCTION) and not unusual_auction) or routine_termination
    measured_market_event = matches(title, r"shares?|stocks?|yields?") and matches(title, ABNORMAL) and bool(re.search(r"\d", title))
    administrative = administrative and not measured_market_event
    if administrative:
        return RelevanceDecision(RelevanceClass.CONTEXT_ONLY, (), ("headline:administration",), "routine_without_material_change", True)
    # A business result may be relevant even when the subject is a sports club.
    business_result = matches(title, r"earnings|profit|revenue|listed.*shares|share price|bond default")
    if matches(title, NONFINANCIAL) and not business_result:
        return RelevanceDecision(RelevanceClass.NOT_RELEVANT, (), ("headline:nonfinancial_subject",), "no_supported_financial_transmission")
    if matches(title, r"hotel rates|hospitality pricing|room rates") and not business_result:
        return RelevanceDecision(RelevanceClass.CONTEXT_ONLY, (), ("headline:hospitality_pricing",), "not_monetary_policy")
    if matches(title, r"here s how|opportunities|stocks to play|how to get long|amazing year|growth potential of these"):
        return RelevanceDecision(RelevanceClass.CONTEXT_ONLY, (), ("headline:investment_commentary",), "commentary_without_specific_new_event")
    title_markets = affected_markets(title)
    if matches(title, r"war breaks out|declares war"):
        return RelevanceDecision(RelevanceClass.TRANSMITTED, ("systemic_geopolitical_risk",), ("headline:realized_conflict",), "credible_early_warning_channel_not_observed_price_causality")
    monetary = matches(title, MONETARY) and matches(title, POLICY_ACTION + r"|expectations|liquidity|policy|minutes")
    financial_signal = matches(title, r"bond yields?|treasury yields?|mortgage rates?|interest rate expectations|rate signal|market liquidity|financial stability|liquidity repricing|liquidity injection|capital requirements?|regulatory ban|enforcement action|supervisory mou|investment advisers|monetary system|liquidity lines|sovereign bonds")
    macro = matches(title, MACRO)
    observed_market = bool(title_markets) and matches(title, OBSERVATION + r"|liquidations?|halt|bankruptcy|default|earnings|profit|issued|issues|tokenized|tokenization|etf")
    if monetary or financial_signal or macro or observed_market or unusual_auction or matches(title, EXCEPTIONAL):
        channels = title_markets or (("financial_stability",) if matches(title, EXCEPTIONAL) else ("macro_policy",))
        return RelevanceDecision(RelevanceClass.DIRECT, channels, ("headline:financial_event",), "explicit_financial_claim")
    policy = matches(title, r"sanctions?|tariffs?|fiscal stimulus|capital controls|trade (?:agreement|restrictions|deal)|shipping|bab al mandeb")
    if policy and matches(title, r"announces?|announced|imposes?|imposed|waives?|waived|restricts?|restricted|approved|blocks?|blocked|disruption|opening|closes?|closed|cuts?|issues?|issued"):
        return RelevanceDecision(RelevanceClass.TRANSMITTED, ("trade_or_shipping_policy",), ("headline:policy_transmission",), "credible_policy_channel_without_requiring_price_response")
    # A specific financial consequence in a snippet can support an early warning.
    if matches(title, r"war|conflict|attack|sanctions|policy|regulation") and matches(summary, r"oil supply disruption|shipping costs|bank liquidity|capital requirements|financial stability"):
        return RelevanceDecision(RelevanceClass.TRANSMITTED, ("documented_financial_risk",), ("source_claim:financial_transmission",), "explicit_transmission_in_source_snippet")
    if matches(title, r"analysts?|commentary|interview|statement|war of words|media|politic|urged|should|trade war"):
        return RelevanceDecision(RelevanceClass.CONTEXT_ONLY, (), ("headline:background",), "no_new_supported_financial_development")
    return RelevanceDecision(RelevanceClass.UNKNOWN, (), (), "insufficient_event_evidence")


def geography_for(title: str, summary: str, source: SourceSpec,
                  region_terms: Sequence[tuple[EventRegion, Sequence[str]]] = ()) -> GeographyDecision:
    combined = f"{title} {summary}"
    extra = (
        (EventRegion.US_EU, ("united states", "u.s.", "european union", "europe", "fed", "federal reserve", "ecb", "bank of england", "gop", "senate", "america", "trump")),
        (EventRegion.GREATER_CHINA, ("china", "chinese", "pboc", "hong kong", "hkma", "hkex", "taiwan")),
        (EventRegion.REST_OF_WORLD, ("russia", "ukraine", "japan", "boj", "india", "rbi", "bank of korea", "saudi", "riyadh", "yemen", "bab al mandeb", "korea", "middle east")),
    )
    found: dict[EventRegion, list[str]] = {}
    for region, terms in (*region_terms, *extra):
        for term in terms:
            cjk_term = any("\u3400" <= char <= "\u9fff" for char in term)
            if (text(term) in text(combined) if cjk_term else matches(combined, re.escape(text(term)))):
                found.setdefault(region, []).append(term)
    if re.search(r"\b(?:US|U\.S\.|EU)\b", combined):
        found.setdefault(EventRegion.US_EU, []).append("uppercase_US_EU_alias")
    if not found and source.source_type in {"Primary", "Official"}:
        official = {"fed": EventRegion.US_EU, "sec": EventRegion.US_EU, "ecb": EventRegion.US_EU, "boe": EventRegion.US_EU,
                    "hkma": EventRegion.GREATER_CHINA, "hkex": EventRegion.GREATER_CHINA, "pboc": EventRegion.GREATER_CHINA,
                    "boj": EventRegion.REST_OF_WORLD, "rbi": EventRegion.REST_OF_WORLD, "bok": EventRegion.REST_OF_WORLD}
        key = source.source_id.split("_")[0]
        if key in official:
            found[official[key]] = ["official_source_jurisdiction:" + key]
    regions = tuple(sorted(found, key=lambda r: r.value))
    primary = regions[0] if len(regions) == 1 else EventRegion.UNKNOWN
    reason = "explicit_jurisdictions" if regions else "insufficient_geographic_evidence"
    lead = text(title)
    for region, pattern in (
        (EventRegion.US_EU, r"(?:the )?(?:fed|federal reserve|ecb|bank of england)\b"),
        (EventRegion.GREATER_CHINA, r"(?:the )?(?:pboc|hkma|hkex)\b"),
        (EventRegion.REST_OF_WORLD, r"(?:the )?(?:boj|rbi|bank of korea)\b"),
    ):
        if re.match(pattern, lead):
            primary = region
            reason = "named_institution_as_primary_actor"
            break
    if matches(title, r"bab al mandeb"):
        primary = EventRegion.REST_OF_WORLD
        reason = "shipping_location_distinct_from_speaker"
    elif matches(title, r"(?:us|united states|trump).*(?:sanctions?|tariffs?|policy).*(?:russia)|trump waives.*russia"):
        primary = EventRegion.US_EU
        reason = "policy_issuer_distinct_from_target"
    global_signal = not regions and (matches(combined, r"global|worldwide|cross regional") or (
        matches(title, r"bitcoin|crypto") and matches(title, r"liquidations|whipsaws")
    ))
    canonical = EventRegion.GLOBAL if len(regions) > 1 or global_signal else primary
    secondary = tuple(r for r in regions if r != primary)
    evidence = tuple(sorted({f"{region.value}:{term}" for region, terms in found.items() for term in terms}))[:12]
    return GeographyDecision(primary, secondary, regions, evidence, canonical, reason)


def materiality_for_assessment(title: str, summary: str, assertion: AssertionDecision,
                              relevance: RelevanceDecision, markets: Sequence[str]) -> tuple[int, int, int]:
    claim = " ".join(summary_claims(summary)) if assertion.evidence_references == ("source_claim:financial",) else title
    cross = min(100, 20 + max(0, len(set(markets)) - 1) * 24) if markets else 0
    if relevance.administrative:
        return 18, 0, 20
    if not relevance.eligible:
        return (25 if relevance.relevance_class == RelevanceClass.CONTEXT_ONLY else 10), 0, 20
    realized = assertion.assertion_type in {AssertionType.REALIZED_EVENT, AssertionType.ANNOUNCED_DECISION, AssertionType.REPORTED_OBSERVATION}
    if matches(claim, EXCEPTIONAL) and realized and not assertion.negation_markers:
        base = 92
    elif matches(claim, MONETARY) and matches(claim, POLICY_ACTION) and realized and not assertion.negation_markers:
        base = 75
    elif matches(claim, MACRO):
        base = 70
    elif matches(claim, r"crypto|bitcoin") and matches(claim, r"liquidations?") and matches(claim, r"billion"):
        base = 75
    elif matches(claim, r"sanctions?|tariffs?|enforcement actions?|regulatory|capital requirements?|liquidity injection|bond yields?|treasury yields?|mortgage rates?|policy statement|supervisory mou"):
        base = 65
    elif relevance.relevance_class == RelevanceClass.TRANSMITTED:
        base = 58
    else:
        base = 40
    if matches(claim, r"unexpected|surprise|emergency") and base < 92 and realized:
        base += 10
    score = min(100, base + round(cross * .12))
    if assertion.negation_markers:
        score = min(score, 55)
    caps = {AssertionType.EXPECTATION: 60, AssertionType.CONDITIONAL_SCENARIO: 55,
            AssertionType.SPECULATION: 30, AssertionType.UNKNOWN: 35}
    score = min(score, caps.get(assertion.assertion_type, 100))
    return score, cross, 65 if matches(claim, MONETARY + "|" + MACRO) else 48


def evidence_quality(source: SourceSpec, url: str, published_at: datetime | None,
                     retrieved_at: datetime, assertion: AssertionDecision,
                     relevance: RelevanceDecision, title: str, independent_count: int = 1) -> EvidenceQuality:
    try:
        parsed = urlsplit(url)
        trace = 20 if parsed.scheme in {"http", "https"} and parsed.netloc and parsed.path not in {"", "/"} else 0
    except ValueError:
        trace = 0
    reliable_time = bool(published_at and published_at.tzinfo and -3600 <= (retrieved_at - published_at).total_seconds())
    authority = 20 if source.source_type in {"Primary", "Official"} else {SourceTier.TIER_1: 18, SourceTier.TIER_2: 15, SourceTier.TIER_3: 10}.get(source.tier, 0)
    specificity = (10 if relevance.supporting_evidence else 0) + (10 if assertion.action or re.search(r"\d", title) else 0)
    assertion_support = 20 if assertion.assertion_type in {AssertionType.REALIZED_EVENT, AssertionType.ANNOUNCED_DECISION, AssertionType.REPORTED_OBSERVATION} else 12 if assertion.assertion_type in {AssertionType.EXPECTATION, AssertionType.CONDITIONAL_SCENARIO} else 0
    parts = {"traceability": trace, "source_authority": authority, "timestamp_reliability": 15 if reliable_time else 0,
             "specificity": specificity, "assertion_support": assertion_support,
             "independent_corroboration": min(15, max(0, independent_count - 1) * 8)}
    basis = "primary_source_report" if source.source_type in {"Primary", "Official"} else "independent_reports" if independent_count >= 2 else "single_secondary_report"
    return EvidenceQuality(min(100, sum(parts.values())), parts, basis, "evidence_heuristic_not_fact_verification")


def memory_for(title: str, summary: str, published_at: datetime | None, assertion: AssertionDecision,
               identity_context: str = "", *, url: str = "", reconstructed: bool = False) -> dict[str, Any]:
    normalized = text(title)
    period_pattern = r"\b(?:january|february|march|april|may|june|july|august|september|october|november|december)\s+(?:\d{1,2}(?: to \d{1,2})?\s+)?\d{4}\b|\b\d{4} q[1-4]\b|\b\d{4} \d{1,2} \d{1,2}\b"
    periodic = matches(title, r"cpi|payroll|gdp|monthly|quarterly|auction|weekly|inflation data|monetary policy committee|policy decision") or (
        matches(title, r"economic developments|economic report") and matches(" ".join(summary_claims(summary)), MACRO))
    session_event = matches(f"{title} {summary}", r"circuit breaker|trading session|market session")
    period = re.search(period_pattern, normalized)
    session_period = re.search(period_pattern, text(" ".join(summary_claims(summary)))) if session_event else None
    family = normalized.replace(period.group(0), " release period ") if period else normalized
    family = re.sub(r"\b(?:update|updated|\d+(?:\.\d+)?)\b", " ", family)
    family = re.sub(r"\s+", " ", family).strip()
    supported_claim = f"{title} {' '.join(summary_claims(summary))}"
    quantitative = tuple(sorted(set(re.findall(r"\b\d+(?:\.\d+)?\s*(?:percent|billion|million|bps|basis points)|\d+(?:\.\d+)?%", supported_claim.lower()))))[:12]
    claim = text(supported_claim)
    developments = tuple(word for word in ("approved", "resolved", "revised", "suspended", "resumed", "defaulted", "implemented", "withdrawn", "cut", "held", "raised", "lowered")
                         if matches(claim, word) and not re.search(
                             r"\b(?:not|never|no|could|may|might|would)\b.{0,30}\b" + word + r"\b", claim))
    return {"schema_version": EDITORIAL_VERSION, "family_key": fingerprint(identity_context + "|" + family),
            "issue_key": period.group(0) if periodic and period else None,
            "fact_fingerprint": fingerprint(text(f"{title} {summary}")),
            "quantitative_evidence": quantitative, "developments": developments,
            "assertion_type": assertion.assertion_type.value,
            "published_at": published_at.isoformat() if published_at else None,
            "identity_evidence_complete": bool(url and published_at and published_at.tzinfo and not reconstructed),
            "publication_fingerprint": fingerprint(url + "|" + published_at.isoformat()) if url and published_at else None,
            "session_key": (session_period or period).group(0) if session_event and (session_period or period) else None,
            "claim_text_present": bool(summary.strip()),
            "supported_development": assertion.assertion_type in {
                AssertionType.ANNOUNCED_DECISION, AssertionType.REPORTED_OBSERVATION, AssertionType.REALIZED_EVENT}
                and not assertion.negation_markers,
            "measured_claim": bool(summary_claims(summary))}


def assess_event(title: str, summary: str, source: SourceSpec, url: str,
                 published_at: datetime | None, retrieved_at: datetime,
                 region_terms: Sequence[tuple[EventRegion, Sequence[str]]] = (), *,
                 reconstructed: bool = False) -> EditorialAssessment:
    assertion = assertion_for(title, summary)
    relevance = relevance_for(title, summary)
    if (assertion.assertion_type == AssertionType.UNKNOWN and relevance.eligible
            and source.source_type in {"Primary", "Official"} and published_at and url
            and assertion.evidence_references == ("headline",) and not assertion.negation_markers):
        # Authenticate only the existence of a financial publication, not an implied policy action.
        assertion = replace(assertion, assertion_type=AssertionType.REPORTED_OBSERVATION,
                            action="source_publication", evidence_references=("headline", "official_publication_metadata"))
    geography = geography_for(title, summary, source, region_terms)
    market_claim = " ".join(summary_claims(summary)) if assertion.evidence_references == ("source_claim:financial",) else f"{title} {' '.join(summary_claims(summary))}"
    markets = affected_markets(market_claim) if relevance.eligible else ()
    materiality, cross, narrative = materiality_for_assessment(title, summary, assertion, relevance, markets)
    quality = evidence_quality(source, url, published_at, retrieved_at, assertion, relevance, title)
    valid_time = bool(published_at and published_at.tzinfo and -3600 <= (retrieved_at - published_at).total_seconds() <= 96 * 3600)
    supported = assertion.assertion_type in {AssertionType.REALIZED_EVENT, AssertionType.ANNOUNCED_DECISION, AssertionType.REPORTED_OBSERVATION} and not assertion.negation_markers
    override_claim = " ".join(summary_claims(summary)) if assertion.evidence_references == ("source_claim:financial",) else title
    override = bool(relevance.eligible and supported and valid_time and quality.components["traceability"] > 0
                    and quality.value >= 70 and materiality >= 85 and (
        matches(override_claim, EXCEPTIONAL) or matches(override_claim, r"unexpected|surprise|emergency")
    ))
    reason = "supported_current_material_financial_event" if override else "assertion_evidence_or_materiality_not_override_eligible"
    actor_identity = assertion.actor
    if actor_identity is None and source.source_type in {"Primary", "Official"}:
        prefix = source.source_id.split("_")[0]
        actor_identity = prefix if prefix in {"fed", "sec", "ecb", "boe", "hkma", "hkex", "boj", "rbi", "bok", "pboc"} else None
    identity_context = geography.canonical_editorial_region.value + "|" + (actor_identity or "unspecified_actor")
    return EditorialAssessment(assertion, relevance, geography, quality, source.markets, markets, materiality,
                               cross, narrative, override, reason, memory_for(title, summary, published_at, assertion, identity_context,
                                                                           url=url, reconstructed=reconstructed))


class NoveltyIndex:
    """One bounded history pass per edition, not one full scan per candidate."""

    def __init__(self, records: Iterable[dict[str, Any]], now: datetime, *, history_available: bool = True):
        self.available = history_available
        self.partial_legacy_history = False
        self.by_family: dict[str, dict[str, Any]] = {}
        for record in records:
            try:
                when = datetime.fromisoformat(str(record.get("evaluated_at", "")).replace("Z", "+00:00"))
                if not when.tzinfo or not 0 <= (now - when).total_seconds() <= 21 * 86400:
                    continue
            except (ValueError, TypeError):
                continue
            for selected in record.get("selected_event_audits", [])[:50]:
                memory = selected.get("editorial_memory") or {}
                key = memory.get("family_key")
                if not key:
                    self.partial_legacy_history = True
                    continue
                prior = self.by_family.get(key)
                if prior is None or when.timestamp() > prior["_timestamp"]:
                    self.by_family[key] = {**memory, "selected_at": when.isoformat(), "_timestamp": when.timestamp()}

    def decide(self, current: dict[str, Any]) -> NoveltyDecision:
        if not self.available:
            return NoveltyDecision(reason="history_missing_or_corrupt")
        prior = self.by_family.get(current.get("family_key"))
        if prior is None:
            if self.partial_legacy_history:
                return NoveltyDecision(reason="legacy_history_has_no_fact_fingerprints")
            return NoveltyDecision(NoveltyStatus.NEW_EVENT, "not_in_retained_editorial_history")
        when = prior["selected_at"]
        if not current.get("identity_evidence_complete") or not prior.get("identity_evidence_complete"):
            return NoveltyDecision(NoveltyStatus.UNKNOWN, "incomplete_event_identity_evidence", when)
        if current.get("session_key") and prior.get("session_key") and current["session_key"] != prior["session_key"]:
            return NoveltyDecision(NoveltyStatus.PERIODIC_NEW_OCCURRENCE, "new_explicit_market_session", when)
        if current.get("issue_key") and prior.get("issue_key") and current["issue_key"] != prior["issue_key"]:
            return NoveltyDecision(NoveltyStatus.PERIODIC_NEW_OCCURRENCE, "new_explicit_release_period", when)
        if current.get("fact_fingerprint") == prior.get("fact_fingerprint"):
            same_publication = current.get("publication_fingerprint") == prior.get("publication_fingerprint")
            same_time = current.get("published_at") == prior.get("published_at")
            same_period = bool(current.get("issue_key") and current["issue_key"] == prior.get("issue_key"))
            if same_publication or same_period or (same_time and current.get("claim_text_present") and prior.get("claim_text_present")):
                return NoveltyDecision(NoveltyStatus.UNCHANGED, "same_retained_event_facts", when)
            return NoveltyDecision(NoveltyStatus.UNKNOWN, "matching_text_without_proven_same_occurrence", when)
        current_actions = set(current.get("developments", ()))
        prior_actions = set(prior.get("developments", ()))
        new_quantities, old_quantities = current.get("quantitative_evidence", ()), prior.get("quantitative_evidence", ())
        quantities_changed = bool(new_quantities and old_quantities and tuple(new_quantities) != tuple(old_quantities)) and (
            "revised" in current_actions or current.get("assertion_type") == AssertionType.ANNOUNCED_DECISION.value
            or material_quantity_change(new_quantities, old_quantities))
        if current.get("supported_development") and (current_actions - prior_actions or (
                quantities_changed and current.get("measured_claim") and prior.get("measured_claim"))):
            return NoveltyDecision(NoveltyStatus.MATERIAL_UPDATE, "new_supported_outcome_or_revised_measurement", when)
        return NoveltyDecision(NoveltyStatus.UNKNOWN, "text_changed_without_proven_material_development", when)


def material_quantity_change(current: Sequence[str], prior: Sequence[str]) -> bool:
    """Conservative replay filter, not calibrated market-impact scoring."""
    def measures(values):
        result = {}
        for value in values:
            match = re.fullmatch(r"(\d+(?:\.\d+)?)\s*(percent|%|billion|million|bps|basis points)", value)
            if match:
                unit = {"%": "percent", "basis points": "bps"}.get(match[2], match[2])
                result.setdefault(unit, []).append(float(match[1]))
        return {unit: sorted(values) for unit, values in result.items()}
    new, old = measures(current), measures(prior)
    for unit in new.keys() & old.keys():
        if len(new[unit]) != len(old[unit]):
            continue
        floor = .25 if unit == "percent" else 5 if unit == "bps" else 0
        if any(abs(a-b) > 0 and abs(a-b) >= max(floor, abs(b)*.2) for a, b in zip(new[unit], old[unit])):
            return True
    return False
