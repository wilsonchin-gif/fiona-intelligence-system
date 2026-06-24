from __future__ import annotations

import html
import json
import re
import urllib.parse
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any

USER_AGENT = "Mozilla/5.0 FinancialDailyReporter/1.0"
TIMEOUT = 20
QUOTE_TIMEOUT = 8

STABLE_SYMBOLS = {
    "usdt",
    "usdc",
    "dai",
    "usde",
    "usds",
    "fdusd",
    "tusd",
    "usdd",
    "usdp",
    "pyusd",
    "frax",
    "lusd",
    "usdf",
    "crvusd",
    "gusd",
}
STABLE_NAMES = ["usd", "stable", "tether", "dai", "frax", "paypal usd"]


def build_universe_snapshot() -> dict[str, Any]:
    snapshot: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sp500": safe_call(sp500_snapshot, "S&P 500"),
        "csi500": safe_call(csi500_snapshot, "CSI 500"),
        "crypto_top100": safe_call(crypto_top100_snapshot, "Crypto Top 100"),
        "new_onchain": safe_call(new_onchain_snapshot, "New on-chain watch"),
        "rwa": safe_call(rwa_snapshot, "RWA"),
        "dex": safe_call(dex_snapshot, "DEX"),
    }
    return snapshot


def safe_call(fn, name: str) -> dict[str, Any]:  # noqa: ANN001
    try:
        return fn()
    except Exception as exc:  # noqa: BLE001 - report source failure, keep preview alive.
        return {"title": name, "error": str(exc), "items": [], "summary": f"{name} 数据暂时不可用。"}


def sp500_snapshot() -> dict[str, Any]:
    rows = sp500_constituents()
    sectors = Counter(row.get("sector", "Unknown") for row in rows)
    quotes = quote_sp500(rows)
    return {
        "title": "S&P 500 成分股雷达",
        "source": "Wikipedia S&P 500 constituents",
        "count": len(rows),
        "summary": f"已读取 {len(rows)} 家 S&P 500 成分公司。行业集中度最高的是 {format_counter(sectors, 3)}。",
        "items": rows[:12],
        "sectors": sectors.most_common(8),
        "gainers": quotes.get("gainers", []),
        "losers": quotes.get("losers", []),
        "quote_count": quotes.get("quote_count", 0),
    }


def csi500_snapshot() -> dict[str, Any]:
    rows = csi500_constituents()
    exchanges = Counter(row.get("exchange", "Unknown") for row in rows)
    quotes = quote_csi500(rows)
    return {
        "title": "中证 500 成分股雷达",
        "source": "Wikipedia CSI 500 constituents fallback",
        "count": len(rows),
        "summary": f"已读取 {len(rows)} 家中证 500 成分公司样本。交易所分布：{format_counter(exchanges, 3)}。",
        "items": rows[:12],
        "exchanges": exchanges.most_common(8),
        "gainers": quotes.get("gainers", []),
        "losers": quotes.get("losers", []),
        "quote_count": quotes.get("quote_count", 0),
        "note": "当前使用公开可访问成分股源；实时全量 A 股行情建议后续接入 Tushare、聚宽、东方财富或券商授权接口。",
    }


def crypto_top100_snapshot() -> dict[str, Any]:
    coins = http_json(
        "https://api.coingecko.com/api/v3/coins/markets?"
        + urllib.parse.urlencode(
            {
                "vs_currency": "usd",
                "order": "market_cap_desc",
                "per_page": 150,
                "page": 1,
                "sparkline": "false",
                "price_change_percentage": "24h",
            }
        )
    )
    filtered = [coin for coin in coins if not is_stablecoin(coin)][:100]
    total_mcap = sum(float(coin.get("market_cap") or 0) for coin in filtered)
    gainers = sorted(filtered, key=lambda coin: float(coin.get("price_change_percentage_24h") or -999), reverse=True)[:5]
    losers = sorted(filtered, key=lambda coin: float(coin.get("price_change_percentage_24h") or 999))[:5]
    return {
        "title": "非稳定币市值 Top 100",
        "source": "CoinGecko markets API",
        "count": len(filtered),
        "summary": f"已剔除主要稳定币，覆盖 {len(filtered)} 个市值头部代币，总市值约 {money(total_mcap)}。",
        "items": [
            {
                "rank": coin.get("market_cap_rank"),
                "symbol": str(coin.get("symbol", "")).upper(),
                "name": coin.get("name"),
                "price": coin.get("current_price"),
                "change_24h": coin.get("price_change_percentage_24h"),
                "market_cap": coin.get("market_cap"),
            }
            for coin in filtered[:12]
        ],
        "gainers": compact_coin_list(gainers),
        "losers": compact_coin_list(losers),
    }


