from __future__ import annotations

import email.utils
import hashlib
import html
import json
import math
import re
import socket
import ssl
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Iterable, Sequence

from app.fiona_source_registry import EventRegion, SourceSpec, SourceTier


USER_AGENT = "Mozilla/5.0 FionaIntelligence/3.1 (+public-feed-validator)"
DEFAULT_TIMEOUT_SECONDS = 12
MAX_FEED_BYTES = 4 * 1024 * 1024
QUALITY_FLOOR = 40
DEFAULT_SELECTION_LIMIT = 10
REGIONAL_TARGETS: dict[EventRegion, float] = {
    EventRegion.US_EU: 0.60,
    EventRegion.GREATER_CHINA: 0.30,
    EventRegion.REST_OF_WORLD: 0.10,
}


class FreshnessStatus(str, Enum):
    CURRENT = "current"
    RECENT = "recent"
    STALE = "stale"
    UNKNOWN = "unknown"


class SourceHealthStatus(str, Enum):
    OK = "ok"
    EMPTY = "empty"
    TIMEOUT = "timeout"
    RATE_LIMITED = "rate_limited"
    INVALID_RESPONSE = "invalid_response"
    HTTP_ERROR = "http_error"
    DISABLED = "disabled"


@dataclass(frozen=True)
class SourceProvenance:
    source_id: str
    source_name: str
    source_url: str
    original_language: str
    original_title: str
    original_text_snippet: str
    published_at: datetime | None
    retrieved_at: datetime
    publisher_region: EventRegion
    event_region: EventRegion
    source_tier: SourceTier
    independence_group: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "source_name": self.source_name,
            "source_url": self.source_url,
            "original_language": self.original_language,
            "original_title": self.original_title,
            "original_text_snippet": self.original_text_snippet,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "retrieved_at": self.retrieved_at.isoformat(),
            "publisher_region": self.publisher_region.value,
            "event_region": self.event_region.value,
            "source_tier": int(self.source_tier),
            "independence_group": self.independence_group,
        }


@dataclass(frozen=True)
class NormalizedCoverageEvent:
    event_id: str
    source_id: str
    event_region: EventRegion
    source_tier: SourceTier
    independence_group: str
    published_at: datetime | None
    retrieved_at: datetime
    freshness: FreshnessStatus
    freshness_score: int
    entities: tuple[str, ...]
    markets: tuple[str, ...]
    category: str
    materiality: int
    cross_market_impact: int
    narrative_relevance: int
    normalized_headline: str
    normalized_fact: str
    canonical_url: str
    source_provenance: SourceProvenance
    material_override: bool = False
    override_reason: str = ""

    def to_dict(self, *, include_snippet: bool = False) -> dict[str, Any]:
        provenance = self.source_provenance.to_dict()
        if not include_snippet:
            provenance.pop("original_text_snippet", None)
        return {
            "event_id": self.event_id,
            "source_id": self.source_id,
            "event_region": self.event_region.value,
            "source_tier": int(self.source_tier),
            "independence_group": self.independence_group,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "retrieved_at": self.retrieved_at.isoformat(),
            "freshness": self.freshness.value,
            "freshness_score": self.freshness_score,
            "entities": list(self.entities),
            "markets": list(self.markets),
            "category": self.category,
            "materiality": self.materiality,
            "cross_market_impact": self.cross_market_impact,
            "narrative_relevance": self.narrative_relevance,
            "normalized_headline": self.normalized_headline,
            "normalized_fact": self.normalized_fact,
            "canonical_url": self.canonical_url,
            "source_provenance": provenance,
            "material_override": self.material_override,
            "override_reason": self.override_reason,
        }


@dataclass(frozen=True)
class SourceHealth:
    source_id: str
    status: SourceHealthStatus
    retrieved_at: datetime
    item_count: int = 0
    normalized_count: int = 0
    invalid_timestamp_count: int = 0
    duration_ms: int = 0
    error_category: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "status": self.status.value,
            "retrieved_at": self.retrieved_at.isoformat(),
            "item_count": self.item_count,
            "normalized_count": self.normalized_count,
            "invalid_timestamp_count": self.invalid_timestamp_count,
            "duration_ms": self.duration_ms,
            "error_category": self.error_category,
        }


