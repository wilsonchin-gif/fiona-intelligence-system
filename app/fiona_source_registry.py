from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from enum import Enum, IntEnum
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable, Iterable


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SOURCE_REGISTRY = ROOT / "config" / "sources.json"
SOURCE_REGISTRY_SCHEMA_VERSION = "3.1"


class EventRegion(str, Enum):
    US_EU = "US_EU"
    GREATER_CHINA = "GREATER_CHINA"
    REST_OF_WORLD = "REST_OF_WORLD"
    GLOBAL = "GLOBAL"
    UNKNOWN = "UNKNOWN"


class SourceTier(IntEnum):
    UNKNOWN = 0
    TIER_1 = 1
    TIER_2 = 2
    TIER_3 = 3


class CoverageProfile(str, Enum):
    LEGACY = "legacy"
    GLOBAL_631 = "global_631"


@dataclass(frozen=True)
class SourceSpec:
    source_id: str
    name: str
    publisher: str
    publisher_region: EventRegion
    default_event_region: EventRegion
    language: str
    tier: SourceTier
    independence_group: str
    source_type: str
    markets: tuple[str, ...]
    content_categories: tuple[str, ...]
    retrieval_method: str
    endpoint: str
    enabled: bool = True
    legacy_enabled: bool = False
    shadow_enabled: bool = False
    market_bucket: str = ""
    weight: float = 1.0
    authority_score: int | None = None
    authority_classification: str = "Unknown"
    expected_update_frequency: str = "unknown"
    supports_original_title: bool = True
    supports_original_text: bool = False
    access_notes: str = ""
    status: str = "active"
    json_records_path: tuple[str, ...] = ()
    json_title_field: str = "title"
    json_url_field: str = "url"
    json_published_field: str = "published_at"
    json_summary_field: str = "summary"
    metadata_notes: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.source_id.strip():
            raise ValueError("SourceSpec.source_id is required.")
        if not self.name.strip():
            raise ValueError(f"Source {self.source_id!r} must have a name.")
        if self.retrieval_method not in {"rss", "json", "none"}:
            raise ValueError(
                f"Source {self.source_id!r} has unsupported retrieval_method {self.retrieval_method!r}."
            )
        if self.enabled and self.retrieval_method != "none" and not self.endpoint.startswith(("https://", "http://")):
            raise ValueError(f"Source {self.source_id!r} must use an HTTP(S) endpoint.")
        if self.authority_score is not None and not 0 <= self.authority_score <= 100:
            raise ValueError(f"Source {self.source_id!r} authority_score must be between 0 and 100.")
        if self.legacy_enabled and self.market_bucket not in {"us", "china", "crypto"}:
            raise ValueError(f"Legacy source {self.source_id!r} requires a valid market_bucket.")

    @property
    def active_for_legacy(self) -> bool:
        return self.enabled and self.status == "active" and self.legacy_enabled

    @property
    def active_for_shadow(self) -> bool:
        return self.enabled and self.status == "active" and self.shadow_enabled

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "name": self.name,
            "publisher": self.publisher,
            "publisher_region": self.publisher_region.value,
            "default_event_region": self.default_event_region.value,
            "language": self.language,
            "tier": int(self.tier),
            "independence_group": self.independence_group,
            "source_type": self.source_type,
            "markets": list(self.markets),
            "content_categories": list(self.content_categories),
            "retrieval_method": self.retrieval_method,
            "enabled": self.enabled,
            "legacy_enabled": self.legacy_enabled,
            "shadow_enabled": self.shadow_enabled,
            "status": self.status,
            "authority_score": self.authority_score,
            "authority_classification": self.authority_classification,
            "expected_update_frequency": self.expected_update_frequency,
            "supports_original_title": self.supports_original_title,
            "supports_original_text": self.supports_original_text,
            "access_notes": self.access_notes,
        }


@dataclass(frozen=True)
class SourceRegistry:
    schema_version: str
    sources: tuple[SourceSpec, ...]
    approved_gaps: tuple[dict[str, Any], ...] = ()

    def __post_init__(self) -> None:
        identifiers = [source.source_id for source in self.sources]
        duplicates = sorted({source_id for source_id in identifiers if identifiers.count(source_id) > 1})
        if duplicates:
            raise ValueError(f"Duplicate source_id values: {', '.join(duplicates)}")

    def by_id(self, source_id: str) -> SourceSpec:
        for source in self.sources:
            if source.source_id == source_id:
                return source
        raise KeyError(source_id)

    def legacy_sources(self) -> tuple[SourceSpec, ...]:
        return tuple(source for source in self.sources if source.active_for_legacy)

    def shadow_sources(self) -> tuple[SourceSpec, ...]:
        return tuple(source for source in self.sources if source.active_for_shadow)

    def shadow_only_sources(self) -> tuple[SourceSpec, ...]:
        return tuple(source for source in self.shadow_sources() if not source.active_for_legacy)


def _region(value: Any) -> EventRegion:
    try:
        return EventRegion(str(value or EventRegion.UNKNOWN.value).upper())
    except ValueError:
        return EventRegion.UNKNOWN


def _tier(value: Any) -> SourceTier:
    try:
        return SourceTier(int(value))
    except (TypeError, ValueError):
        return SourceTier.UNKNOWN