def new_onchain_snapshot() -> dict[str, Any]:
    protocols = http_json("https://api.llama.fi/protocols")
    recent = sorted(
        [item for item in protocols if item.get("listedAt")],
        key=lambda item: int(item.get("listedAt") or 0),
        reverse=True,
    )
    candidates = [
        item
        for item in recent
        if not item.get("gecko_id") and not item.get("cmcId") and not item.get("mcap")
    ][:10]
    if len(candidates) < 10:
        existing = {item.get("name") for item in candidates}
        candidates.extend([item for item in recent if item.get("name") not in existing][: 10 - len(candidates)])
    return {
        "title": "近期新上链 / 未进入二级市场观察池",
        "source": "DefiLlama recently listed protocols",
        "count": len(candidates),
        "summary": f"筛出 {len(candidates)} 个近期上链协议/资产线索，优先关注尚无 CoinGecko/CMC 标识或市值字段的项目。",
        "items": [
            {
                "name": item.get("name"),
                "category": item.get("category"),
                "chain": item.get("chain"),
                "tvl": item.get("tvl"),
                "listed_at": format_ts(item.get("listedAt")),
                "secondary_hint": "未见公开价格标识" if not item.get("gecko_id") and not item.get("cmcId") else "已有价格标识",
            }
            for item in candidates
        ],
    }


def rwa_snapshot() -> dict[str, Any]:
    protocols = http_json("https://api.llama.fi/protocols")
    rwa = [item for item in protocols if str(item.get("category", "")).lower() == "rwa"]
    rwa.sort(key=lambda item: float(item.get("tvl") or 0), reverse=True)
    total_tvl = sum(float(item.get("tvl") or 0) for item in rwa)
    top = rwa[:10]
    return {
        "title": "RWA 赛道数据",
        "source": "DefiLlama protocols category=RWA",
        "count": len(rwa),
        "summary": f"RWA 协议 {len(rwa)} 个，总 TVL 约 {money(total_tvl)}；头部项目包括 {', '.join(str(item.get('name')) for item in top[:3])}。",
        "items": [
            {
                "name": item.get("name"),
                "chain": item.get("chain"),
                "tvl": item.get("tvl"),
                "change_1d": item.get("change_1d"),
                "change_7d": item.get("change_7d"),
            }
            for item in top
        ],
    }


def dex_snapshot() -> dict[str, Any]:
    data = http_json("https://api.llama.fi/overview/dexs?excludeTotalDataChart=true&excludeTotalDataChartBreakdown=true")
    protocols = sorted(data.get("protocols", []), key=lambda item: float(item.get("total24h") or 0), reverse=True)
    top = protocols[:10]
    return {
        "title": "主流 DEX 交易所数据",
        "source": "DefiLlama DEX overview",
        "count": len(protocols),
        "summary": f"DEX 24h 总成交约 {money(float(data.get('total24h') or 0))}，7d 成交约 {money(float(data.get('total7d') or 0))}。",
        "change_1d": data.get("change_1d"),
        "change_7d": data.get("change_7d"),
        "items": [
            {
                "name": item.get("displayName") or item.get("name"),
                "chains": ", ".join((item.get("chains") or [])[:3]),
                "volume_24h": item.get("total24h"),
                "volume_7d": item.get("total7d"),
                "change_1d": item.get("change_1d"),
            }
            for item in top
        ],
    }


