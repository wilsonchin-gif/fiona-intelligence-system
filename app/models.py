from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class Source:
    name: str
    market: str
    url: str
    kind: str = "rss"
    enabled: bool = True
    weight: float = 1.0
    language: str = "mixed"


@dataclass
class NewsItem:
    title: str
    url: str
    source: str
    market: str
    published_at: datetime
    summary: str = ""
    tags: list[str] = field(default_factory=list)
    score: float = 0.0
    priority: str = "观察"
    reasons: list[str] = field(default_factory=list)
    stance: str = "中性"

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "url": self.url,
            "source": self.source,
            "market": self.market,
            "published_at": self.published_at.astimezone(timezone.utc).isoformat(),
            "summary": self.summary,
            "tags": self.tags,
            "score": round(self.score, 2),
            "priority": self.priority,
            "reasons": self.reasons,
            "stance": self.stance,
        }


@dataclass
class MarketReport:
    market: str
    title: str
    generated_at: datetime
    items: list[NewsItem]
    briefing: str
    advice: str
    risk_flags: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "market": self.market,
            "title": self.title,
            "generated_at": self.generated_at.astimezone(timezone.utc).isoformat(),
            "briefing": self.briefing,
            "advice": self.advice,
            "risk_flags": self.risk_flags,
            "items": [item.to_dict() for item in self.items],
        }