@dataclass
class EventCluster:
    cluster_id: str
    events: list[NormalizedCoverageEvent]
    event_region: EventRegion
    source_tier: SourceTier
    normalized_headline: str
    category: str
    materiality: int
    cross_market_impact: int
    narrative_relevance: int
    freshness_score: int
    source_count: int
    independent_source_count: int
    duplicate_count: int = 0
    syndication_count: int = 0
    stale: bool = False
    material_override: bool = False
    override_reason: str = ""
    ranking_score: float = 0.0

    @property
    def quality_score(self) -> float:
        authority = {SourceTier.TIER_1: 12, SourceTier.TIER_2: 7, SourceTier.TIER_3: 3}.get(
            self.source_tier,
            0,
        )
        independent_confirmation = min(12, max(0, self.independent_source_count - 1) * 6)
        return min(100.0, self.materiality + authority + independent_confirmation)

    def to_dict(self) -> dict[str, Any]:
        return {
            "cluster_id": self.cluster_id,
            "event_region": self.event_region.value,
            "source_tier": int(self.source_tier),
            "normalized_headline": self.normalized_headline,
            "category": self.category,
            "materiality": self.materiality,
            "cross_market_impact": self.cross_market_impact,
            "narrative_relevance": self.narrative_relevance,
            "freshness_score": self.freshness_score,
            "source_count": self.source_count,
            "independent_source_count": self.independent_source_count,
            "duplicate_count": self.duplicate_count,
            "syndication_count": self.syndication_count,
            "stale": self.stale,
            "material_override": self.material_override,
            "override_reason": self.override_reason,
            "quality_score": round(self.quality_score, 2),
            "ranking_score": round(self.ranking_score, 2),
        }


@dataclass(frozen=True)
class ClusterDiagnostics:
    duplicate_rejection_count: int = 0
    syndication_rejection_count: int = 0


@dataclass
class CoverageEvaluation:
    evaluated_at: datetime
    candidate_events: list[NormalizedCoverageEvent]
    clusters: list[EventCluster]
    qualified_clusters: list[EventCluster]
    selected_clusters: list[EventCluster]
    source_health: list[SourceHealth]
    metrics: dict[str, Any]

    def to_dict(self, *, include_events: bool = False) -> dict[str, Any]:
        payload = {
            "evaluated_at": self.evaluated_at.isoformat(),
            "metrics": self.metrics,
            "selected_clusters": [cluster.to_dict() for cluster in self.selected_clusters],
            "source_health": [health.to_dict() for health in self.source_health],
        }
        if include_events:
            payload["candidate_event_records"] = [event.to_dict() for event in self.candidate_events]
        return payload


def ensure_aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def parse_source_timestamp(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return ensure_aware(value).astimezone(timezone.utc)
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = email.utils.parsedate_to_datetime(text)
        if parsed is not None:
            return ensure_aware(parsed).astimezone(timezone.utc)
    except (TypeError, ValueError, OverflowError):
        pass
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except (TypeError, ValueError, OverflowError):
        return None
    return ensure_aware(parsed).astimezone(timezone.utc)


def clean_source_text(value: Any, *, limit: int = 1200) -> str:
    text = html.unescape(re.sub(r"<[^>]+>", " ", str(value or "")))
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit]


def canonicalize_url(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    try:
        parsed = urllib.parse.urlsplit(raw)
        filtered = [
            (key, item)
            for key, item in urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
            if not key.lower().startswith("utm_") and key.lower() not in {"ref", "source", "outputtype"}
        ]
        path = re.sub(r"/{2,}", "/", parsed.path or "/").rstrip("/") or "/"
        return urllib.parse.urlunsplit(
            (parsed.scheme.lower(), parsed.netloc.lower(), path, urllib.parse.urlencode(filtered), "")
        )
    except ValueError:
        return raw


def normalized_text(value: str) -> str:
    text = clean_source_text(value, limit=4000).casefold()
    text = re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE)
    return re.sub(r"\s+", " ", text).strip()


def has_term(text: str, term: str) -> bool:
    normalized = normalized_text(term)
    if any("\u3400" <= char <= "\u9fff" for char in normalized):
        return normalized in text
    return bool(re.search(rf"(?<!\w){re.escape(normalized)}(?!\w)", text))


STOPWORDS = {
    "a",
    "an",
    "and",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "this",
    "to",
    "with",
    "says",
    "said",
    "update",
    "news",
}


def significant_tokens(value: str) -> set[str]:
    return {
        token
        for token in normalized_text(value).split()
        if len(token) > 2 and token not in STOPWORDS and not token.isdigit()
    }


def text_similarity(left: str, right: str) -> float:
    left_tokens = significant_tokens(left)
    right_tokens = significant_tokens(right)
    if not left_tokens or not right_tokens:
        return 1.0 if normalized_text(left) == normalized_text(right) else 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


REGION_KEYWORDS: tuple[tuple[EventRegion, tuple[str, ...]], ...] = (
    (
        EventRegion.GREATER_CHINA,
        (
            "people's bank of china",
            "pboc",
            "china",
            "chinese",
            "beijing",
            "shanghai",
            "shenzhen",
            "hong kong",
            "hkma",
            "hkex",
            "taiwan",
            "taipei",
            "twse",
            "中国",
            "央行",
            "香港",
            "台湾",
        ),
    ),
    (
        EventRegion.REST_OF_WORLD,
        (
            "bank of japan",
            "boj",
            "japan",
            "tokyo",
            "reserve bank of india",
            "rbi",
            "india",
            "bank of korea",
            "south korea",
            "seoul",
            "reserve bank of australia",
            "rba",
            "australia",
            "monetary authority of singapore",
            "singapore",
            "brazil",
            "banco central",
            "japan ministry of finance",
        ),
    ),
    (
        EventRegion.US_EU,
        (
            "federal reserve",
            "fomc",
            "u.s. treasury",
            "us treasury",
            "sec",
            "securities and exchange commission",
            "cftc",
            "united states",
            "u.s.",
            "wall street",
            "s&p 500",
            "nasdaq",
            "european central bank",
            "ecb",
            "euro area",
            "eurozone",
            "european union",
            "europe",
            "bank of england",
            "united kingdom",
            "britain",
            "london",
        ),
    ),
)