def sp500_constituents() -> list[dict[str, str]]:
    text = http_text("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies")
    table = extract_table(text, "constituents")
    rows = []
    for cells in table_rows(table):
        if len(cells) < 4 or cells[0] == "Symbol":
            continue
        rows.append({"symbol": cells[0].replace(".", "-"), "name": cells[1], "sector": cells[2], "industry": cells[3]})
    return rows


def csi500_constituents() -> list[dict[str, str]]:
    text = http_text("https://zh.wikipedia.org/wiki/%E4%B8%AD%E8%AF%81500%E6%8C%87%E6%95%B0")
    rows = []
    for cells in table_rows(text):
        if len(cells) < 4 or not re.fullmatch(r"\d{6}", cells[0]):
            continue
        rows.append({"symbol": cells[0], "name": cells[1], "exchange": cells[2], "weight": cells[3]})
    return rows


def quote_sp500(rows: list[dict[str, str]]) -> dict[str, Any]:
    quotes: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=18) as executor:
        futures = {executor.submit(yahoo_chart_quote, row): row for row in rows}
        for future in as_completed(futures):
            quote = future.result()
            if quote:
                quotes.append(quote)
    ranked = sorted(quotes, key=lambda item: float(item.get("change_pct") or 0), reverse=True)
    return {
        "quote_count": len(quotes),
        "gainers": [with_reason(item, "上涨") for item in ranked[:8]],
        "losers": [with_reason(item, "下跌") for item in ranked[-8:]][::-1],
    }


def yahoo_chart_quote(row: dict[str, str]) -> dict[str, Any] | None:
    symbol = row.get("symbol", "")
    if not symbol:
        return None
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(symbol)}?range=5d&interval=1d"
    try:
        data = http_json(url, timeout=QUOTE_TIMEOUT)
        result = (data.get("chart", {}).get("result") or [None])[0]
        if not result:
            return None
        meta = result.get("meta", {})
        price = first_number(meta.get("regularMarketPrice"), meta.get("postMarketPrice"), meta.get("previousClose"))
        previous = first_number(meta.get("chartPreviousClose"), meta.get("previousClose"))
        if price is None or previous in (None, 0):
            return None
        change = price - previous
        change_pct = change / previous * 100
        return {
            "symbol": symbol,
            "name": row.get("name", ""),
            "sector": row.get("sector", ""),
            "industry": row.get("industry", ""),
            "price": price,
            "change": change,
            "change_pct": change_pct,
        }
    except Exception:
        return None


def quote_csi500(rows: list[dict[str, str]]) -> dict[str, Any]:
    secids = [eastmoney_secid(row) for row in rows]
    secids = [secid for secid in secids if secid]
    quotes: list[dict[str, Any]] = []
    fields = "f12,f14,f2,f3,f4,f5,f6,f17,f18"
    for index in range(0, len(secids), 80):
        batch = ",".join(secids[index : index + 80])
        url = "https://push2.eastmoney.com/api/qt/ulist.np/get?" + urllib.parse.urlencode(
            {"fltt": "2", "invt": "2", "fields": fields, "secids": batch}
        )
        try:
            data = http_json(url, timeout=QUOTE_TIMEOUT)
            for item in data.get("data", {}).get("diff", []):
                price = first_number(item.get("f2"))
                change_pct = first_number(item.get("f3"))
                if price is None or change_pct is None:
                    continue
                quotes.append(
                    {
                        "symbol": item.get("f12"),
                        "name": item.get("f14"),
                        "price": price,
                        "change": item.get("f4"),
                        "change_pct": change_pct,
                        "volume": item.get("f5"),
                        "turnover": item.get("f6"),
                    }
                )
        except Exception:
            continue
    ranked = sorted(quotes, key=lambda item: float(item.get("change_pct") or 0), reverse=True)
    return {
        "quote_count": len(quotes),
        "gainers": [with_reason(item, "上涨") for item in ranked[:8]],
        "losers": [with_reason(item, "下跌") for item in ranked[-8:]][::-1],
    }


