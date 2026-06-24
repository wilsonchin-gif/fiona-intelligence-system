from __future__ import annotations

import math
import re
from collections import Counter
from datetime import datetime, timezone

from app.config import MARKET_KEYWORDS
from app.models import NewsItem, Source

CRITICAL_KEYWORDS = {
    "breaking": 24,
    "unexpected": 12,
    "surge": 10,
    "plunge": 10,
    "crash": 16,
    "ban": 18,
    "approve": 16,
    "lawsuit": 14,
    "probe": 14,
    "爆": 12,
    "突发": 24,
    "意外": 12,
    "大跌": 16,
    "大涨": 12,
    "批准": 16,
    "调查": 14,
    "禁令": 18,
}

POSITIVE_HINTS = ["beat", "approve", "stimulus", "rate cut", "inflow", "record high", "上涨", "利好", "刺激", "降息", "流入", "新高"]
NEGATIVE_HINTS = ["miss", "lawsuit", "hack", "outflow", "liquidation", "tariff", "sanction", "下跌", "利空", "黑客", "流出", "清算", "制裁", "关税"]


def rank_items(items: list[NewsItem], sources: list[Source], now: datetime | None = None) -> list[NewsItem]:
    now = now or datetime.now(timezone.utc)
    source_weights = {source.name: source.weight for source in sources}
    normalized_counts = Counter(normalize_title(item.title) for item in items)

    deduped: dict[str, NewsItem] = {}
    for item in items:
        key = normalize_title(item.title)
        if not key:
            continue
        score, reasons, tags = score_item(item, source_weights.get(item.source, 1.0), normalized_counts[key], now)
        item.score = score
        item.reasons = reasons[:4]
        item.tags = tags[:5]
        item.priority = priority_label(score)
        item.stance = stance_for(item)

        previous = deduped.get(key)
        if previous is None or item.score > previous.score:
            deduped[key] = item

    return sorted(deduped.values(), key=lambda entry: entry.score, reverse=True)


def score_item(item: NewsItem, source_weight: float, duplicate_count: int, now: datetime) -> tuple[float, list[str], list[str]]:
    text = f"{item.title} {item.summary}".lower()
    score = 18.0 * source_weight
    reasons: list[str] = [f"来源权重 {source_weight:g}"]
    tags: list[str] = []

    age_hours = max((now - item.published_at.astimezone(timezone.utc)).total_seconds() / 3600, 0)
    recency_bonus = max(0.0, 26.0 - age_hours * 3.6)
    score += recency_bonus
    if recency_bonus >= 18:
        reasons.append("近 2 小时新消息")

    if duplicate_count > 1:
        consensus_bonus = min(18, 7 * math.log2(duplicate_count + 1))
        score += consensus_bonus
        reasons.append(f"{duplicate_count} 条相似消息共振")

    market_groups = MARKET_KEYWORDS.get(item.market, {})
    for tag, keywords in market_groups.items():
        hits = [keyword for keyword in keywords if keyword.lower() in text]
        if hits:
            score += 8 + min(18, 3 * len(hits))
            tags.append(tag)
            reasons.append(f"命中 {tag}: {', '.join(hits[:3])}")

    for keyword, weight in CRITICAL_KEYWORDS.items():
        if keyword.lower() in text:
            score += weight
            tags.append("high-impact")
            reasons.append(f"高冲击词: {keyword}")

    if re.search(r"\b([5-9]\d|100)\s?%|\b\d+(\.\d+)?\s?(billion|trillion)\b|[百千]亿", text):
        score += 10
        tags.append("data-heavy")
        reasons.append("包含大幅百分比或大额金额")

    return score, unique(reasons), unique(tags)


def stance_for(item: NewsItem) -> str:
    text = f"{item.title} {item.summary}".lower()
    positive = sum(1 for word in POSITIVE_HINTS if word in text)
    negative = sum(1 for word in NEGATIVE_HINTS if word in text)
    if positive > negative:
        return "偏利好"
    if negative > positive:
        return "偏利空"
    return "中性/待确认"


def priority_label(score: float) -> str:
    if score >= 82:
        return "一级关注"
    if score >= 62:
        return "二级关注"
    if score >= 44:
        return "三级关注"
    return "观察"


def normalize_title(title: str) -> str:
    value = re.sub(r"https?://\S+", "", title.lower())
    value = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", " ", value)
    tokens = [token for token in value.split() if len(token) > 1]
    return " ".join(tokens[:18])


def unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        output.append(value)
    return output