def infer_event_region(title: str, summary: str, source: SourceSpec) -> EventRegion:
    for text in (title, summary):
        searchable = normalized_text(text)
        regions = {
            region for region, keywords in REGION_KEYWORDS
            if any(has_term(searchable, keyword) for keyword in keywords)
        }
        if len(regions) == 1:
            return next(iter(regions))
        if len(regions) > 1:
            return EventRegion.GLOBAL
    return source.default_event_region


CATEGORY_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("regulation", ("sec", "cftc", "regulator", "regulation", "enforcement", "lawsuit", "rulemaking", "监管")),
    ("macro_policy", ("central bank", "federal reserve", "fomc", "ecb", "interest rate", "inflation", "cpi", "gdp", "employment", "treasury", "央行")),
    ("rwa", ("tokenized", "tokenization", "real world asset", "rwa", "buidl", "ondo")),
    ("crypto", ("bitcoin", "btc", "ethereum", "eth", "crypto", "stablecoin", "blockchain", "defi")),
    ("market", ("stocks", "shares", "equities", "bond", "yield", "index", "market", "nasdaq", "s&p")),
)


def infer_category(title: str, summary: str, source: SourceSpec) -> str:
    searchable = normalized_text(f"{title} {summary}")
    for category, keywords in CATEGORY_KEYWORDS:
        if any(has_term(searchable, keyword) for keyword in keywords):
            return category
    return source.content_categories[0] if source.content_categories else "other"


ENTITY_MAP: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Federal Reserve", ("federal reserve", "fomc", "powell")),
    ("SEC", ("securities and exchange commission", " sec ")),
    ("ECB", ("european central bank", "ecb")),
    ("Bank of England", ("bank of england",)),
    ("PBOC", ("people's bank of china", "pboc", "中国人民银行")),
    ("HKMA", ("hong kong monetary authority", "hkma")),
    ("HKEX", ("hong kong exchanges", "hkex")),
    ("BOJ", ("bank of japan", "boj")),
    ("RBI", ("reserve bank of india", "rbi")),
    ("Bank of Korea", ("bank of korea",)),
    ("RBA", ("reserve bank of australia", "rba")),
    ("Bitcoin", ("bitcoin", "btc")),
    ("Ethereum", ("ethereum", "eth")),
)


def infer_entities(title: str, summary: str) -> tuple[str, ...]:
    searchable = f" {normalized_text(f'{title} {summary}')} "
    return tuple(name for name, aliases in ENTITY_MAP if any(has_term(searchable, alias) for alias in aliases))


def infer_markets(title: str, summary: str, source: SourceSpec) -> tuple[str, ...]:
    searchable = normalized_text(f"{title} {summary}")
    markets = set(source.markets)
    if any(word in searchable for word in ("bitcoin", "ethereum", "crypto", "stablecoin", "blockchain")):
        markets.add("crypto")
    if any(word in searchable for word in ("stock", "equity", "nasdaq", "s&p", "shares", "hkex", "twse")):
        markets.add("equities")
    if any(word in searchable for word in ("bond", "yield", "treasury", "interest rate", "central bank")):
        markets.add("rates")
    if any(word in searchable for word in ("dollar", "yen", "yuan", "euro", "sterling", "currency", "fx")):
        markets.add("fx")
    if any(word in searchable for word in ("commodity", "oil", "gold")):
        markets.add("commodities")
    return tuple(sorted(markets))


def freshness_window_hours(category: str) -> int:
    return {
        "macro_policy": 96,
        "regulation": 96,
        "rwa": 72,
        "market": 48,
        "crypto": 36,
    }.get(category, 48)


def freshness_for(
    published_at: datetime | None,
    retrieved_at: datetime,
    category: str,
) -> tuple[FreshnessStatus, int]:
    if published_at is None:
        return FreshnessStatus.UNKNOWN, 0
    age_hours = (ensure_aware(retrieved_at) - ensure_aware(published_at)).total_seconds() / 3600
    if age_hours < -1:
        return FreshnessStatus.UNKNOWN, 0
    if age_hours <= 4:
        return FreshnessStatus.CURRENT, 100
    if age_hours <= 12:
        return FreshnessStatus.CURRENT, 88
    if age_hours <= 24:
        return FreshnessStatus.RECENT, 74
    window = freshness_window_hours(category)
    if age_hours <= window:
        return FreshnessStatus.RECENT, max(45, round(74 - (age_hours - 24) * 24 / max(1, window - 24)))
    return FreshnessStatus.STALE, 0