def eastmoney_secid(row: dict[str, str]) -> str:
    symbol = row.get("symbol", "")
    exchange = row.get("exchange", "")
    if not re.fullmatch(r"\d{6}", symbol):
        return ""
    if "上海" in exchange or symbol.startswith("6"):
        return f"1.{symbol}"
    return f"0.{symbol}"


def with_reason(item: dict[str, Any], direction: str) -> dict[str, Any]:
    sector = item.get("sector") or item.get("industry") or "所属板块"
    change_pct = float(item.get("change_pct") or 0)
    if abs(change_pct) >= 7:
        reason = f"{direction}幅度较大，可能存在个股事件、资金集中交易或板块情绪共振，需要结合公告与新闻二次确认。"
    elif sector and sector != "所属板块":
        reason = f"{sector} 相关风险偏好变化带动，属于成分股内部相对强弱信号。"
    else:
        reason = "价格相对成分股池明显异动，需结合成交量、公告和行业消息确认原因。"
    output = dict(item)
    output["reason"] = reason
    return output


def http_json(url: str, timeout: int = TIMEOUT) -> Any:
    return json.loads(http_text(url, timeout=timeout))


def http_text(url: str, timeout: int = TIMEOUT) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", "ignore")


def extract_table(text: str, table_id: str) -> str:
    marker = f'id="{table_id}"'
    start = text.find(marker)
    if start == -1:
        return text
    table_start = text.rfind("<table", 0, start)
    table_end = text.find("</table>", start)
    if table_start == -1 or table_end == -1:
        return text
    return text[table_start : table_end + 8]


def table_rows(table_html: str) -> list[list[str]]:
    rows: list[list[str]] = []
    for row_html in re.findall(r"<tr[^>]*>(.*?)</tr>", table_html, flags=re.S | re.I):
        cells = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row_html, flags=re.S | re.I)
        cleaned = [clean_cell(cell) for cell in cells]
        if cleaned:
            rows.append(cleaned)
    return rows


def clean_cell(cell_html: str) -> str:
    text = re.sub(r"<style.*?</style>|<script.*?</script>", "", cell_html, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"\[[^\]]+\]", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def is_stablecoin(coin: dict[str, Any]) -> bool:
    symbol = str(coin.get("symbol", "")).lower()
    name = str(coin.get("name", "")).lower()
    coin_id = str(coin.get("id", "")).lower()
    if symbol in STABLE_SYMBOLS or coin_id in STABLE_SYMBOLS:
        return True
    return any(stable in name for stable in STABLE_NAMES) and symbol.startswith(("usd", "eur"))


def compact_coin_list(coins: list[dict[str, Any]]) -> list[str]:
    return [
        f"{str(coin.get('symbol', '')).upper()} {pct(coin.get('price_change_percentage_24h'))}"
        for coin in coins
    ]


def format_counter(counter: Counter, limit: int) -> str:
    return "、".join(f"{name} {count}" for name, count in counter.most_common(limit))


def money(value: float | int | None) -> str:
    if value is None:
        return "-"
    value = float(value)
    if value >= 1_000_000_000_000:
        return f"${value / 1_000_000_000_000:.2f}T"
    if value >= 1_000_000_000:
        return f"${value / 1_000_000_000:.2f}B"
    if value >= 1_000_000:
        return f"${value / 1_000_000:.2f}M"
    return f"${value:,.0f}"


def price(value: Any, currency: str = "") -> str:
    if value is None:
        return "-"
    number = float(value)
    if abs(number) >= 1000:
        rendered = f"{number:,.2f}"
    elif abs(number) >= 1:
        rendered = f"{number:.2f}"
    else:
        rendered = f"{number:.4f}"
    return f"{currency}{rendered}"


def pct(value: Any) -> str:
    if value is None:
        return "-"
    return f"{float(value):+.2f}%"


def first_number(*values: Any) -> float | None:
    for value in values:
        try:
            if value in ("-", "", None):
                continue
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def format_ts(value: Any) -> str:
    if not value:
        return "-"
    return datetime.fromtimestamp(int(value), timezone.utc).strftime("%Y-%m-%d")
