from __future__ import annotations

from datetime import datetime, timezone

import unittest

from app.models import NewsItem, Source
from app.scoring import rank_items


class ScoringTest(unittest.TestCase):
    def test_macro_policy_news_ranks_above_generic_news(self) -> None:
        now = datetime(2026, 6, 22, 8, 0, tzinfo=timezone.utc)
        sources = [Source(name="Test", market="us_equities", url="https://example.com", weight=1.0)]
        items = [
            NewsItem(
                title="Small-cap stocks drift higher in quiet session",
                url="https://example.com/a",
                source="Test",
                market="us_equities",
                published_at=now,
            ),
            NewsItem(
                title="Breaking: Fed signals unexpected rate cut path as Treasury yields plunge",
                url="https://example.com/b",
                source="Test",
                market="us_equities",
                published_at=now,
            ),
        ]

        ranked = rank_items(items, sources, now=now)

        self.assertEqual(ranked[0].url, "https://example.com/b")
        self.assertIn(ranked[0].priority, {"一级关注", "二级关注"})


if __name__ == "__main__":
    unittest.main()