MATERIAL_OVERRIDE_KEYWORDS = (
    "emergency rate decision",
    "unexpected rate decision",
    "currency intervention",
    "market intervention",
    "sovereign default",
    "systemic financial risk",
    "systemic banking risk",
    "bank run",
    "trading halt",
    "exchange halt",
    "major cyberattack",
    "major hack",
    "capital controls",
    "declares war",
    "war breaks out",
)


def contains_material_override(searchable: str) -> bool:
    return any(re.search(rf"\b{re.escape(term)}\b", searchable) for term in MATERIAL_OVERRIDE_KEYWORDS)


def materiality_for(
    title: str,
    summary: str,
    source: SourceSpec,
    category: str,
    markets: Sequence[str],
) -> tuple[int, int, int, bool, str]:
    searchable = normalized_text(f"{title} {summary}")
    tier_points = {SourceTier.TIER_1: 24, SourceTier.TIER_2: 17, SourceTier.TIER_3: 12}.get(
        source.tier,
        5,
    )
    score = tier_points
    exceptional_event = contains_material_override(searchable)
    if exceptional_event:
        score += 50
    elif any(
        term in searchable
        for term in (
            "rate decision",
            "interest rate",
            "monetary policy",
            "inflation",
            "consumer price",
            "gross domestic product",
            "payroll",
            "unemployment",
            "sanction",
            "tariff",
            "enforcement action",
            "new regulation",
            "policy statement",
        )
    ):
        score += 31
    elif category in {"macro_policy", "regulation"}:
        score += 23
    elif category in {"rwa", "crypto", "market"}:
        score += 15
    if any(term in searchable for term in ("unexpected", "surprise", "emergency", "record", "largest")):
        score += 10
    market_count = len(set(markets))
    cross_market = min(100, 20 + max(0, market_count - 1) * 24)
    if category in {"macro_policy", "regulation"}:
        cross_market = max(cross_market, 58)
    score += round(cross_market * 0.12)
    narrative_relevance = 65 if category in {"macro_policy", "regulation", "rwa"} else 48
    materiality = max(0, min(100, score))
    material_override = materiality >= 85 or exceptional_event
    override_reason = "systemic_or_exceptional_material_event" if material_override else ""
    return materiality, cross_market, narrative_relevance, material_override, override_reason


def stable_event_id(source_id: str, url: str, title: str, published_at: datetime | None) -> str:
    timestamp = published_at.isoformat() if published_at else "unknown-time"
    raw = "|".join((source_id, canonicalize_url(url), normalized_text(title), timestamp))
    return "coverage_" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]


def normalize_source_item(
    raw: dict[str, Any],
    source: SourceSpec,
    *,
    retrieved_at: datetime,
    normalized_headline: str | None = None,
    normalized_fact: str | None = None,
) -> NormalizedCoverageEvent | None:
    title = clean_source_text(raw.get("title"), limit=500)
    if not title:
        return None
    summary = clean_source_text(raw.get("summary") or raw.get("description"), limit=1200)
    source_url = str(raw.get("url") or raw.get("link") or "").strip()
    published_value = (
        raw["original_published_at"] if "original_published_at" in raw
        else raw.get("published_at") or raw.get("published")
    )
    published_at = parse_source_timestamp(published_value)
    event_region = infer_event_region(title, summary, source)
    category = infer_category(title, summary, source)
    entities = infer_entities(title, summary)
    markets = infer_markets(title, summary, source)
    freshness, freshness_score = freshness_for(published_at, retrieved_at, category)
    materiality, cross_market, narrative, override, override_reason = materiality_for(
        title,
        summary,
        source,
        category,
        markets,
    )
    provenance = SourceProvenance(
        source_id=source.source_id,
        source_name=source.name,
        source_url=source_url,
        original_language=source.language,
        original_title=title,
        original_text_snippet=summary,
        published_at=published_at,
        retrieved_at=ensure_aware(retrieved_at),
        publisher_region=source.publisher_region,
        event_region=event_region,
        source_tier=source.tier,
        independence_group=source.independence_group,
    )
    return NormalizedCoverageEvent(
        event_id=stable_event_id(source.source_id, source_url, title, published_at),
        source_id=source.source_id,
        event_region=event_region,
        source_tier=source.tier,
        independence_group=source.independence_group,
        published_at=published_at,
        retrieved_at=ensure_aware(retrieved_at),
        freshness=freshness,
        freshness_score=freshness_score,
        entities=entities,
        markets=markets,
        category=category,
        materiality=materiality,
        cross_market_impact=cross_market,
        narrative_relevance=narrative,
        normalized_headline=clean_source_text(normalized_headline or title, limit=500),
        normalized_fact=clean_source_text(normalized_fact or summary or title, limit=800),
        canonical_url=canonicalize_url(source_url),
        source_provenance=provenance,
        material_override=override,
        override_reason=override_reason,
    )


