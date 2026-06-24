from __future__ import annotations

import json
from pathlib import Path

from app.models import Source


MARKET_TITLES = {
    "us_equities": "美国股市即时情报",
    "china_equities": "中国股市即时情报",
    "crypto": "加密货币即时情报",
}


MARKET_KEYWORDS = {
    "us_equities": {
        "macro": ["fed", "fomc", "rate cut", "rate hike", "cpi", "pce", "jobs", "payroll", "treasury", "yield", "inflation", "gdp", "美元", "美联储", "通胀", "非农", "降息", "加息"],
        "policy": ["sec", "doj", "ftc", "tariff", "sanction", "congress", "white house", "监管", "关税", "制裁"],
        "leaders": ["nvidia", "apple", "microsoft", "amazon", "meta", "tesla", "google", "alphabet", "amd", "英伟达", "苹果", "特斯拉"],
        "market": ["nasdaq", "s&p", "dow", "earnings", "guidance", "buyback", "ipo", "merger", "纳指", "标普", "财报", "回购"],
    },
    "china_equities": {
        "policy": ["pboc", "pboc", "csrc", "ndrc", "politburo", "stimulus", "liquidity", "rrr", "lpr", "央行", "证监会", "发改委", "政治局", "刺激", "降准", "降息", "流动性"],
        "macro": ["pmi", "cpi", "ppi", "exports", "imports", "credit", "property", "real estate", "人民币", "地产", "出口", "进口", "社融", "信贷"],
        "markets": ["shanghai", "shenzhen", "hong kong", "h shares", "a shares", "etf", "北向", "沪指", "深成指", "创业板", "港股", "a股"],
        "sectors": ["semiconductor", "ev", "solar", "battery", "consumer", "brokerage", "芯片", "半导体", "新能源", "光伏", "券商", "消费"],
    },
    "crypto": {
        "macro": ["fed", "rate", "dollar", "treasury", "liquidity", "美联储", "美元", "流动性", "降息", "加息"],
        "policy": ["sec", "cftc", "etf", "stablecoin", "bill", "lawsuit", "监管", "法案", "稳定币", "现货etf"],
        "market": ["bitcoin", "btc", "ethereum", "eth", "solana", "sol", "altcoin", "defi", "比特币", "以太坊", "山寨币"],
        "risk": ["hack", "exploit", "outflow", "liquidation", "bankruptcy", "whale", "交易所", "黑客", "清算", "爆仓", "巨鲸"],
    },
}


def load_sources(path: Path) -> list[Source]:
    data = json.loads(path.read_text(encoding="utf-8"))
    sources: list[Source] = []
    for raw in data.get("sources", []):
        sources.append(
            Source(
                name=raw["name"],
                market=raw["market"],
                url=raw["url"],
                kind=raw.get("kind", "rss"),
                enabled=raw.get("enabled", True),
                weight=float(raw.get("weight", 1.0)),
                language=raw.get("language", "mixed"),
            )
        )
    return sources