def source_spec_from_dict(raw: dict[str, Any]) -> SourceSpec:
    source_id = str(raw.get("source_id") or "").strip()
    return SourceSpec(
        source_id=source_id,
        name=str(raw.get("name") or source_id or "Unknown").strip(),
        publisher=str(raw.get("publisher") or raw.get("name") or source_id or "Unknown").strip(),
        publisher_region=_region(raw.get("publisher_region")),
        default_event_region=_region(raw.get("default_event_region")),
        language=str(raw.get("language") or "und").strip(),
        tier=_tier(raw.get("tier")),
        independence_group=str(raw.get("independence_group") or "unknown").strip(),
        source_type=str(raw.get("source_type") or "Unknown").strip(),
        markets=tuple(str(item) for item in raw.get("markets", []) if str(item).strip()),
        content_categories=tuple(
            str(item) for item in raw.get("content_categories", []) if str(item).strip()
        ),
        retrieval_method=str(raw.get("retrieval_method") or raw.get("kind") or "rss").strip().lower(),
        endpoint=str(raw.get("endpoint") or raw.get("url") or "").strip(),
        enabled=bool(raw.get("enabled", True)),
        legacy_enabled=bool(raw.get("legacy_enabled", False)),
        shadow_enabled=bool(raw.get("shadow_enabled", False)),
        market_bucket=str(raw.get("market_bucket") or "").strip(),
        weight=float(raw.get("weight", 1.0)),
        authority_score=(int(raw["authority_score"]) if raw.get("authority_score") is not None else None),
        authority_classification=str(raw.get("authority_classification") or "Unknown").strip(),
        expected_update_frequency=str(raw.get("expected_update_frequency") or "unknown").strip(),
        supports_original_title=bool(raw.get("supports_original_title", True)),
        supports_original_text=bool(raw.get("supports_original_text", False)),
        access_notes=str(raw.get("access_notes") or "").strip(),
        status=str(raw.get("status") or "active").strip().lower(),
        json_records_path=tuple(str(item) for item in raw.get("json_records_path", []) if str(item).strip()),
        json_title_field=str(raw.get("json_title_field") or "title"),
        json_url_field=str(raw.get("json_url_field") or raw.get("json_link_field") or "url"),
        json_published_field=str(raw.get("json_published_field") or "published_at"),
        json_summary_field=str(raw.get("json_summary_field") or "summary"),
        metadata_notes=tuple(str(item) for item in raw.get("metadata_notes", []) if str(item).strip()),
    )


@lru_cache(maxsize=4)
def load_source_registry(path: str | Path = DEFAULT_SOURCE_REGISTRY) -> SourceRegistry:
    target = Path(path)
    payload = json.loads(target.read_text(encoding="utf-8"))
    sources = tuple(source_spec_from_dict(raw) for raw in payload.get("sources", []) if isinstance(raw, dict))
    gaps = tuple(raw for raw in payload.get("approved_gaps", []) if isinstance(raw, dict))
    return SourceRegistry(
        schema_version=str(payload.get("schema_version") or "unknown"),
        sources=sources,
        approved_gaps=gaps,
    )


def clear_source_registry_cache() -> None:
    load_source_registry.cache_clear()


def coverage_profile_from_env(
    env: dict[str, str] | None = None,
    warning_logger: Callable[[dict[str, Any]], None] | None = None,
) -> CoverageProfile:
    source = os.environ if env is None else env
    raw = str(source.get("FIONA_COVERAGE_PROFILE", CoverageProfile.LEGACY.value)).strip().lower()
    try:
        return CoverageProfile(raw)
    except ValueError:
        if warning_logger is not None:
            warning_logger(
                {
                    "event": "fionaCoverageProfileWarning",
                    "invalid_profile": raw,
                    "fallback_profile": CoverageProfile.LEGACY.value,
                }
            )
        return CoverageProfile.LEGACY


def validate_registry(registry: SourceRegistry) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    seen_endpoints: dict[str, str] = {}
    for source in registry.sources:
        if source.tier == SourceTier.UNKNOWN:
            warnings.append(f"{source.source_id}: tier is UNKNOWN")
        if source.publisher_region == EventRegion.UNKNOWN:
            warnings.append(f"{source.source_id}: publisher_region is UNKNOWN")
        if source.default_event_region == EventRegion.UNKNOWN:
            warnings.append(f"{source.source_id}: default_event_region is UNKNOWN")
        if source.language == "und":
            warnings.append(f"{source.source_id}: language is undetermined")
        if not source.independence_group:
            errors.append(f"{source.source_id}: independence_group is missing")
        elif source.independence_group == "unknown":
            warnings.append(f"{source.source_id}: independence_group is unknown")
        if source.enabled and source.retrieval_method != "none" and not source.endpoint:
            errors.append(f"{source.source_id}: endpoint is missing")
        if source.endpoint:
            other = seen_endpoints.get(source.endpoint)
            if other and other != source.source_id:
                warnings.append(f"{source.source_id}: endpoint duplicates {other}")
            seen_endpoints[source.endpoint] = source.source_id
    return {
        "ok": not errors,
        "schema_version": registry.schema_version,
        "source_count": len(registry.sources),
        "legacy_source_count": len(registry.legacy_sources()),
        "shadow_source_count": len(registry.shadow_sources()),
        "errors": errors,
        "warnings": warnings,
    }


def source_ids(sources: Iterable[SourceSpec]) -> set[str]:
    return {source.source_id for source in sources}