def _first_text(entry: ET.Element, tags: Sequence[str]) -> str:
    for tag in tags:
        found = entry.find(tag)
        if found is not None and found.text:
            return found.text.strip()
    return ""


def _first_link(entry: ET.Element) -> str:
    direct = _first_text(entry, ("link",))
    if direct:
        return direct
    for child in entry.findall("{http://www.w3.org/2005/Atom}link"):
        href = child.attrib.get("href", "")
        if href:
            return href
    return ""


def parse_rss_payload(payload: bytes) -> list[dict[str, Any]]:
    root = ET.fromstring(payload)
    if root.tag.rsplit("}", 1)[-1].lower() not in {"rss", "feed", "rdf"}:
        raise ValueError("Unexpected feed schema")
    entries = list(root.findall(".//item")) or list(root.findall(".//{http://www.w3.org/2005/Atom}entry"))
    items: list[dict[str, Any]] = []
    for entry in entries:
        title = _first_text(entry, ("title", "{http://www.w3.org/2005/Atom}title"))
        if not title:
            continue
        summary = _first_text(
            entry,
            (
                "description",
                "summary",
                "{http://www.w3.org/2005/Atom}summary",
                "{http://purl.org/rss/1.0/modules/content/}encoded",
            ),
        )
        published = _first_text(
            entry,
            (
                "pubDate",
                "published",
                "updated",
                "{http://www.w3.org/2005/Atom}published",
                "{http://www.w3.org/2005/Atom}updated",
                "{http://purl.org/dc/elements/1.1/}date",
            ),
        )
        items.append({"title": title, "summary": summary, "url": _first_link(entry), "published_at": published})
    return items


def _nested_records(payload: Any, path: Sequence[str]) -> list[dict[str, Any]]:
    value = payload
    for key in path:
        if not isinstance(value, dict) or key not in value:
            raise ValueError("Missing JSON records path")
        value = value.get(key)
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    raise ValueError("Expected JSON records array")


def parse_json_payload(payload: bytes, source: SourceSpec) -> list[dict[str, Any]]:
    data = json.loads(payload.decode("utf-8"))
    records = _nested_records(data, source.json_records_path)
    items: list[dict[str, Any]] = []
    for record in records:
        items.append(
            {
                "title": record.get(source.json_title_field),
                "url": record.get(source.json_url_field),
                "published_at": record.get(source.json_published_field),
                "summary": record.get(source.json_summary_field),
            }
        )
    return items


def fetch_source_items(source: SourceSpec, timeout: int = DEFAULT_TIMEOUT_SECONDS) -> list[dict[str, Any]]:
    request = urllib.request.Request(
        source.endpoint,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json,application/rss+xml,application/atom+xml,text/xml,*/*",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = response.read(MAX_FEED_BYTES + 1)
    if len(payload) > MAX_FEED_BYTES:
        raise ValueError("Source response exceeds the bounded feed size")
    if source.retrieval_method == "json":
        return parse_json_payload(payload, source)
    return parse_rss_payload(payload)


SourceFetcher = Callable[[SourceSpec, int], list[dict[str, Any]]]


def collect_source(
    source: SourceSpec,
    *,
    retrieved_at: datetime,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
    fetcher: SourceFetcher = fetch_source_items,
) -> tuple[list[NormalizedCoverageEvent], SourceHealth]:
    started = datetime.now(timezone.utc)
    if not source.active_for_shadow:
        return [], SourceHealth(source.source_id, SourceHealthStatus.DISABLED, ensure_aware(retrieved_at))
    try:
        raw_items = fetcher(source, timeout)
    except (TimeoutError, socket.timeout):
        status = SourceHealthStatus.TIMEOUT
        raw_items = []
        error = "timeout"
    except urllib.error.HTTPError as exc:
        status = SourceHealthStatus.RATE_LIMITED if exc.code == 429 else SourceHealthStatus.HTTP_ERROR
        raw_items = []
        error = f"http_{exc.code}"
    except (ET.ParseError, json.JSONDecodeError, UnicodeDecodeError, ValueError, TypeError):
        status = SourceHealthStatus.INVALID_RESPONSE
        raw_items = []
        error = "invalid_response"
    except urllib.error.URLError as exc:
        if isinstance(exc.reason, (TimeoutError, socket.timeout)):
            status = SourceHealthStatus.TIMEOUT
            error = "timeout"
        elif isinstance(exc.reason, ssl.SSLCertVerificationError):
            status = SourceHealthStatus.HTTP_ERROR
            error = "tls_verification_error"
        else:
            status = SourceHealthStatus.HTTP_ERROR
            error = "network_error"
        raw_items = []
    except OSError:
        status = SourceHealthStatus.HTTP_ERROR
        raw_items = []
        error = "network_error"
    else:
        if not isinstance(raw_items, list):
            status, error, raw_items = SourceHealthStatus.INVALID_RESPONSE, "schema_drift", []
        else:
            status = SourceHealthStatus.OK if raw_items else SourceHealthStatus.EMPTY
            error = ""
    events = [
        event
        for item in raw_items[:50]
        if isinstance(item, dict)
        for event in [normalize_source_item(item, source, retrieved_at=retrieved_at)]
        if event is not None
    ]
    invalid_timestamps = sum(1 for event in events if event.published_at is None)
    if raw_items and not events:
        status, error = SourceHealthStatus.INVALID_RESPONSE, "missing_titles"
    duration = max(0, round((datetime.now(timezone.utc) - started).total_seconds() * 1000))
    return events, SourceHealth(
        source_id=source.source_id,
        status=status,
        retrieved_at=ensure_aware(retrieved_at),
        item_count=len(raw_items),
        normalized_count=len(events),
        invalid_timestamp_count=invalid_timestamps,
        duration_ms=duration,
        error_category=error,
    )


def collect_sources(
    sources: Iterable[SourceSpec],
    *,
    retrieved_at: datetime,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
    fetcher: SourceFetcher = fetch_source_items,
    max_workers: int = 6,
) -> tuple[list[NormalizedCoverageEvent], list[SourceHealth]]:
    active = sorted((source for source in sources if source.active_for_shadow), key=lambda item: item.source_id)
    if not active:
        return [], []
    events: list[NormalizedCoverageEvent] = []
    health: list[SourceHealth] = []
    with ThreadPoolExecutor(max_workers=min(max_workers, len(active))) as executor:
        futures = {
            executor.submit(
                collect_source,
                source,
                retrieved_at=retrieved_at,
                timeout=timeout,
                fetcher=fetcher,
            ): source.source_id
            for source in active
        }
        for future in as_completed(futures):
            try:
                source_events, source_health = future.result()
            except Exception:  # pragma: no cover - collect_source is the containment boundary.
                source_events = []
                source_health = SourceHealth(
                    source_id=futures[future],
                    status=SourceHealthStatus.INVALID_RESPONSE,
                    retrieved_at=ensure_aware(retrieved_at),
                    error_category="collector_boundary_error",
                )
            events.extend(source_events)
            health.append(source_health)
    return sorted(events, key=lambda item: item.event_id), sorted(health, key=lambda item: item.source_id)


def _event_time_distance_hours(left: NormalizedCoverageEvent, right: NormalizedCoverageEvent) -> float:
    if left.published_at is None or right.published_at is None:
        return math.inf
    return abs((left.published_at - right.published_at).total_seconds()) / 3600


def _match_kind(left: NormalizedCoverageEvent, right: NormalizedCoverageEvent) -> str | None:
    if left.canonical_url and left.canonical_url == right.canonical_url:
        return "exact_url"
    similarity = text_similarity(left.normalized_headline, right.normalized_headline)
    same_title = normalized_text(left.normalized_headline) == normalized_text(right.normalized_headline)
    if _event_time_distance_hours(left, right) > 36:
        return None
    if left.source_id == right.source_id and (same_title or similarity >= 0.62):
        return "same_source"
    if left.independence_group == right.independence_group and (same_title or similarity >= 0.58):
        return "syndicated"
    if _same_syndicated_copy(left, right):
        return "syndicated"
    if left.category != right.category or _event_time_distance_hours(left, right) > 36:
        return None
    target_regions = set(REGIONAL_TARGETS)
    if (
        left.event_region != right.event_region
        and left.event_region in target_regions
        and right.event_region in target_regions
        and not same_title
    ):
        return None
    entities_overlap = bool(set(left.entities) & set(right.entities))
    if same_title or (similarity >= 0.78 and left.event_region == right.event_region) or (
        entities_overlap and similarity >= 0.42
    ):
        return "independent_confirmation"
    return None


def _same_syndicated_copy(left: NormalizedCoverageEvent, right: NormalizedCoverageEvent) -> bool:
    first = normalized_text(left.source_provenance.original_text_snippet)
    second = normalized_text(right.source_provenance.original_text_snippet)
    return bool(len(first) >= 80 and len(second) >= 80 and first == second)


def independent_evidence_groups(events: Sequence[NormalizedCoverageEvent]) -> list[set[str]]:
    groups: list[set[str]] = []
    for event in sorted(events, key=lambda item: item.event_id):
        keys = {"owner:" + event.independence_group}
        if event.canonical_url:
            keys.add("url:" + event.canonical_url)
        snippet = normalized_text(event.source_provenance.original_text_snippet)
        if len(snippet) >= 80:
            keys.add("copy:" + hashlib.sha256(snippet.encode("utf-8")).hexdigest())
        overlapping = [group for group in groups if group & keys]
        for group in overlapping:
            keys.update(group)
            groups.remove(group)
        groups.append(keys)
    return groups


def _cluster_id(events: Sequence[NormalizedCoverageEvent]) -> str:
    raw = "|".join(sorted(event.event_id for event in events))
    return "cluster_" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]


def _cluster_region(events: Sequence[NormalizedCoverageEvent]) -> EventRegion:
    counts = Counter(event.event_region for event in events)
    return sorted(counts, key=lambda region: (-counts[region], region.value))[0]


def _cluster_from_events(
    events: list[NormalizedCoverageEvent],
    duplicate_count: int,
    syndication_count: int,
) -> EventCluster:
    representative = sorted(
        events,
        key=lambda item: (-item.materiality, int(item.source_tier) if item.source_tier else 99, item.event_id),
    )[0]
    unique_sources = {event.source_id for event in events}
    independence_groups = independent_evidence_groups(events)
    known_tiers = [event.source_tier for event in events if event.source_tier != SourceTier.UNKNOWN]
    tier = min(known_tiers, default=SourceTier.UNKNOWN)
    independent_bonus = min(12, max(0, len(independence_groups) - 1) * 4)
    materiality = min(100, max(event.materiality for event in events) + independent_bonus)
    overrides = [event for event in events if event.material_override]
    return EventCluster(
        cluster_id=_cluster_id(events),
        events=sorted(events, key=lambda item: item.event_id),
        event_region=_cluster_region(events),
        source_tier=tier,
        normalized_headline=representative.normalized_headline,
        category=representative.category,
        materiality=materiality,
        cross_market_impact=max(event.cross_market_impact for event in events),
        narrative_relevance=max(event.narrative_relevance for event in events),
        freshness_score=max(event.freshness_score for event in events),
        source_count=len(unique_sources),
        independent_source_count=len(independence_groups),
        duplicate_count=duplicate_count,
        syndication_count=syndication_count,
        stale=all(event.freshness in {FreshnessStatus.STALE, FreshnessStatus.UNKNOWN} for event in events),
        material_override=bool(overrides),
        override_reason=overrides[0].override_reason if overrides else "",
    )


def cluster_events(
    events: Sequence[NormalizedCoverageEvent],
) -> tuple[list[EventCluster], ClusterDiagnostics]:
    working: list[dict[str, Any]] = []
    duplicate_total = 0
    syndication_total = 0
    for event in sorted(events, key=lambda item: (item.normalized_headline.casefold(), item.event_id)):
        match_index: int | None = None
        match_kind: str | None = None
        for index, record in enumerate(working):
            kinds = [_match_kind(event, member) for member in record["events"]]
            matched = [kind for kind in kinds if kind]
            if matched:
                match_index = index
                priority = ("exact_url", "same_source", "syndicated", "independent_confirmation")
                match_kind = min(matched, key=priority.index)
                break
        if match_index is None:
            working.append({"events": [event], "duplicate_count": 0, "syndication_count": 0})
            continue
        record = working[match_index]
        record["events"].append(event)
        if match_kind in {"exact_url", "same_source"}:
            record["duplicate_count"] += 1
            duplicate_total += 1
        elif match_kind == "syndicated":
            record["syndication_count"] += 1
            syndication_total += 1
    clusters = [
        _cluster_from_events(record["events"], record["duplicate_count"], record["syndication_count"])
        for record in working
    ]
    clusters.sort(key=lambda item: item.cluster_id)
    return clusters, ClusterDiagnostics(duplicate_total, syndication_total)


def base_ranking_score(cluster: EventCluster) -> float:
    authority = {SourceTier.TIER_1: 100, SourceTier.TIER_2: 70, SourceTier.TIER_3: 40}.get(
        cluster.source_tier,
        10,
    )
    confirmation = min(100, 35 + max(0, cluster.independent_source_count - 1) * 25)
    return (
        cluster.materiality * 0.46
        + cluster.cross_market_impact * 0.13
        + cluster.freshness_score * 0.15
        + authority * 0.10
        + confirmation * 0.08
        + cluster.narrative_relevance * 0.08
    )


def rank_coverage_clusters(
    clusters: Sequence[EventCluster],
    *,
    limit: int = DEFAULT_SELECTION_LIMIT,
    quality_floor: int = QUALITY_FLOOR,
) -> tuple[list[EventCluster], list[EventCluster], int]:
    stale_rejections = sum(1 for cluster in clusters if cluster.stale)
    qualified = [
        cluster
        for cluster in clusters
        if not cluster.stale and cluster.quality_score >= quality_floor
    ]
    qualified.sort(key=lambda item: (-base_ranking_score(item), item.cluster_id))
    selected: list[EventCluster] = []
    remaining = list(qualified)

    overrides = [cluster for cluster in remaining if cluster.material_override]
    for cluster in overrides:
        cluster.ranking_score = base_ranking_score(cluster) + 100
        selected.append(cluster)
        remaining.remove(cluster)

    target_limit = max(limit, len(selected))
    while remaining and len(selected) < target_limit:
        selected_counts = Counter(cluster.event_region for cluster in selected)
        denominator = max(1, len(selected))

        def dynamic_score(cluster: EventCluster) -> tuple[float, float, str]:
            target = REGIONAL_TARGETS.get(cluster.event_region)
            regional_bonus = 0.0
            if target is not None:
                current_share = selected_counts[cluster.event_region] / denominator
                regional_bonus = max(-0.15, min(0.60, target - current_share)) * 40
            score = base_ranking_score(cluster) + regional_bonus
            return score, cluster.quality_score, cluster.cluster_id

        chosen = max(remaining, key=dynamic_score)
        chosen.ranking_score = dynamic_score(chosen)[0]
        selected.append(chosen)
        remaining.remove(chosen)
    return qualified, selected, stale_rejections


def _region_counts_from_events(events: Sequence[NormalizedCoverageEvent]) -> dict[str, int]:
    counter = Counter(event.event_region.value for event in events)
    return {region.value: counter.get(region.value, 0) for region in EventRegion}


def _region_counts_from_clusters(clusters: Sequence[EventCluster]) -> dict[str, int]:
    counter = Counter(cluster.event_region.value for cluster in clusters)
    return {region.value: counter.get(region.value, 0) for region in EventRegion}


def _shares(counts: dict[str, int]) -> dict[str, float]:
    total = sum(counts.values())
    return {key: round(value / total, 4) if total else 0.0 for key, value in counts.items()}


def coverage_metrics(
    events: Sequence[NormalizedCoverageEvent],
    clusters: Sequence[EventCluster],
    qualified: Sequence[EventCluster],
    selected: Sequence[EventCluster],
    diagnostics: ClusterDiagnostics,
    stale_rejections: int,
) -> dict[str, Any]:
    candidate_counts = _region_counts_from_events(events)
    selected_counts = _region_counts_from_clusters(selected)
    selected_shares = _shares(selected_counts)
    tier_counts = Counter(cluster.source_tier for cluster in selected)
    selected_total = len(selected)
    underweight: list[str] = []
    gap_reasons: dict[str, str] = {}
    qualified_by_region = Counter(cluster.event_region for cluster in qualified)
    for region, target in REGIONAL_TARGETS.items():
        actual = selected_shares.get(region.value, 0.0)
        if actual + 0.05 < target:
            underweight.append(region.value)
            gap_reasons[region.value] = (
                "no_qualified_event"
                if qualified_by_region[region] == 0
                else "higher_materiality_events_selected_elsewhere"
            )
    confirmation_distribution = Counter(cluster.independent_source_count for cluster in clusters)
    independent_groups = {
        event.independence_group for event in events if event.independence_group
    }
    sources = {event.source_id for event in events}
    unknown_selected = selected_counts.get(EventRegion.UNKNOWN.value, 0) + selected_counts.get(
        EventRegion.GLOBAL.value,
        0,
    )
    return {
        "candidate_events": len(events),
        "qualified_clusters": len(qualified),
        "selected_shadow_clusters": selected_total,
        "regional_candidate_counts": candidate_counts,
        "regional_selected_counts": selected_counts,
        "regional_selected_share": selected_shares,
        "tier_selected_counts": {
            "1": tier_counts[SourceTier.TIER_1],
            "2": tier_counts[SourceTier.TIER_2],
            "3": tier_counts[SourceTier.TIER_3],
            "0": tier_counts[SourceTier.UNKNOWN],
        },
        "tier1_share": round(tier_counts[SourceTier.TIER_1] / selected_total, 4) if selected_total else 0.0,
        "tier2_share": round(tier_counts[SourceTier.TIER_2] / selected_total, 4) if selected_total else 0.0,
        "tier3_share": round(tier_counts[SourceTier.TIER_3] / selected_total, 4) if selected_total else 0.0,
        "unknown_region_share": round(unknown_selected / selected_total, 4) if selected_total else 0.0,
        "source_diversity": len(sources),
        "independent_source_diversity": len(independent_groups),
        "duplicate_rejection_count": diagnostics.duplicate_rejection_count,
        "syndication_rejection_count": diagnostics.syndication_rejection_count,
        "stale_rejection_count": stale_rejections,
        "material_override_count": sum(1 for cluster in selected if cluster.material_override),
        "underweight_regions": underweight,
        "regional_gap_reason": gap_reasons,
        "confirmation_distribution": {
            str(key): value for key, value in sorted(confirmation_distribution.items())
        },
    }


def evaluate_global_coverage(
    events: Sequence[NormalizedCoverageEvent],
    *,
    evaluated_at: datetime,
    source_health: Sequence[SourceHealth] = (),
    limit: int = DEFAULT_SELECTION_LIMIT,
    quality_floor: int = QUALITY_FLOOR,
) -> CoverageEvaluation:
    clusters, diagnostics = cluster_events(events)
    qualified, selected, stale_rejections = rank_coverage_clusters(
        clusters,
        limit=limit,
        quality_floor=quality_floor,
    )
    metrics = coverage_metrics(
        events,
        clusters,
        qualified,
        selected,
        diagnostics,
        stale_rejections,
    )
    return CoverageEvaluation(
        evaluated_at=ensure_aware(evaluated_at),
        candidate_events=list(events),
        clusters=clusters,
        qualified_clusters=qualified,
        selected_clusters=selected,
        source_health=list(source_health),
        metrics=metrics,
    )
