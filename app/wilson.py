from __future__ import annotations

import argparse
import email.utils
import html
import json
import math
import os
import re
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.telegram_service import send_document as telegram_service_send_document
from app.telegram_service import send_message as telegram_service_send_message

try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover - Python 3.8 fallback only.
    ZoneInfo = None  # type: ignore[assignment]

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = ROOT / "reports" / "wilson"
DEFAULT_TIMEZONE = "Asia/Manila"
DISCLAIMER = "本内容仅供参考，不构成任何投资建议。投资有风险，入市需谨慎。"
TELEGRAM_LOG_NAME = "telegram_push.log"
USER_AGENT = "Mozilla/5.0 WilsonMarketNews/0.1 (+local market intelligence bot)"
TIMEOUT = 16
QUOTE_TIMEOUT = 8
RUN_CACHE: dict[str, Any] = {}
CHROME_PATH = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")

US_INDICES = [
    ("^GSPC", "S&P 500"),
    ("^IXIC", "Nasdaq"),
    ("^DJI", "Dow Jones"),
    ("^VIX", "VIX"),
    ("DX-Y.NYB", "DXY"),
    ("^RUT", "Russell 2000"),
]
US_SECTOR_ETFS = [
    ("XLK", "科技"),
    ("XLC", "通信"),
    ("XLY", "可选消费"),
    ("XLF", "金融"),
    ("XLV", "医疗"),
    ("XLI", "工业"),
    ("XLE", "能源"),
    ("XLP", "必需消费"),
    ("XLU", "公用事业"),
    ("XLB", "材料"),
    ("XLRE", "地产"),
]
US_ETFS = [
    ("SPY", "S&P 500 ETF"),
    ("QQQ", "Nasdaq 100 ETF"),
    ("IWM", "Russell 2000 ETF"),
    ("DIA", "Dow ETF"),
    ("TLT", "20Y Treasury"),
    ("HYG", "High Yield"),
    ("GLD", "Gold"),
]
US_AI = [
    ("NVDA", "NVIDIA"),
    ("MSFT", "Microsoft"),
    ("GOOGL", "Alphabet"),
    ("META", "Meta"),
    ("AVGO", "Broadcom"),
    ("AMD", "AMD"),
    ("TSM", "TSMC"),
    ("PLTR", "Palantir"),
    ("ORCL", "Oracle"),
    ("MU", "Micron"),
]
US_STOCKS = [
    ("NVDA", "NVIDIA"),
    ("MSFT", "Microsoft"),
    ("AAPL", "Apple"),
    ("AMZN", "Amazon"),
    ("GOOGL", "Alphabet"),
    ("META", "Meta"),
    ("TSLA", "Tesla"),
    ("AVGO", "Broadcom"),
    ("AMD", "AMD"),
    ("NFLX", "Netflix"),
    ("PLTR", "Palantir"),
    ("ORCL", "Oracle"),
    ("CRM", "Salesforce"),
    ("ADBE", "Adobe"),
    ("INTC", "Intel"),
    ("MU", "Micron"),
    ("QCOM", "Qualcomm"),
    ("JPM", "JPMorgan"),
    ("BAC", "Bank of America"),
    ("GS", "Goldman Sachs"),
    ("XOM", "Exxon Mobil"),
    ("CVX", "Chevron"),
    ("UNH", "UnitedHealth"),
    ("LLY", "Eli Lilly"),
    ("JNJ", "Johnson & Johnson"),
    ("WMT", "Walmart"),
    ("COST", "Costco"),
    ("HD", "Home Depot"),
    ("MCD", "McDonald's"),
    ("NKE", "Nike"),
    ("DIS", "Disney"),
    ("PYPL", "PayPal"),
    ("UBER", "Uber"),
    ("SHOP", "Shopify"),
    ("SNOW", "Snowflake"),
    ("SMCI", "Super Micro"),
    ("GE", "GE Aerospace"),
    ("CAT", "Caterpillar"),
    ("BA", "Boeing"),
    ("F", "Ford"),
    ("GM", "GM"),
    ("MRNA", "Moderna"),
    ("PFE", "Pfizer"),
    ("T", "AT&T"),
]
DAILY_MARKET_QUOTES = [
    ("^HSI", "HSI"),
    ("GC=F", "GOLD"),
    ("SI=F", "SILVER"),
    ("CL=F", "USOIL"),
    ("BZ=F", "UKOIL"),
]
DAILY_CRYPTO_IDS = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "SOL": "solana",
    "BNB": "binancecoin",
    "HYPE": "hyperliquid",
    "UNI": "uniswap",
}

CHINA_INDEX_SECIDS = [
    ("1.000001", "上证指数"),
    ("0.399001", "深证成指"),
    ("0.399006", "创业板指"),
    ("1.000300", "沪深300"),
    ("1.000905", "中证500"),
]
CHINA_CORE_SECIDS = [
    ("1.600519", "贵州茅台"),
    ("0.300750", "宁德时代"),
    ("0.002594", "比亚迪"),
    ("1.601318", "中国平安"),
    ("1.600036", "招商银行"),
    ("0.000858", "五粮液"),
    ("1.688981", "中芯国际"),
    ("0.000333", "美的集团"),
    ("0.300760", "迈瑞医疗"),
    ("1.600276", "恒瑞医药"),
]

BTC_ETFS = [
    ("IBIT", "BlackRock IBIT"),
    ("FBTC", "Fidelity FBTC"),
    ("GBTC", "Grayscale GBTC"),
    ("BITB", "Bitwise BITB"),
    ("ARKB", "ARK 21Shares ARKB"),
    ("HODL", "VanEck HODL"),
    ("BTCO", "Invesco BTCO"),
]
ETH_ETFS = [
    ("ETHA", "BlackRock ETHA"),
    ("FETH", "Fidelity FETH"),
    ("ETHE", "Grayscale ETHE"),
    ("CETH", "21Shares CETH"),
]

STABLE_SYMBOLS = {"usdt", "usdc", "dai", "usde", "usds", "fdusd", "tusd", "usdd", "usdp", "pyusd", "frax"}
AI_SYMBOLS = {"FET", "VIRTUAL", "TAO", "VVV", "AIXBT", "AI16Z", "GRIFFAIN", "COOKIE", "ARC", "SWARMS", "PAAL"}
MEME_SYMBOLS = {"DOGE", "SHIB", "PEPE", "TRUMP", "BONK", "FLOKI", "WIF", "BRETT", "MOG", "PENGU"}
LAYER1_SYMBOLS = {"BTC", "ETH", "BNB", "SOL", "ADA", "TRX", "AVAX", "SUI", "TON", "DOT", "NEAR", "APT", "ATOM", "SEI"}
RWA_KEYWORDS = ("rwa", "tokenization", "tokenized", "real-world", "real world", "treasury", "buidl", "ondo", "centrifuge")
CRYPTO_FALLBACK_SYMBOLS = [
    ("BTCUSDT", "bitcoin", "btc", "Bitcoin"),
    ("ETHUSDT", "ethereum", "eth", "Ethereum"),
    ("BNBUSDT", "binancecoin", "bnb", "BNB"),
    ("SOLUSDT", "solana", "sol", "Solana"),
    ("XRPUSDT", "ripple", "xrp", "XRP"),
    ("DOGEUSDT", "dogecoin", "doge", "Dogecoin"),
    ("ADAUSDT", "cardano", "ada", "Cardano"),
    ("TRXUSDT", "tron", "trx", "TRON"),
    ("AVAXUSDT", "avalanche-2", "avax", "Avalanche"),
    ("LINKUSDT", "chainlink", "link", "Chainlink"),
    ("DOTUSDT", "polkadot", "dot", "Polkadot"),
    ("SHIBUSDT", "shiba-inu", "shib", "Shiba Inu"),
    ("PEPEUSDT", "pepe", "pepe", "Pepe"),
    ("NEARUSDT", "near", "near", "NEAR Protocol"),
    ("APTUSDT", "aptos", "apt", "Aptos"),
    ("ARBUSDT", "arbitrum", "arb", "Arbitrum"),
]

RSS_SOURCES = [
    ("Fed Press", "us", "https://www.federalreserve.gov/feeds/press_all.xml", 1.2),
    ("Yahoo US", "us", "https://feeds.finance.yahoo.com/rss/2.0/headline?s=%5EGSPC,%5EIXIC,%5EDJI,SPY,QQQ&region=US&lang=en-US", 1.0),
    ("CNBC Markets", "us", "https://www.cnbc.com/id/100003114/device/rss/rss.html", 1.0),
    ("Yahoo China", "china", "https://feeds.finance.yahoo.com/rss/2.0/headline?s=000001.SS,399001.SZ,FXI,MCHI&region=US&lang=en-US", 0.9),
    ("SCMP China Economy", "china", "https://www.scmp.com/rss/91/feed", 0.9),
    ("Cointelegraph", "crypto", "https://cointelegraph.com/rss", 1.0),
    ("Decrypt", "crypto", "https://decrypt.co/feed", 0.9),
]


@dataclass
class Quote:
    symbol: str
    name: str
    price: float | None = None
    change_pct: float | None = None
    change: float | None = None
    volume: float | None = None
    value_traded: float | None = None
    currency: str = "USD"
    sparkline: list[float] | None = None


def run_once(output_dir: Path, send: bool = False, timezone_name: str = DEFAULT_TIMEZONE) -> dict[str, Any]:
    RUN_CACHE.clear()
    generated_at = now_in_timezone(timezone_name)
    snapshot = build_snapshot(generated_at)
    latest_dir, archive_dir = prepare_output_dirs(output_dir, generated_at)

    json_text = json.dumps(snapshot, ensure_ascii=False, indent=2)
    for base in (latest_dir, archive_dir):
        (base / "snapshot.json").write_text(json_text, encoding="utf-8")

    markdown = render_markdown(snapshot)
    svg_pages = render_svg_pages(snapshot)
    for base in (latest_dir, archive_dir):
        (base / "telegram.md").write_text(markdown, encoding="utf-8")
        png_paths = []
        for page in svg_pages:
            svg_path = base / page["svg"]
            png_path = base / page["png"]
            svg_path.write_text(str(page["content"]), encoding="utf-8")
            convert_svg_to_png(svg_path, png_path)
            png_paths.append(png_path)
        # Keep the legacy filename as the first overview image for easy local preview.
        (base / "infographic.svg").write_text(str(svg_pages[0]["content"]), encoding="utf-8")
        convert_svg_to_png(base / "infographic.svg", base / "infographic.png")

    telegram_status = {"enabled": send, "sent": [], "errors": []}
    if send:
        image_paths = [latest_dir / str(page["png"]) for page in svg_pages] if os.getenv("WILSON_SEND_IMAGES", "1") == "1" else []
        telegram_status = push_to_telegram(markdown, image_paths, output_dir)

    status = {
        "generated_at": generated_at.isoformat(),
        "output_dir": str(latest_dir),
        "archive_dir": str(archive_dir),
        "markdown": str(latest_dir / "telegram.md"),
        "png": str(latest_dir / "infographic.png"),
        "png_pages": [str(latest_dir / str(page["png"])) for page in svg_pages],
        "telegram": telegram_status,
        "errors": snapshot.get("errors", []),
    }
    (latest_dir / "status.json").write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
    (archive_dir / "status.json").write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
    organize_archive_run(archive_dir)
    return status


def watch(output_dir: Path, send: bool, interval_minutes: int, timezone_name: str) -> None:
    while True:
        status = run_once(output_dir, send=send, timezone_name=timezone_name)
        print(json.dumps(status, ensure_ascii=False), flush=True)
        time.sleep(max(1, interval_minutes) * 60)


def build_snapshot(generated_at: datetime) -> dict[str, Any]:
    errors: list[str] = []
    news, news_errors = fetch_news()
    errors.extend(news_errors)

    us = safe_market("US Market", fetch_us_market, news, errors)
    china = safe_market("China Market", fetch_china_market, news, errors)
    crypto = safe_market("Crypto Market", fetch_crypto_market, news, errors)
    rwa = safe_market("RWA Market", fetch_rwa_market, news, errors, crypto)
    daily_market = safe_call(fetch_daily_market_quotes, {"quotes": []})
    heatmap = build_heatmap(us, china, crypto, rwa)
    wilson_view = build_wilson_view(us, china, crypto, rwa)

    return {
        "title": "Wilson's Market News",
        "generated_at": generated_at.isoformat(),
        "generated_at_display": generated_at.strftime("%Y-%m-%d %H:%M"),
        "timezone": "UTC+8",
        "frequency": "每4小时更新一次",
        "heatmap": heatmap,
        "us_market": us,
        "china_market": china,
        "crypto_market": crypto,
        "rwa_market": rwa,
        "daily_market": daily_market,
        "wilson_view": wilson_view[:150],
        "errors": errors,
    }


def safe_market(name: str, fn, news: dict[str, list[dict[str, Any]]], errors: list[str], *args: Any) -> dict[str, Any]:  # noqa: ANN001
    try:
        return fn(news, *args)
    except Exception as exc:  # noqa: BLE001 - one failed source should not stop the bot.
        errors.append(f"{name}: {exc}")
        return {"title": name, "error": str(exc)}


def fetch_us_market(news: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    indices = fetch_yahoo_quotes(US_INDICES)
    sectors = sorted(fetch_yahoo_quotes(US_SECTOR_ETFS), key=lambda item: safe_float(item.change_pct), reverse=True)
    etfs = sorted(fetch_yahoo_quotes(US_ETFS), key=lambda item: safe_float(item.value_traded), reverse=True)
    ai = sorted(fetch_yahoo_quotes(US_AI), key=lambda item: safe_float(item.change_pct), reverse=True)
    stock_quotes = fetch_yahoo_quotes(US_STOCKS, max_workers=12)
    ranked = sorted(stock_quotes, key=lambda item: safe_float(item.change_pct), reverse=True)
    traded = sorted(stock_quotes, key=lambda item: safe_float(item.value_traded), reverse=True)

    spx = first_quote(indices, "^GSPC")
    return {
        "title": "美国市场",
        "color": "#1565d8",
        "macro_policy": news_lines(news.get("us", []), ("fed", "fomc", "rate", "inflation", "cpi", "pce", "jobs", "tariff", "policy"), 3),
        "market_overview": [quote_line(q) for q in indices],
        "sector_rotation": [quote_line(q) for q in sectors[:5]],
        "etf_flow": [etf_proxy_line(q) for q in etfs[:5]],
        "ai_sector": [quote_line(q) for q in ai[:5]],
        "top_gainers": [quote_row(q) for q in ranked[:5]],
        "top_losers": [quote_row(q) for q in ranked[-5:]][::-1],
        "top_traded": [quote_row(q) for q in traded[:5]],
        "primary": quote_to_dict(spx),
        "indices": [quote_to_dict(q) for q in indices],
        "sectors": [quote_to_dict(q) for q in sectors[:8]],
        "note": "ETF Flow 为主要 ETF 成交额/涨跌代理，MVP 未接入付费净流入接口。",
    }


def fetch_china_market(news: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    indices = safe_call(lambda: fetch_eastmoney_ulist(CHINA_INDEX_SECIDS), [])
    core_assets = sorted(safe_call(lambda: fetch_eastmoney_ulist(CHINA_CORE_SECIDS), []), key=lambda item: safe_float(item.change_pct), reverse=True)
    gainers = safe_call(lambda: fetch_eastmoney_clist(fid="f3", po="1", limit=5), [])
    losers = safe_call(lambda: fetch_eastmoney_clist(fid="f3", po="0", limit=5), [])
    traded = safe_call(lambda: fetch_eastmoney_clist(fid="f6", po="1", limit=5), [])
    sectors = safe_call(lambda: fetch_eastmoney_boards("m:90+t:2", limit=5), [])
    concepts = safe_call(lambda: fetch_eastmoney_boards("m:90+t:3", limit=5), [])
    northbound = safe_call(fetch_northbound, {"text": "北向资金源暂未返回有效数据。"})
    fx_quote = first_quote(fetch_yahoo_quotes([("CNY=X", "人民币汇率")]), "CNY=X")

    csi500 = first_quote(indices, "000905")
    overview = [quote_line(q, currency="¥") for q in indices]
    if fx_quote:
        overview.append(f"人民币汇率 {format_price(fx_quote.price, '')} ({pct(fx_quote.change_pct)})")
    return {
        "title": "中国市场",
        "color": "#e3272d",
        "policy_update": news_lines(
            news.get("china", []),
            ("china", "policy", "stimulus", "trade", "tariff", "rare earth", "philippines", "hong kong", "pboc", "csrc", "lpr", "rrr", "央行", "证监", "政策"),
            3,
        ),
        "market_overview": overview,
        "northbound_capital_flow": northbound,
        "hot_sectors": [board_line(item) for item in (sectors + concepts)[:6]],
        "core_assets": [quote_line(q, currency="¥") for q in core_assets[:5]],
        "top_gainers": [quote_row(q, currency="¥") for q in gainers],
        "top_losers": [quote_row(q, currency="¥") for q in losers],
        "top_traded": [quote_row(q, currency="¥") for q in traded],
        "primary": quote_to_dict(csi500),
        "indices": [quote_to_dict(q) for q in indices],
        "fx": quote_to_dict(fx_quote),
        "sectors": sectors[:5],
        "concepts": concepts[:5],
    }


def fetch_crypto_market(news: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    top100 = safe_call(fetch_coingecko_top100, [])
    if not top100:
        top100 = fetch_binance_market_coins()
    categories = fetch_coingecko_categories()
    global_data = safe_call(lambda: http_json("https://api.coingecko.com/api/v3/global"), {})
    defi_data = safe_call(lambda: http_json("https://api.coingecko.com/api/v3/global/decentralized_finance_defi"), {})
    global_metrics = crypto_global_metrics(global_data, defi_data)
    fear_greed = fetch_fear_greed()
    dex = fetch_dex_volume()
    stablecoins = fetch_stablecoin_growth()
    cex = fetch_cex_volume(top100)
    etf_quotes = sorted(fetch_yahoo_quotes(BTC_ETFS + ETH_ETFS), key=lambda item: safe_float(item.value_traded), reverse=True)

    btc = coin_by_symbol(top100, "btc")
    eth = coin_by_symbol(top100, "eth")
    daily_assets = fetch_daily_crypto_assets(top100)
    ai_sector = sector_snapshot("AI Agent", top100, categories, "ai-agents", AI_SYMBOLS)
    meme_sector = sector_snapshot("Meme", top100, categories, "meme-token", MEME_SYMBOLS)
    layer1_sector = sector_snapshot("Layer1", top100, categories, "layer-1", LAYER1_SYMBOLS)
    gainers = sorted(top100, key=lambda item: safe_float(item.get("price_change_percentage_24h")), reverse=True)[:5]
    losers = sorted(top100, key=lambda item: safe_float(item.get("price_change_percentage_24h")))[:5]

    return {
        "title": "加密市场",
        "color": "#f5b400",
        "market_overview": crypto_overview_from_metrics(global_metrics),
        "global_metrics": global_metrics,
        "fear_greed": fear_greed,
        "btc": coin_summary(btc),
        "eth": coin_summary(eth),
        "etf_flow": [etf_proxy_line(q) for q in etf_quotes[:5]],
        "stablecoin_growth": stablecoins,
        "cex_volume": cex,
        "dex_volume": dex,
        "ai_agent_sector": ai_sector,
        "meme_sector": meme_sector,
        "layer1_sector": layer1_sector,
        "top100_ranking": {
            "gainers": [coin_row(item) for item in gainers],
            "losers": [coin_row(item) for item in losers],
        },
        "major_events": news_lines(news.get("crypto", []), ("bitcoin", "ethereum", "etf", "stablecoin", "sec", "hack", "exchange"), 4),
        "top100": [coin_row(item) for item in top100[:10]],
        "daily_assets": daily_assets,
        "primary": coin_quote_dict(btc),
        "note": "ETF Flow 为 ETF 成交额/涨跌代理，MVP 未接入付费净申购赎回接口。",
    }


def fetch_daily_market_quotes() -> dict[str, Any]:
    quotes = fetch_yahoo_quotes(DAILY_MARKET_QUOTES, max_workers=5)
    return {"quotes": [quote_to_dict(quote) for quote in quotes]}


def fetch_daily_crypto_assets(top100: list[dict[str, Any]]) -> dict[str, Any]:
    assets: dict[str, dict[str, Any]] = {}
    for symbol in DAILY_CRYPTO_IDS:
        coin = coin_by_symbol(top100, symbol)
        if coin:
            assets[symbol] = coin_row(coin)
    missing_ids = [coin_id for symbol, coin_id in DAILY_CRYPTO_IDS.items() if symbol not in assets]
    if missing_ids:
        url = "https://api.coingecko.com/api/v3/coins/markets?" + urllib.parse.urlencode(
            {
                "vs_currency": "usd",
                "ids": ",".join(missing_ids),
                "sparkline": "false",
                "price_change_percentage": "24h",
            }
        )
        for coin in safe_call(lambda: http_json(url), []):
            symbol = str(coin.get("symbol", "")).upper()
            if symbol in DAILY_CRYPTO_IDS:
                assets[symbol] = coin_row(coin)
    return assets


def fetch_rwa_market(news: dict[str, list[dict[str, Any]]], crypto: dict[str, Any]) -> dict[str, Any]:
    protocols = safe_call(lambda: http_json("https://api.llama.fi/protocols"), [])
    rwa_protocols = [item for item in protocols if str(item.get("category", "")).lower() == "rwa"]
    rwa_protocols.sort(key=lambda item: safe_float(item.get("tvl")), reverse=True)
    total_tvl = sum(safe_float(item.get("tvl")) for item in rwa_protocols)
    weighted_change = weighted_average([safe_float(item.get("change_1d")) for item in rwa_protocols], [safe_float(item.get("tvl")) for item in rwa_protocols])
    categories = fetch_coingecko_categories()
    rwa_category = categories.get("real-world-assets-rwa", {})
    dex = crypto.get("dex_volume", {}) if isinstance(crypto, dict) else {}

    rwa_news = [item for item in news.get("crypto", []) if any(keyword in item.get("text", "").lower() for keyword in RWA_KEYWORDS)]
    top_projects = [
        {
            "name": item.get("name"),
            "chain": item.get("chain"),
            "tvl": safe_float(item.get("tvl")),
            "change_1d": item.get("change_1d"),
            "mcap": item.get("mcap"),
        }
        for item in rwa_protocols[:8]
    ]
    market_cap = safe_float(rwa_category.get("market_cap"))
    volume = safe_float(rwa_category.get("volume_24h"))
    market_cap_change = safe_float(rwa_category.get("market_cap_change_24h"))
    capital_flow = total_tvl * weighted_change / 100 if total_tvl and weighted_change else 0

    return {
        "title": "RWA市场",
        "color": "#169b62",
        "tvl": {"value": total_tvl, "change_1d": weighted_change},
        "market_cap": {"value": market_cap, "change_24h": market_cap_change},
        "volume": {"value": volume, "change_24h": None, "dex_context": dex.get("total24h") if isinstance(dex, dict) else None},
        "capital_flow": {"value": capital_flow, "change_pct": weighted_change},
        "top_projects": top_projects,
        "major_events": [translate_for_display(item["title"]) for item in rwa_news[:4]] or ["RWA 暂无高频重大新闻，重点观察 TVL 与头部项目变化。"],
        "primary": {"label": "RWA TVL", "price": total_tvl, "change_pct": weighted_change, "symbol": "RWA"},
    }


def fetch_yahoo_quotes(symbols: list[tuple[str, str]], max_workers: int = 8) -> list[Quote]:
    quotes: list[Quote] = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(fetch_yahoo_quote, symbol, name): (symbol, name) for symbol, name in symbols}
        for future in as_completed(futures):
            quote = future.result()
            if quote and quote.price is not None:
                quotes.append(quote)
    order = {symbol: index for index, (symbol, _) in enumerate(symbols)}
    quotes.sort(key=lambda item: order.get(item.symbol, 10_000))
    return quotes


def fetch_yahoo_quote(symbol: str, name: str) -> Quote | None:
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(symbol)}?range=5d&interval=1d"
    try:
        data = http_json(url, timeout=QUOTE_TIMEOUT)
        result = (data.get("chart", {}).get("result") or [None])[0]
        if not result:
            return None
        meta = result.get("meta", {})
        quote = (result.get("indicators", {}).get("quote") or [{}])[0]
        closes = [float(value) for value in quote.get("close", []) if value is not None]
        price_value = first_number(meta.get("regularMarketPrice"), closes[-1] if closes else None)
        previous = first_number(meta.get("chartPreviousClose"), closes[-2] if len(closes) > 1 else None)
        if price_value is None or previous in (None, 0):
            return None
        change = price_value - previous
        volume = first_number(meta.get("regularMarketVolume"))
        return Quote(
            symbol=symbol.replace("^", ""),
            name=name,
            price=price_value,
            change=change,
            change_pct=change / previous * 100,
            volume=volume,
            value_traded=(price_value * volume) if volume is not None else None,
            currency=meta.get("currency", "USD"),
            sparkline=closes[-8:],
        )
    except Exception:
        return None


def fetch_eastmoney_ulist(secids: list[tuple[str, str]]) -> list[Quote]:
    fields = "f12,f14,f2,f3,f4,f5,f6,f17,f18"
    ids = ",".join(secid for secid, _ in secids)
    url = "https://push2.eastmoney.com/api/qt/ulist.np/get?" + urllib.parse.urlencode({"fltt": "2", "invt": "2", "fields": fields, "secids": ids})
    data = http_json(url, timeout=QUOTE_TIMEOUT, referer="https://quote.eastmoney.com/")
    name_map = {secid.split(".")[-1]: name for secid, name in secids}
    order = {secid.split(".")[-1]: index for index, (secid, _) in enumerate(secids)}
    quotes = []
    for item in data.get("data", {}).get("diff", []):
        symbol = str(item.get("f12") or "")
        price_value = first_number(item.get("f2"))
        change_pct = first_number(item.get("f3"))
        if not symbol or price_value is None or change_pct is None:
            continue
        quotes.append(
            Quote(
                symbol=symbol,
                name=name_map.get(symbol, str(item.get("f14") or symbol)),
                price=price_value,
                change=first_number(item.get("f4")),
                change_pct=change_pct,
                volume=first_number(item.get("f5")),
                value_traded=first_number(item.get("f6")),
                currency="CNY",
            )
        )
    quotes.sort(key=lambda item: order.get(item.symbol, 10_000))
    return quotes


def fetch_eastmoney_clist(fid: str, po: str, limit: int) -> list[Quote]:
    fields = "f12,f14,f2,f3,f4,f5,f6,f17,f18"
    url = "https://push2.eastmoney.com/api/qt/clist/get?" + urllib.parse.urlencode(
        {
            "pn": "1",
            "pz": "40",
            "po": po,
            "np": "1",
            "fltt": "2",
            "invt": "2",
            "fid": fid,
            "fs": "m:1+t:2,m:0+t:6",
            "fields": fields,
        }
    )
    data = http_json(url, timeout=QUOTE_TIMEOUT, referer="https://quote.eastmoney.com/")
    quotes = []
    for item in data.get("data", {}).get("diff", []):
        name = str(item.get("f14") or "")
        if "退" in name or name.upper().startswith("*ST") or name.upper().startswith("ST"):
            continue
        price_value = first_number(item.get("f2"))
        change_pct = first_number(item.get("f3"))
        if price_value is None or change_pct is None:
            continue
        quotes.append(
            Quote(
                symbol=str(item.get("f12") or ""),
                name=name,
                price=price_value,
                change=first_number(item.get("f4")),
                change_pct=change_pct,
                volume=first_number(item.get("f5")),
                value_traded=first_number(item.get("f6")),
                currency="CNY",
            )
        )
        if len(quotes) >= limit:
            break
    return quotes


def fetch_eastmoney_boards(fs: str, limit: int) -> list[dict[str, Any]]:
    fields = "f12,f14,f2,f3,f62,f128,f140,f136,f152"
    url = "https://push2.eastmoney.com/api/qt/clist/get?" + urllib.parse.urlencode(
        {
            "pn": "1",
            "pz": str(limit),
            "po": "1",
            "np": "1",
            "fltt": "2",
            "invt": "2",
            "fid": "f3",
            "fs": fs,
            "fields": fields,
        }
    )
    data = http_json(url, timeout=QUOTE_TIMEOUT, referer="https://quote.eastmoney.com/")
    output = []
    for item in data.get("data", {}).get("diff", [])[:limit]:
        output.append(
            {
                "symbol": item.get("f12"),
                "name": item.get("f14"),
                "price": first_number(item.get("f2")),
                "change_pct": first_number(item.get("f3")),
                "main_inflow": first_number(item.get("f62")),
                "leader": item.get("f128"),
                "leader_symbol": item.get("f140"),
                "leader_change_pct": first_number(item.get("f136")),
            }
        )
    return output


def fetch_northbound() -> dict[str, Any]:
    url = "https://push2.eastmoney.com/api/qt/kamt/get?fields1=f1,f2,f3,f4&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63"
    data = http_json(url, timeout=QUOTE_TIMEOUT, referer="https://quote.eastmoney.com/")
    payload = data.get("data", {})
    hk2sh = payload.get("hk2sh", {})
    hk2sz = payload.get("hk2sz", {})
    sh = safe_float(hk2sh.get("netBuyAmt") or hk2sh.get("dayNetAmtIn"))
    sz = safe_float(hk2sz.get("netBuyAmt") or hk2sz.get("dayNetAmtIn"))
    total = sh + sz
    return {
        "date": hk2sh.get("date2") or hk2sh.get("date") or "",
        "shanghai": sh,
        "shenzhen": sz,
        "total": total,
        "text": f"北向净买入 {format_cny_wan(total)}（沪股通 {format_cny_wan(sh)}，深股通 {format_cny_wan(sz)}）",
    }


def fetch_coingecko_top100() -> list[dict[str, Any]]:
    url = "https://api.coingecko.com/api/v3/coins/markets?" + urllib.parse.urlencode(
        {
            "vs_currency": "usd",
            "order": "market_cap_desc",
            "per_page": "130",
            "page": "1",
            "sparkline": "false",
            "price_change_percentage": "24h",
        }
    )
    coins = http_json(url)
    return [coin for coin in coins if not is_stablecoin(coin)][:100]


def fetch_binance_market_coins() -> list[dict[str, Any]]:
    symbol_map = {symbol: (coin_id, short_symbol, name) for symbol, coin_id, short_symbol, name in CRYPTO_FALLBACK_SYMBOLS}
    symbols_json = json.dumps(list(symbol_map), separators=(",", ":"))
    url = "https://api.binance.com/api/v3/ticker/24hr?" + urllib.parse.urlencode({"symbols": symbols_json})
    data = safe_call(lambda: http_json(url), [])
    coins = []
    for index, item in enumerate(data if isinstance(data, list) else [], 1):
        coin_id, short_symbol, name = symbol_map.get(str(item.get("symbol")), ("", "", ""))
        if not coin_id:
            continue
        coins.append(
            {
                "id": coin_id,
                "symbol": short_symbol,
                "name": name,
                "current_price": first_number(item.get("lastPrice")),
                "price_change_percentage_24h": first_number(item.get("priceChangePercent")),
                "total_volume": first_number(item.get("quoteVolume")),
                "market_cap": None,
                "market_cap_rank": index,
            }
        )
    return coins


def fetch_coingecko_categories() -> dict[str, dict[str, Any]]:
    if "coingecko_categories" in RUN_CACHE:
        return RUN_CACHE["coingecko_categories"]
    data = safe_call(lambda: http_json("https://api.coingecko.com/api/v3/coins/categories"), [])
    categories = {str(item.get("id")): item for item in data if isinstance(item, dict)}
    RUN_CACHE["coingecko_categories"] = categories
    return categories


def fetch_dex_volume() -> dict[str, Any]:
    data = safe_call(lambda: http_json("https://api.llama.fi/overview/dexs?excludeTotalDataChart=true&excludeTotalDataChartBreakdown=true"), {})
    protocols = sorted(data.get("protocols", []), key=lambda item: safe_float(item.get("total24h")), reverse=True) if isinstance(data, dict) else []
    return {
        "total24h": safe_float(data.get("total24h")) if isinstance(data, dict) else 0,
        "total7d": safe_float(data.get("total7d")) if isinstance(data, dict) else 0,
        "change_1d": data.get("change_1d") if isinstance(data, dict) else None,
        "top": [
            {
                "name": item.get("displayName") or item.get("name"),
                "volume_24h": safe_float(item.get("total24h")),
                "change_1d": item.get("change_1d"),
            }
            for item in protocols[:5]
        ],
        "text": f"DEX 24h 成交 {format_usd(safe_float(data.get('total24h')) if isinstance(data, dict) else 0)}，日变动 {pct(data.get('change_1d') if isinstance(data, dict) else None)}",
    }


def fetch_stablecoin_growth() -> dict[str, Any]:
    data = safe_call(lambda: http_json("https://stablecoins.llama.fi/stablecoins?includePrices=true"), {})
    assets = data.get("peggedAssets", []) if isinstance(data, dict) else []
    current = sum(safe_float(item.get("circulating", {}).get("peggedUSD")) for item in assets)
    prev_day = sum(safe_float(item.get("circulatingPrevDay", {}).get("peggedUSD")) for item in assets)
    prev_week = sum(safe_float(item.get("circulatingPrevWeek", {}).get("peggedUSD")) for item in assets)
    change_1d = pct_change(current, prev_day)
    change_7d = pct_change(current, prev_week)
    top = sorted(assets, key=lambda item: safe_float(item.get("circulating", {}).get("peggedUSD")), reverse=True)[:5]
    return {
        "current": current,
        "change_1d": change_1d,
        "change_7d": change_7d,
        "top": [{"symbol": item.get("symbol"), "name": item.get("name"), "supply": safe_float(item.get("circulating", {}).get("peggedUSD"))} for item in top],
        "text": f"稳定币总供给 {format_usd(current)}，24h {pct(change_1d)}，7d {pct(change_7d)}",
    }


def fetch_cex_volume(top100: list[dict[str, Any]]) -> dict[str, Any]:
    exchanges = safe_call(lambda: http_json("https://api.coingecko.com/api/v3/exchanges?per_page=10&page=1"), [])
    btc = coin_by_symbol(top100, "btc")
    btc_price = safe_float(btc.get("current_price")) if btc else 0
    rows = []
    for item in exchanges[:8] if isinstance(exchanges, list) else []:
        volume_btc = safe_float(item.get("trade_volume_24h_btc"))
        rows.append({"name": item.get("name"), "volume_24h": volume_btc * btc_price if btc_price else volume_btc, "trust_score": item.get("trust_score")})
    total = sum(row["volume_24h"] for row in rows)
    if total <= 0:
        return fetch_binance_cex_volume()
    return {"total24h": total, "top": rows[:5], "text": f"Top CEX 24h 成交约 {format_usd(total)}（CoinGecko Top10 估算）"}


def fetch_binance_cex_volume() -> dict[str, Any]:
    data = safe_call(lambda: http_json("https://api.binance.com/api/v3/ticker/24hr"), [])
    rows = []
    for item in data if isinstance(data, list) else []:
        symbol = str(item.get("symbol", ""))
        if not symbol.endswith(("USDT", "USDC", "FDUSD")):
            continue
        volume = safe_float(item.get("quoteVolume"))
        if volume <= 0:
            continue
        rows.append({"name": symbol, "volume_24h": volume, "change_pct": first_number(item.get("priceChangePercent"))})
    rows.sort(key=lambda item: item["volume_24h"], reverse=True)
    total = sum(item["volume_24h"] for item in rows)
    return {
        "total24h": total,
        "top": rows[:5],
        "text": f"Binance Spot 24h 成交约 {format_usd(total)}（CoinGecko 限流时 fallback）",
    }


def fetch_fear_greed() -> dict[str, Any]:
    data = safe_call(lambda: http_json("https://api.alternative.me/fng/?limit=1"), {})
    rows = data.get("data", []) if isinstance(data, dict) else []
    if not rows:
        return {}
    item = rows[0]
    value = first_number(item.get("value"))
    return {
        "value": value,
        "classification": item.get("value_classification") or "",
        "timestamp": item.get("timestamp"),
        "text": f"{int(value) if value is not None else '-'}（{item.get('value_classification') or 'N/A'}）",
    }


def fetch_news() -> tuple[dict[str, list[dict[str, Any]]], list[str]]:
    buckets = {"us": [], "china": [], "crypto": []}
    errors = []
    for name, market, url, weight in RSS_SOURCES:
        try:
            for item in fetch_rss(url)[:20]:
                item["source"] = name
                item["weight"] = weight
                item["market"] = market
                item["text"] = f"{item.get('title', '')} {item.get('summary', '')}"
                buckets[market].append(item)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{name}: {exc}")
    for market, items in buckets.items():
        items.sort(key=lambda item: (item.get("published_at") or datetime.now(timezone.utc)), reverse=True)
        buckets[market] = items[:30]
    return buckets, errors


def fetch_rss(url: str) -> list[dict[str, Any]]:
    root = ET.fromstring(http_bytes(url))
    entries = list(root.findall(".//item")) or list(root.findall(".//{http://www.w3.org/2005/Atom}entry"))
    items = []
    for entry in entries:
        title = first_text(entry, ["title", "{http://www.w3.org/2005/Atom}title"])
        summary = first_text(entry, ["description", "summary", "{http://www.w3.org/2005/Atom}summary", "{http://purl.org/rss/1.0/modules/content/}encoded"])
        published = first_text(entry, ["pubDate", "published", "updated", "{http://www.w3.org/2005/Atom}published", "{http://www.w3.org/2005/Atom}updated"])
        link = first_link(entry)
        if title:
            items.append({"title": clean_text(title), "summary": clean_text(summary), "url": link, "published_at": parse_datetime(published)})
    return items


def build_heatmap(us: dict[str, Any], china: dict[str, Any], crypto: dict[str, Any], rwa: dict[str, Any]) -> list[dict[str, Any]]:
    us_score = score_from_changes(
        (us.get("primary") or {}).get("change_pct"),
        *[item.get("change_pct") for item in as_list(us.get("indices"))[:3] if isinstance(item, dict)],
        *[item.get("change_pct") for item in as_list(us.get("sectors"))[:5] if isinstance(item, dict)],
    )
    china_score = score_from_changes(
        (china.get("primary") or {}).get("change_pct"),
        *[item.get("change_pct") for item in as_list(china.get("indices")) if isinstance(item, dict)],
    )
    crypto_score = score_from_changes(
        (crypto.get("btc") or {}).get("change_pct"),
        (crypto.get("eth") or {}).get("change_pct"),
        (crypto.get("stablecoin_growth") or {}).get("change_1d"),
        (crypto.get("dex_volume") or {}).get("change_1d"),
    )
    rwa_score = score_from_changes(
        (rwa.get("tvl") or {}).get("change_1d"),
        (rwa.get("market_cap") or {}).get("change_24h"),
        (rwa.get("capital_flow") or {}).get("change_pct"),
    )
    return [
        market_heat_card("US Market", "us", us_score, f"S&P 500 {pct((us.get('primary') or {}).get('change_pct'))}"),
        market_heat_card("China Market", "china", china_score, f"中证500 {pct((china.get('primary') or {}).get('change_pct'))}"),
        market_heat_card("Crypto Market", "crypto", crypto_score, f"BTC {pct((crypto.get('btc') or {}).get('change_pct'))}"),
        market_heat_card("RWA Market", "rwa", rwa_score, rwa_summary_line(rwa)),
    ]


def heat_tile(label: str, source: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(source, dict):
        return None
    value = first_number(source.get("price"), source.get("current"), source.get("total24h"), source.get("value"))
    change = first_number(source.get("change_pct"), source.get("change_1d"), source.get("change_24h"), source.get("price_change_percentage_24h"))
    if value is None and change is None:
        return None
    return {"label": label, "value": value, "change_pct": change}


def score_from_changes(*changes: Any) -> int:
    values = [number for number in (first_number(change) for change in changes) if number is not None]
    if not values:
        return 50
    average = sum(values) / len(values)
    score = 50 + average * 6
    score += min(12, max(-12, (sum(1 for value in values if value > 0) - sum(1 for value in values if value < 0)) * 3))
    return int(max(0, min(100, round(score))))


def market_status(score: int) -> str:
    if score >= 67:
        return "Bullish"
    if score <= 43:
        return "Bearish"
    return "Neutral"


def market_heat_card(label: str, key: str, score: int, summary: str) -> dict[str, Any]:
    return {"label": label, "key": key, "score": score, "status": market_status(score), "summary": summary}


def build_wilson_view(us: dict[str, Any], china: dict[str, Any], crypto: dict[str, Any], rwa: dict[str, Any]) -> str:
    signals = []
    spx = safe_float((us.get("primary") or {}).get("change_pct"))
    csi = safe_float((china.get("primary") or {}).get("change_pct"))
    btc = safe_float((crypto.get("btc") or {}).get("change_pct"))
    rwa_change = safe_float((rwa.get("tvl") or {}).get("change_1d"))
    if spx > 0:
        signals.append("美股风险偏好修复")
    elif spx < 0:
        signals.append("美股承压")
    if csi > 0:
        signals.append("A股相对走强")
    elif csi < 0:
        signals.append("A股需看政策与资金承接")
    if btc > 0:
        signals.append("BTC带动加密反弹")
    elif btc < 0:
        signals.append("加密市场波动偏防守")
    if rwa_change > 0:
        signals.append("RWA TVL小幅流入")
    elif rwa_change < 0:
        signals.append("RWA TVL短线回落")
    text = "；".join(signals[:4]) or "市场信号分散"
    return (
        f"{text}。本周期市场仍以风险偏好和资金流切换为主，短线不宜只看单一涨跌。"
        "更适合跟踪美股科技龙头、A股政策承接、BTC关键位与RWA资金流，等待量价确认后再提高仓位。"
    )


def render_markdown(snapshot: dict[str, Any]) -> str:
    us = snapshot.get("us_market", {})
    crypto = snapshot.get("crypto_market", {})
    rwa = snapshot.get("rwa_market", {})
    heatmap = {item.get("key"): item for item in as_list(snapshot.get("heatmap")) if isinstance(item, dict)}
    crypto_metrics = crypto.get("global_metrics") or {}
    fear = crypto.get("fear_greed") or {}
    lines = [
        "Wilson's Market News",
        f"更新时间：{snapshot['generated_at_display']} {snapshot['timezone']}",
        "每4小时更新一次",
        "",
        "【Market Heat Map】",
        heatmap_text_line("🇺🇸 US Market", heatmap.get("us")),
        heatmap_text_line("🇨🇳 China Market", heatmap.get("china")),
        heatmap_text_line("🟡 Crypto Market", heatmap.get("crypto")),
        f"🟢 RWA Market：{rwa_summary_line(rwa)}",
        "",
        "【US Market】",
        "Macro Policy：",
        *bullet_lines(us.get("macro_policy"), 2),
        "Market Overview：",
        f"• S&P 500：{quote_text(find_quote(us.get('indices'), 'GSPC', 'S&P 500'))}",
        f"• Nasdaq：{quote_text(find_quote(us.get('indices'), 'IXIC', 'Nasdaq'))}",
        f"• Dow Jones：{quote_text(find_quote(us.get('indices'), 'DJI', 'Dow Jones'))}",
        f"• VIX：{quote_text(find_quote(us.get('indices'), 'VIX', 'VIX'))}",
        f"• DXY：{quote_text(find_quote(us.get('indices'), 'DX-Y.NYB', 'DXY'))}",
        "",
        "【Crypto Market】",
        f"• 总市值：{format_usd(crypto_metrics.get('market_cap'))}",
        f"• 24h成交：{format_usd(crypto_metrics.get('volume_24h'))}",
        f"• BTC：{coin_brief(crypto.get('btc'))}",
        f"• ETH：{coin_brief(crypto.get('eth'))}",
        f"• BTC Dominance：{format_percent_value(crypto_metrics.get('btc_dominance'))}",
        f"• Fear & Greed：{fear_greed_text(fear)}",
        "",
        "【Wilson's View】",
        str(snapshot.get("wilson_view", "")),
        "",
        "【Disclaimer】",
        DISCLAIMER,
    ]
    return "\n".join(line for line in lines if line is not None)


def render_html_report(snapshot: dict[str, Any]) -> str:
    us = snapshot.get("us_market", {})
    china = snapshot.get("china_market", {})
    crypto = snapshot.get("crypto_market", {})
    rwa = snapshot.get("rwa_market", {})
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>{h(snapshot.get("title"))}</title>
  <style>
    @page {{ size: A4; margin: 12mm; }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      color: #17202a;
      background: #f4f7fb;
      font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", Arial, sans-serif;
      font-size: 12px;
      line-height: 1.5;
    }}
    .cover {{
      min-height: 96vh;
      padding: 30mm 12mm 20mm;
      color: #ffffff;
      background: #061a2c;
      border-radius: 8px;
      page-break-after: always;
    }}
    h1 {{ margin: 0 0 8px; font-size: 38px; line-height: 1.1; letter-spacing: 0; }}
    .subtitle {{ color: #d7e5f5; font-size: 15px; margin-bottom: 22px; }}
    .view {{ margin: 18px 0 24px; padding: 14px 16px; border-radius: 8px; background: #07365d; font-size: 15px; font-weight: 700; }}
    .heatmap {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; margin-top: 18px; }}
    .heat {{ padding: 12px; border: 1px solid rgba(255,255,255,.18); border-radius: 8px; background: rgba(255,255,255,.08); }}
    .heat b {{ display: block; font-size: 13px; color: #d7e5f5; }}
    .heat strong {{ display: block; margin-top: 5px; font-size: 20px; }}
    .pos {{ color: #079455; }}
    .neg {{ color: #e03131; }}
    .page {{ page-break-before: always; padding: 4mm 0 0; }}
    .section {{
      border: 1px solid #d8e2eb;
      border-radius: 8px;
      background: #ffffff;
      overflow: hidden;
      margin-bottom: 12px;
    }}
    .bar {{ padding: 11px 14px; color: #ffffff; font-size: 20px; font-weight: 900; }}
    .blue {{ background: #1677f2; }}
    .red {{ background: #ef343b; }}
    .yellow {{ background: #f5b400; color: #163b2b; }}
    .green {{ background: #169b62; }}
    .content {{ padding: 14px; }}
    .grid2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }}
    .grid3 {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }}
    .card {{ border: 1px solid #dfe7ef; border-radius: 8px; padding: 10px; background: #fbfdff; min-height: 86px; }}
    .card h3 {{ margin: 0 0 7px; font-size: 14px; color: #17202a; }}
    ul {{ margin: 0; padding-left: 17px; }}
    li {{ margin: 0 0 4px; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 8px; font-size: 11px; }}
    th {{ text-align: left; color: #5b6875; border-bottom: 1px solid #cfd9e3; padding: 5px 6px; }}
    td {{ border-bottom: 1px solid #edf2f6; padding: 5px 6px; vertical-align: top; }}
    .metric {{ font-size: 16px; font-weight: 900; }}
    .small {{ color: #667481; font-size: 10px; }}
    .note {{ margin-top: 10px; color: #667481; font-size: 10px; }}
  </style>
</head>
<body>
  <section class="cover">
    <h1>{h(snapshot.get("title"))}</h1>
    <div class="subtitle">{h(snapshot.get("generated_at_display"))} (UTC+8) · {h(snapshot.get("frequency"))}</div>
    <div class="view">Wilson's View: {h(snapshot.get("wilson_view"))}</div>
    <h2>Market Heat Map</h2>
    <div class="heatmap">{render_html_heatmap(snapshot.get("heatmap", []))}</div>
    <p class="note">免责声明：本内容仅供参考，不构成任何投资建议。投资有风险，入市需谨慎。</p>
  </section>

  {render_market_html("🇺🇸 美国市场 / US Market", "blue", [
      ("Macro Policy", html_list(us.get("macro_policy"))),
      ("Market Overview", html_list(us.get("market_overview"))),
      ("Sector Rotation", html_list(us.get("sector_rotation"))),
      ("ETF Flow", html_list(us.get("etf_flow"))),
      ("AI Sector", html_list(us.get("ai_sector"))),
  ], us.get("top_gainers"), us.get("top_losers"))}

  {render_china_html(china)}

  {render_crypto_html(crypto)}

  {render_rwa_html(rwa)}
</body>
</html>"""


def render_html_heatmap(tiles: Any) -> str:
    output = []
    for tile in as_list(tiles):
        change = safe_float(tile.get("change_pct")) if isinstance(tile, dict) else 0
        klass = "pos" if change >= 0 else "neg"
        output.append(
            f"""<div class="heat">
              <b>{h(tile.get("label"))}</b>
              <strong>{h(format_metric(tile.get("value")))}</strong>
              <span class="{klass}">{h(pct(tile.get("change_pct")))}</span>
            </div>"""
        )
    return "\n".join(output)


def render_market_html(title: str, color_class: str, cards: list[tuple[str, str]], gainers: Any, losers: Any) -> str:
    cards_html = "".join(f'<div class="card"><h3>{h(card_title)}</h3>{body}</div>' for card_title, body in cards)
    return f"""<section class="page section">
      <div class="bar {color_class}">{h(title)}</div>
      <div class="content">
        <div class="grid2">{cards_html}</div>
        <div class="grid2">
          <div>{html_table("Top Gainers", gainers)}</div>
          <div>{html_table("Top Losers", losers)}</div>
        </div>
      </div>
    </section>"""


def render_china_html(china: dict[str, Any]) -> str:
    northbound = (china.get("northbound_capital_flow") or {}).get("text", "暂无数据")
    cards = [
        ("Policy Update", html_list(china.get("policy_update"))),
        ("Market Overview", html_list(china.get("market_overview"))),
        ("Northbound Capital Flow", f"<p>{h(northbound)}</p>"),
        ("Hot Sectors", html_list(china.get("hot_sectors"))),
        ("Core Assets", html_list(china.get("core_assets"))),
    ]
    return render_market_html("🇨🇳 中国市场 / China Market", "red", cards, china.get("top_gainers"), china.get("top_losers"))


def render_crypto_html(crypto: dict[str, Any]) -> str:
    cards = [
        ("Market Overview", html_list(crypto.get("market_overview"))),
        ("BTC / ETH", f"<p>{h(coin_brief(crypto.get('btc')))}<br>{h(coin_brief(crypto.get('eth')))}</p>"),
        ("ETF Flow", html_list(crypto.get("etf_flow"))),
        ("Stablecoin Growth", f"<p>{h((crypto.get('stablecoin_growth') or {}).get('text', '暂无数据'))}</p>"),
        ("CEX Volume", f"<p>{h((crypto.get('cex_volume') or {}).get('text', '暂无数据'))}</p>"),
        ("DEX Volume", f"<p>{h((crypto.get('dex_volume') or {}).get('text', '暂无数据'))}</p>"),
        ("AI Agent Sector", f"<p>{h(sector_plain(crypto.get('ai_agent_sector')))}</p>"),
        ("Meme Sector", f"<p>{h(sector_plain(crypto.get('meme_sector')))}</p>"),
        ("Layer1 Sector", f"<p>{h(sector_plain(crypto.get('layer1_sector')))}</p>"),
    ]
    return f"""<section class="page section">
      <div class="bar yellow">🟡 加密市场 / Crypto Market</div>
      <div class="content">
        <div class="grid3">{"".join(f'<div class="card"><h3>{h(title)}</h3>{body}</div>' for title, body in cards)}</div>
        <div class="grid2">
          <div>{html_table("Top100 Gainers", (crypto.get("top100_ranking") or {}).get("gainers"))}</div>
          <div>{html_table("Top100 Losers", (crypto.get("top100_ranking") or {}).get("losers"))}</div>
        </div>
      </div>
    </section>"""


def render_rwa_html(rwa: dict[str, Any]) -> str:
    cards = [
        ("TVL", f"{format_usd((rwa.get('tvl') or {}).get('value'))} / {pct((rwa.get('tvl') or {}).get('change_1d'))}"),
        ("Market Cap", f"{format_usd((rwa.get('market_cap') or {}).get('value'))} / {pct((rwa.get('market_cap') or {}).get('change_24h'))}"),
        ("Volume", format_usd((rwa.get("volume") or {}).get("value"))),
        ("Capital Flow", format_usd((rwa.get("capital_flow") or {}).get("value"))),
    ]
    metrics = "".join(f'<div class="card"><h3>{h(title)}</h3><div class="metric">{h(value)}</div></div>' for title, value in cards)
    return f"""<section class="page section">
      <div class="bar green">🟢 RWA市场 / Real World Assets</div>
      <div class="content">
        <div class="grid2">{metrics}</div>
        <div class="grid2">
          <div>{html_table("Top Projects", rwa_project_rows(rwa.get("top_projects")))}</div>
          <div class="card"><h3>Major Events</h3>{html_list(rwa.get("major_events"))}</div>
        </div>
      </div>
    </section>"""


def html_list(items: Any) -> str:
    values = as_list(items)
    if not values:
        return "<p>暂无数据</p>"
    return "<ul>" + "".join(f"<li>{h(item)}</li>" for item in values[:6]) + "</ul>"


def html_table(title: str, rows: Any) -> str:
    body = []
    for index, row in enumerate(as_list(rows)[:8], 1):
        if not isinstance(row, dict):
            body.append(f"<tr><td>{index}</td><td colspan=\"4\">{h(row)}</td></tr>")
            continue
        symbol = row.get("symbol") or row.get("chain") or "-"
        name = row.get("name") or row.get("symbol") or "-"
        value = row.get("price") if row.get("price") is not None else row.get("tvl") or row.get("market_cap")
        change = row.get("change_pct")
        klass = "pos" if safe_float(change) >= 0 else "neg"
        body.append(
            f"<tr><td>{index}</td><td>{h(symbol)}</td><td>{h(name)}</td><td class=\"{klass}\">{h(pct(change))}</td><td>{h(format_metric(value))}</td></tr>"
        )
    return f"""<h3>{h(title)}</h3>
    <table>
      <thead><tr><th>#</th><th>代码</th><th>名称</th><th>涨跌幅</th><th>价格/TVL</th></tr></thead>
      <tbody>{''.join(body) or '<tr><td colspan="5">暂无数据</td></tr>'}</tbody>
    </table>"""


def sector_plain(sector: Any) -> str:
    if not isinstance(sector, dict):
        return "暂无数据"
    top = "，".join(f"{row.get('symbol')} {pct(row.get('change_pct'))}" for row in as_list(sector.get("top"))[:4])
    return f"市值 {format_usd(sector.get('market_cap'))} / {pct(sector.get('change_24h'))}" + (f"；Top: {top}" if top else "")


def render_svg(snapshot: dict[str, Any]) -> str:
    width = 1280
    y = 0
    parts: list[str] = []
    add = parts.append
    add(f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="2600" viewBox="0 0 {width} 2600">')
    add("<defs>")
    add('<linearGradient id="bg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#061a2c"/><stop offset="1" stop-color="#02101d"/></linearGradient>')
    add('<linearGradient id="usg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#1184ff"/><stop offset="1" stop-color="#2144d2"/></linearGradient>')
    add('<linearGradient id="cng" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#ff343d"/><stop offset="1" stop-color="#bf141b"/></linearGradient>')
    add('<linearGradient id="crg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#ffe35a"/><stop offset="1" stop-color="#ffb100"/></linearGradient>')
    add('<linearGradient id="rwag" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#2bd982"/><stop offset="1" stop-color="#0d8c55"/></linearGradient>')
    add('<filter id="shadow" x="-10%" y="-10%" width="120%" height="140%"><feDropShadow dx="0" dy="8" stdDeviation="10" flood-color="#001225" flood-opacity="0.28"/></filter>')
    add("</defs>")
    add('<rect width="1280" height="2600" fill="url(#bg)"/>')
    add('<path d="M0 110 C240 40 360 180 610 92 C850 10 1010 130 1280 55 L1280 0 L0 0 Z" fill="#08365a" opacity=".52"/>')
    y += 28
    add(text(width / 2, y + 48, "Wilson's Market News", 54, "#ffffff", "middle", 900))
    add(text(width / 2, y + 92, f"{snapshot['generated_at_display']} (UTC+8)", 22, "#e7f0fb", "middle", 500))
    add(text(width / 2, y + 124, "每4小时更新一次", 20, "#e7f0fb", "middle", 500))
    y += 146

    card_w = 294
    gap = 18
    x0 = 28
    top_cards = [
        ("🇺🇸", "美国", "US MARKET", "url(#usg)", "#ffffff"),
        ("🇨🇳", "中国", "CHINA MARKET", "url(#cng)", "#ffffff"),
        ("₿", "加密", "CRYPTO MARKET", "url(#crg)", "#0d6030"),
        ("R", "RWA", "REAL WORLD ASSETS", "url(#rwag)", "#ffffff"),
    ]
    for index, (icon, title, sub, fill, fg) in enumerate(top_cards):
        x = x0 + index * (card_w + gap)
        add(round_rect(x, y, card_w, 96, 8, fill, "#ffffff", 0.95, "shadow"))
        add(text(x + 58, y + 58, icon, 42, fg, "middle", 800))
        add(text(x + 108, y + 44, title, 34, fg, "start", 900))
        add(text(x + 110, y + 70, sub, 14, fg, "start", 700))
    y += 116

    y = render_heatmap_svg(add, snapshot.get("heatmap", []), 28, y, width - 56)
    y += 12
    y = render_us_svg(add, snapshot.get("us_market", {}), 28, y, width - 56)
    y += 14
    y = render_china_svg(add, snapshot.get("china_market", {}), 28, y, width - 56)
    y += 14
    y = render_crypto_svg(add, snapshot.get("crypto_market", {}), 28, y, width - 56)
    y += 14
    y = render_rwa_svg(add, snapshot.get("rwa_market", {}), 28, y, width - 56)
    y += 18
    add(round_rect(28, y, width - 56, 76, 8, "#052b4a", "#103b5b", 1))
    add(text(54, y + 33, "Wilson's View", 24, "#ffdc4a", "start", 900))
    for i, line in enumerate(wrap_text(snapshot.get("wilson_view", ""), 52)[:2]):
        add(text(230, y + 30 + i * 24, line, 20, "#ffffff", "start", 700))
    y += 106
    add(text(width / 2, y, "免责声明：本内容仅供参考，不构成任何投资建议。投资有风险，入市需谨慎。", 16, "#93a8ba", "middle", 400))
    add("</svg>")
    return "\n".join(parts).replace('height="2600"', f'height="{y + 30}"')


def render_heatmap_svg(add, tiles: list[dict[str, Any]], x: int, y: int, width: int) -> int:  # noqa: ANN001
    add(section_shell(x, y, width, 154, "#ffffff", "#b8d6ff"))
    add(text(x + 22, y + 34, "Market Heat Map", 26, "#0c2340", "start", 900))
    tile_w = (width - 44 - 7 * 10) / 8
    ty = y + 54
    for index, tile in enumerate(tiles[:8]):
        tx = x + 22 + index * (tile_w + 10)
        change = safe_float(tile.get("change_pct"))
        color = "#0fa463" if change >= 0 else "#e03131"
        bg = "#eaf8f0" if change >= 0 else "#fff0f0"
        add(round_rect(tx, ty, tile_w, 74, 6, bg, "#d6e2ef", 1))
        add(text(tx + 10, ty + 22, str(tile.get("label", "")), 15, "#3b4b5c", "start", 800))
        add(text(tx + 10, ty + 47, format_metric(tile.get("value")), 18, "#111827", "start", 900))
        add(text(tx + tile_w - 10, ty + 66, pct(tile.get("change_pct")), 15, color, "end", 800))
    return y + 154


def render_us_svg(add, market: dict[str, Any], x: int, y: int, width: int) -> int:  # noqa: ANN001
    section_h = 440
    add(section_shell(x, y, width, section_h, "#f8fbff", "#70b5ff"))
    add(header_band(x, y, width, "#1677f2", "🇺🇸  美国市场（S&P 500）"))
    add(info_box(add, x + 22, y + 72, 390, 118, "重大政策 / 政策动向", market.get("macro_policy", []), "#e8f3ff"))
    add(info_box(add, x + 432, y + 72, 390, 118, "市场讯息", market.get("market_overview", []), "#e8f3ff"))
    add(chart_box(add, x + 842, y + 72, 350, 118, (market.get("primary") or {}), "#168455"))
    add(table_box(add, x + 22, y + 208, 572, 180, "↗  领涨TOP 5", market.get("top_gainers", []), "#079455"))
    add(table_box(add, x + 614, y + 208, 578, 180, "↘  领跌TOP 5", market.get("top_losers", []), "#e03131"))
    add(text(x + 22, y + section_h - 16, trim("Sector: " + join_short(market.get("sector_rotation", []), 4) + "   ETF: " + join_short(market.get("etf_flow", []), 3), 118), 13, "#516274", "start", 500))
    return y + section_h


def render_china_svg(add, market: dict[str, Any], x: int, y: int, width: int) -> int:  # noqa: ANN001
    section_h = 440
    add(section_shell(x, y, width, section_h, "#fffafa", "#ff858a"))
    add(header_band(x, y, width, "#ef343b", "🇨🇳  中国市场（中证500）"))
    add(info_box(add, x + 22, y + 72, 390, 118, "重大政策 / 政策动向", market.get("policy_update", []), "#fff0f0"))
    add(info_box(add, x + 432, y + 72, 390, 118, "市场讯息", market.get("market_overview", []), "#fff0f0"))
    add(chart_box(add, x + 842, y + 72, 350, 118, (market.get("primary") or {}), "#e03131"))
    add(table_box(add, x + 22, y + 208, 572, 180, "↗  领涨TOP 5", market.get("top_gainers", []), "#079455"))
    add(table_box(add, x + 614, y + 208, 578, 180, "↘  领跌TOP 5", market.get("top_losers", []), "#e03131"))
    north = (market.get("northbound_capital_flow") or {}).get("text", "北向数据暂无")
    add(text(x + 22, y + section_h - 16, trim(str(north) + "   热门板块: " + join_short(market.get("hot_sectors", []), 4), 86), 13, "#674747", "start", 500))
    return y + section_h


def render_crypto_svg(add, market: dict[str, Any], x: int, y: int, width: int) -> int:  # noqa: ANN001
    section_h = 378
    add(section_shell(x, y, width, section_h, "#fffdf4", "#ffd95c"))
    add(header_band(x, y, width, "#f5b400", "₿  加密市场（Crypto Market）", "#0b3d2b"))
    stable = market.get("stablecoin_growth") or {}
    dex = market.get("dex_volume") or {}
    metric_cards = [
        ("总市值", first_line(market.get("market_overview", [])).split("，")[0]),
        ("BTC", coin_card_brief(market.get("btc"))),
        ("ETH", coin_card_brief(market.get("eth"))),
        ("稳定币", f"供给 {format_usd(stable.get('current'))}"),
        ("DEX", f"24h {format_usd(dex.get('total24h'))}"),
    ]
    card_w = (width - 44 - 4 * 10) / 5
    for index, (label, body) in enumerate(metric_cards):
        bx = x + 22 + index * (card_w + 10)
        add(round_rect(bx, y + 66, card_w, 78, 6, "#ffffff", "#f2d37a", 1))
        add(text(bx + 14, y + 91, label, 15, "#52606d", "start", 700))
        add(text(bx + 14, y + 120, trim(str(body), 22), 17, "#111827", "start", 900))
    add(table_box(add, x + 22, y + 164, 572, 178, "↗  Top100 领涨TOP 5", (market.get("top100_ranking") or {}).get("gainers", []), "#079455"))
    add(table_box(add, x + 614, y + 164, 578, 178, "↘  Top100 领跌TOP 5", (market.get("top100_ranking") or {}).get("losers", []), "#e03131"))
    add(text(x + 22, y + section_h - 16, trim("AI Agent: " + sector_brief(market.get("ai_agent_sector")) + "   Meme: " + sector_brief(market.get("meme_sector")) + "   Layer1: " + sector_brief(market.get("layer1_sector")), 122), 13, "#6d5922", "start", 500))
    return y + section_h


def render_rwa_svg(add, market: dict[str, Any], x: int, y: int, width: int) -> int:  # noqa: ANN001
    section_h = 348
    add(section_shell(x, y, width, section_h, "#f6fff9", "#75db9b"))
    add(header_band(x, y, width, "#169b62", "🟢  RWA市场（Real World Assets）"))
    cards = [
        ("TVL", f"{format_usd((market.get('tvl') or {}).get('value'))} {pct((market.get('tvl') or {}).get('change_1d'))}"),
        ("Market Cap", f"{format_usd((market.get('market_cap') or {}).get('value'))} {pct((market.get('market_cap') or {}).get('change_24h'))}"),
        ("Volume", format_usd((market.get("volume") or {}).get("value"))),
        ("Capital Flow", format_usd((market.get("capital_flow") or {}).get("value"))),
    ]
    card_w = (width - 44 - 3 * 12) / 4
    for index, (label, body) in enumerate(cards):
        bx = x + 22 + index * (card_w + 12)
        add(round_rect(bx, y + 68, card_w, 72, 6, "#ffffff", "#b8e8cd", 1))
        add(text(bx + 14, y + 94, label, 15, "#52606d", "start", 700))
        add(text(bx + 14, y + 120, trim(body, 24), 22, "#111827", "start", 900))
    projects = rwa_project_rows(market.get("top_projects"))
    add(table_box(add, x + 22, y + 160, 572, 154, "Top Projects", projects[:4], "#169b62"))
    add(info_box(add, x + 614, y + 160, 578, 154, "Major Events", market.get("major_events", []), "#ffffff"))
    return y + section_h


def section_shell(x: int, y: int, width: int, height: int, fill: str, stroke: str) -> str:
    return round_rect(x, y, width, height, 8, fill, stroke, 1, "shadow")


def header_band(x: int, y: int, width: int, color: str, label: str, fg: str = "#ffffff") -> str:
    return round_rect(x, y, width, 56, 8, color, color, 1) + text(x + 24, y + 36, label, 25, fg, "start", 900)


def info_box(add, x: float, y: float, w: float, h: float, title: str, lines: Any, fill: str) -> str:  # noqa: ANN001
    parts = [round_rect(x, y, w, h, 7, fill, "#e2e8f0", 1), text(x + 18, y + 28, title, 18, "#111827", "start", 900)]
    for idx, line in enumerate(as_list(lines)[:3]):
        parts.append(text(x + 20, y + 56 + idx * 24, "• " + trim(str(line), 36), 15, "#111827", "start", 500))
    return "".join(parts)


def chart_box(add, x: float, y: float, w: float, h: float, primary: dict[str, Any], line_color: str) -> str:  # noqa: ANN001
    label = primary.get("name") or primary.get("symbol") or primary.get("label") or "Index"
    price_value = format_metric(primary.get("price"))
    change = pct(primary.get("change_pct"))
    color = "#079455" if safe_float(primary.get("change_pct")) >= 0 else "#e03131"
    spark = primary.get("sparkline") or []
    parts = [round_rect(x, y, w, h, 7, "#ffffff", "#e2e8f0", 1)]
    parts.append(text(x + 18, y + 30, trim(str(label), 24), 17, "#111827", "start", 800))
    parts.append(text(x + 18, y + 58, price_value, 23, "#111827", "start", 900))
    parts.append(text(x + 18, y + 84, change, 17, color, "start", 800))
    if spark:
        parts.append(sparkline_path(spark, x + 150, y + 28, w - 175, h - 45, line_color))
    return "".join(parts)


def table_box(add, x: float, y: float, w: float, h: float, title: str, rows: Any, accent: str) -> str:  # noqa: ANN001
    rows_list = as_list(rows)
    parts = [round_rect(x, y, w, h, 7, "#ffffff", "#e2e8f0", 1)]
    parts.append(text(x + 16, y + 28, title, 18, accent, "start", 900))
    headers = ["代码", "名称", "涨跌幅", "价格/TVL"]
    col_x = [x + 18, x + 112, x + w - 198, x + w - 102]
    for i, header in enumerate(headers):
        parts.append(text(col_x[i], y + 58, header, 13, "#4b5563", "start", 800))
    for idx, row in enumerate(rows_list[:5]):
        ry = y + 84 + idx * 26
        symbol = row.get("symbol") or row.get("name") or "-"
        name = row.get("name") or row.get("symbol") or "-"
        change = row.get("change_pct")
        value = row.get("price")
        if value is None:
            value = row.get("tvl") or row.get("market_cap")
        change_color = "#079455" if safe_float(change) >= 0 else "#e03131"
        parts.append(text(x + 18, ry, str(idx + 1), 14, "#111827", "start", 500))
        parts.append(text(col_x[0] + 24, ry, trim(str(symbol), 7), 14, "#111827", "start", 600))
        parts.append(text(col_x[1], ry, trim(str(name), 18), 14, "#111827", "start", 500))
        parts.append(text(col_x[2], ry, pct(change), 14, change_color, "start", 800))
        parts.append(text(col_x[3], ry, trim(format_metric(value), 12), 14, "#111827", "start", 500))
    return "".join(parts)


def render_svg(snapshot: dict[str, Any]) -> str:
    width = 1280
    parts: list[str] = []
    add = parts.append
    add(f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="__HEIGHT__" viewBox="0 0 {width} __HEIGHT__">')
    add("<defs>")
    add('<linearGradient id="bg2" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#071c30"/><stop offset="1" stop-color="#02111f"/></linearGradient>')
    add('<linearGradient id="usg2" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#1689ff"/><stop offset="1" stop-color="#2448da"/></linearGradient>')
    add('<linearGradient id="cng2" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#ff4249"/><stop offset="1" stop-color="#c9141c"/></linearGradient>')
    add('<linearGradient id="cryptog2" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#ffdc28"/><stop offset="1" stop-color="#f5b400"/></linearGradient>')
    add('<linearGradient id="rwag2" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#24d27a"/><stop offset="1" stop-color="#0d8f57"/></linearGradient>')
    add('<linearGradient id="viewg2" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#102a72"/><stop offset=".55" stop-color="#073a62"/><stop offset="1" stop-color="#0d6142"/></linearGradient>')
    add('<filter id="softShadow2" x="-10%" y="-10%" width="120%" height="140%"><feDropShadow dx="0" dy="8" stdDeviation="9" flood-color="#001225" flood-opacity=".26"/></filter>')
    add("</defs>")
    add(f'<rect width="{width}" height="__HEIGHT__" fill="url(#bg2)"/>')
    add('<path d="M0 118 C230 45 380 168 604 92 C850 10 1010 132 1280 58 L1280 0 L0 0 Z" fill="#0b3a60" opacity=".48"/>')

    y = 30
    add(round_rect(36, y + 11, 94, 46, 10, "#ffffff", "#dce9f7", 0.96, "softShadow2"))
    add(text(83, y + 43, "WMN", 24, "#08213a", "middle", 900))
    add(text(width / 2, y + 42, "Wilson's Market News", 54, "#ffffff", "middle", 900))
    add(text(width / 2, y + 82, f"{snapshot['generated_at_display']} (UTC+8)  |  Every 4 Hours Update", 22, "#dce9f7", "middle", 700))
    add(text(width / 2, y + 116, "Wilson's Market News by Wilson", 20, "#ffe066", "middle", 800))
    y += 142
    y = draw_brand_cards(add, y, width)
    y += 16
    y = draw_heatmap_long(add, snapshot, 36, y, width - 72)
    y += 18
    y = draw_us_long(add, snapshot.get("us_market", {}), 36, y, width - 72)
    y += 20
    y = draw_china_long(add, snapshot.get("china_market", {}), 36, y, width - 72)
    y += 20
    y = draw_crypto_long(add, snapshot.get("crypto_market", {}), 36, y, width - 72)
    y += 20
    y = draw_rwa_long(add, snapshot.get("rwa_market", {}), 36, y, width - 72)
    y += 22

    view_lines = wrap_text(str(snapshot.get("wilson_view", "")), 52)
    view_h = 84 + len(view_lines) * 29
    add(round_rect(36, y, width - 72, view_h, 10, "url(#viewg2)", "#ffe066", 1, "softShadow2"))
    add(text(64, y + 42, "Wilson's View", 28, "#ffe066", "start", 900))
    for index, line in enumerate(view_lines):
        add(text(64, y + 76 + index * 29, line, 20, "#ffffff", "start", 850))
    y += view_h + 34
    add(text(width / 2, y, f"Disclaimer：{DISCLAIMER}", 16, "#94a9bb", "middle", 500))
    height = y + 34
    add("</svg>")
    return "\n".join(parts).replace("__HEIGHT__", str(height))


def render_svg_pages(snapshot: dict[str, Any]) -> list[dict[str, str]]:
    return [
        {"svg": "infographic_01_overview.svg", "png": "infographic_01_overview.png", "content": render_overview_page(snapshot)},
        {"svg": "infographic_02_us_china.svg", "png": "infographic_02_us_china.png", "content": render_us_china_page(snapshot)},
        {"svg": "infographic_03_crypto_rwa.svg", "png": "infographic_03_crypto_rwa.png", "content": render_crypto_rwa_page(snapshot)},
    ]


def page_svg_start(title: str, subtitle: str) -> tuple[list[str], Any, int]:
    width, height = 1080, 1350
    parts: list[str] = []
    add = parts.append
    add(f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">')
    add("<defs>")
    add('<linearGradient id="pagebg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#071c30"/><stop offset="1" stop-color="#02111f"/></linearGradient>')
    add('<linearGradient id="usg2" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#1689ff"/><stop offset="1" stop-color="#2448da"/></linearGradient>')
    add('<linearGradient id="cng2" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#ff4249"/><stop offset="1" stop-color="#c9141c"/></linearGradient>')
    add('<linearGradient id="cryptog2" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#ffdc28"/><stop offset="1" stop-color="#f5b400"/></linearGradient>')
    add('<linearGradient id="rwag2" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#24d27a"/><stop offset="1" stop-color="#0d8f57"/></linearGradient>')
    add('<linearGradient id="viewg2" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#102a72"/><stop offset=".55" stop-color="#073a62"/><stop offset="1" stop-color="#0d6142"/></linearGradient>')
    add('<filter id="softShadow2" x="-10%" y="-10%" width="120%" height="140%"><feDropShadow dx="0" dy="7" stdDeviation="7" flood-color="#001225" flood-opacity=".28"/></filter>')
    add("</defs>")
    add('<rect width="1080" height="1350" fill="url(#pagebg)"/>')
    add('<path d="M0 108 C210 40 340 150 532 86 C760 12 900 126 1080 54 L1080 0 L0 0 Z" fill="#0b3a60" opacity=".48"/>')
    add(round_rect(34, 28, 88, 44, 10, "#ffffff", "#dce9f7", 0.96, "softShadow2"))
    add(text(78, 58, "WMN", 23, "#08213a", "middle", 900))
    add(text(540, 48, "Wilson's Market News", 40, "#ffffff", "middle", 900))
    add(text(540, 84, subtitle, 22, "#dce9f7", "middle", 750))
    add(text(540, 116, title, 24, "#ffe066", "middle", 850))
    return parts, add, 150


def finish_page(parts: list[str]) -> str:
    parts.append(text(540, 1316, f"Disclaimer: {DISCLAIMER}", 15, "#98acbe", "middle", 500))
    parts.append("</svg>")
    return "\n".join(parts)


def render_overview_page(snapshot: dict[str, Any]) -> str:
    parts, add, y = page_svg_start("Market Heat Map + Wilson's View", f"{snapshot['generated_at_display']} UTC+8  |  Every 4 Hours Update")
    heatmap = [item for item in as_list(snapshot.get("heatmap")) if isinstance(item, dict)]
    styles = {
        "us": ("url(#usg2)", "#ffffff", "🇺🇸"),
        "china": ("url(#cng2)", "#ffe866", "🇨🇳"),
        "crypto": ("url(#cryptog2)", "#057a37", "₿"),
        "rwa": ("url(#rwag2)", "#ffffff", "R"),
    }
    add(round_rect(34, y, 1012, 510, 12, "#ffffff", "#bdd7f0", 1, "softShadow2"))
    add(text(62, y + 42, "Market Heat Map  市场温度", 34, "#0c2340", "start", 900))
    card_w, card_h = 478, 178
    for index, card in enumerate(heatmap[:4]):
        row, col = divmod(index, 2)
        x = 62 + col * (card_w + 28)
        ty = y + 72 + row * (card_h + 28)
        fill, fg, icon = styles.get(str(card.get("key")), ("#eef4fb", "#102033", "•"))
        add(round_rect(x, ty, card_w, card_h, 12, fill, "#dbe9f4", 1))
        add(text(x + 28, ty + 58, icon, 42, fg, "start", 900))
        add(text(x + 96, ty + 46, str(card.get("label", "")), 27, fg, "start", 900))
        if card.get("key") == "rwa":
            for line_index, line in enumerate(wrap_text(str(card.get("summary", "")), 24)[:3]):
                add(text(x + 96, ty + 86 + line_index * 28, line, 22, fg, "start", 800))
        else:
            add(text(x + 96, ty + 94, f"{card.get('score', 50)}/100", 40, fg, "start", 900))
            add(text(x + 96, ty + 132, str(card.get("status", "Neutral")), 24, fg, "start", 850))
    y += 540
    add(round_rect(34, y, 1012, 560, 12, "url(#viewg2)", "#ffe066", 1, "softShadow2"))
    add(text(62, y + 52, "Wilson's View", 36, "#ffe066", "start", 900))
    for index, line in enumerate(wrap_text(str(snapshot.get("wilson_view", "")), 35)[:8]):
        add(text(62, y + 104 + index * 42, line, 28, "#ffffff", "start", 850))
    return finish_page(parts)


def render_us_china_page(snapshot: dict[str, Any]) -> str:
    parts, add, y = page_svg_start("US Market + China Market", f"{snapshot['generated_at_display']} UTC+8  |  Every 4 Hours Update")
    us = snapshot.get("us_market", {})
    china = snapshot.get("china_market", {})
    y = draw_page_market(add, 34, y, 1012, 560, "🇺🇸  US Market", "url(#usg2)", "#ffffff", [
        ("Macro Policy", bullet_plain(us.get("macro_policy"), 2)),
        ("Market Overview", [
            f"S&P 500: {quote_text(find_quote(us.get('indices'), 'GSPC', 'S&P 500'))}",
            f"Nasdaq: {quote_text(find_quote(us.get('indices'), 'IXIC', 'Nasdaq'))}",
            f"Dow Jones: {quote_text(find_quote(us.get('indices'), 'DJI', 'Dow Jones'))}",
            f"VIX: {quote_text(find_quote(us.get('indices'), 'VIX', 'VIX'))}",
            f"DXY: {quote_text(find_quote(us.get('indices'), 'DX-Y.NYB', 'DXY'))}",
        ]),
        ("Top Gainers", ranking_compact(us.get("top_gainers"), 3)),
        ("Top Losers", ranking_compact(us.get("top_losers"), 3)),
    ])
    y += 28
    china_items = [
        ("Policy Update", bullet_plain(china.get("policy_update"), 2)),
        ("Market Overview", [
            f"中证500: {quote_text(find_quote(china.get('indices'), '000905', '中证500'))}",
            f"沪深300: {quote_text(find_quote(china.get('indices'), '000300', '沪深300'))}",
            f"创业板: {quote_text(find_quote(china.get('indices'), '399006', '创业板指'))}",
            f"人民币汇率: {quote_text(china.get('fx'), currency='')}",
        ]),
        ("Top Gainers", ranking_compact(china.get("top_gainers"), 3)),
        ("Top Losers", ranking_compact(china.get("top_losers"), 3)),
    ]
    if china_data_unavailable(china):
        china_items = [("数据状态", ["中股行情源暂未返回有效数据", "待接入：中证500、沪深300、创业板、人民币汇率、涨跌TOP5"])]
    draw_page_market(add, 34, y, 1012, 560, "🇨🇳  China Market", "url(#cng2)", "#ffe866", china_items)
    return finish_page(parts)


def render_crypto_rwa_page(snapshot: dict[str, Any]) -> str:
    parts, add, y = page_svg_start("Crypto Market + RWA Market", f"{snapshot['generated_at_display']} UTC+8  |  Every 4 Hours Update")
    crypto = snapshot.get("crypto_market", {})
    rwa = snapshot.get("rwa_market", {})
    metrics = crypto.get("global_metrics") or {}
    stable = crypto.get("stablecoin_growth") or {}
    cex = crypto.get("cex_volume") or {}
    dex = crypto.get("dex_volume") or {}
    y = draw_page_market(add, 34, y, 1012, 620, "₿  Crypto Market", "url(#cryptog2)", "#057a37", [
        ("Market Overview", [
            f"Total Market Cap: {format_usd(metrics.get('market_cap'))}",
            f"24h Volume: {format_usd(metrics.get('volume_24h'))}",
            f"BTC: {coin_brief(crypto.get('btc'))}",
            f"ETH: {coin_brief(crypto.get('eth'))}",
            f"BTC Dominance: {format_percent_value(metrics.get('btc_dominance'))}",
            f"Fear & Greed: {fear_greed_text(crypto.get('fear_greed'))}",
        ]),
        ("Stablecoin / CEX / DEX", [
            f"Stablecoin: {format_usd(stable.get('current'))}, 24h {pct(stable.get('change_1d'))}, 7d {pct(stable.get('change_7d'))}",
            f"CEX 24h: {format_usd(cex.get('total24h'))}",
            f"DEX 24h: {format_usd(dex.get('total24h'))}, {pct(dex.get('change_1d'))}",
        ]),
        ("Top100 Gainers", ranking_compact((crypto.get("top100_ranking") or {}).get("gainers"), 3)),
        ("Top100 Losers", ranking_compact((crypto.get("top100_ranking") or {}).get("losers"), 3)),
    ])
    y += 28
    draw_page_market(add, 34, y, 1012, 480, "🟢  RWA Market", "url(#rwag2)", "#ffffff", [
        ("Core Data", [
            f"TVL: {format_usd((rwa.get('tvl') or {}).get('value'))} / {pct((rwa.get('tvl') or {}).get('change_1d'))}",
            f"Market Cap: {format_usd((rwa.get('market_cap') or {}).get('value'))} / {pct((rwa.get('market_cap') or {}).get('change_24h'))}",
            f"Volume: {format_usd((rwa.get('volume') or {}).get('value'))}",
            f"Capital Flow: {format_usd((rwa.get('capital_flow') or {}).get('value'))}",
        ]),
        ("Top Projects", ranking_compact(rwa_project_rows(rwa.get("top_projects")), 4, label="name")),
        ("Major Events", bullet_plain(rwa.get("major_events"), 2)),
    ])
    return finish_page(parts)


def draw_page_market(add, x: int, y: int, w: int, h: int, title: str, header_fill: str, header_fg: str, sections: list[tuple[str, list[str]]]) -> int:  # noqa: ANN001
    add(round_rect(x, y, w, h, 12, "#f8fbff", "#cfe2f3", 1, "softShadow2"))
    add(round_rect(x, y, w, 62, 12, header_fill, header_fill, 1))
    add(text(x + 26, y + 42, title, 32, header_fg, "start", 900))
    cy = y + 96
    for section_title, lines in sections:
        add(text(x + 28, cy, section_title, 25, "#12263a", "start", 900))
        add(f'<line x1="{x + 28}" y1="{cy + 12}" x2="{x + w - 28}" y2="{cy + 12}" stroke="#c7d9ea" stroke-width="2"/>')
        cy += 44
        for item in lines[:6]:
            for index, line in enumerate(wrap_text(str(item), 39)[:2]):
                prefix = "• " if index == 0 else "  "
                add(text(x + 36, cy, prefix + line, 22, "#142033", "start", 700))
                cy += 31
        cy += 18
        if cy > y + h - 28:
            break
    return y + h

def draw_brand_cards(add, y: int, width: int) -> int:  # noqa: ANN001
    card_w = 286
    gap = 18
    x0 = (width - card_w * 4 - gap * 3) / 2
    cards = [
        {"icon": "🇺🇸", "title": "美国", "sub": "US MARKET", "fill": "url(#usg2)", "fg": "#ffffff", "kind": "normal"},
        {"icon": "🇨🇳", "title": "中国", "sub": "CHINA MARKET", "fill": "url(#cng2)", "fg": "#ffe866", "kind": "normal"},
        {"icon": "₿", "title": "加密", "sub": "CRYPTO MARKET", "fill": "url(#cryptog2)", "fg": "#057a37", "kind": "normal"},
        {"icon": "R", "title": "RWA", "sub": "REAL WORLD ASSETS", "fill": "url(#rwag2)", "fg": "#ffffff", "kind": "normal"},
    ]
    for index, card in enumerate(cards):
        x = x0 + index * (card_w + gap)
        add(round_rect(x, y, card_w, 104, 8, card["fill"], "#ffffff", 0.96, "softShadow2"))
        add(text(x + 58, y + 64, card["icon"], 42, card["fg"], "middle", 900))
        add(text(x + 110, y + 46, card["title"], 34, card["fg"], "start", 900))
        add(text(x + 112, y + 76, card["sub"], 14, card["fg"], "start", 800))
    return y + 104


def draw_heatmap_long(add, snapshot: dict[str, Any], x: int, y: int, width: int) -> int:  # noqa: ANN001
    tiles = [item for item in as_list(snapshot.get("heatmap")) if isinstance(item, dict)]
    tile_w = (width - 44 - 3 * 14) / 4
    tile_h = 120
    section_h = 58 + tile_h + 24
    add(round_rect(x, y, width, section_h, 8, "#ffffff", "#b9d6f4", 1, "softShadow2"))
    add(text(x + 24, y + 36, "Market Heat Map  市场温度", 28, "#0c2340", "start", 900))
    styles = {
        "us": ("url(#usg2)", "#ffffff", "🇺🇸"),
        "china": ("url(#cng2)", "#ffe866", "🇨🇳"),
        "crypto": ("url(#cryptog2)", "#057a37", "₿"),
        "rwa": ("url(#rwag2)", "#ffffff", "R"),
    }
    for index, tile in enumerate(tiles[:4]):
        tx = x + 22 + index * (tile_w + 14)
        ty = y + 58
        fill, fg, icon = styles.get(str(tile.get("key")), ("#eef4fb", "#102033", "•"))
        add(round_rect(tx, ty, tile_w, tile_h, 8, fill, "#d9e7f2", 1))
        add(text(tx + 22, ty + 38, icon, 34, fg, "start", 900))
        add(text(tx + 78, ty + 32, str(tile.get("label", "")), 22, fg, "start", 900))
        if tile.get("key") == "rwa":
            for line_index, line in enumerate(wrap_text(str(tile.get("summary", "")), 18)[:2]):
                add(text(tx + 78, ty + 64 + line_index * 23, line, 17, fg, "start", 800))
        else:
            add(text(tx + 78, ty + 68, f"{tile.get('score', 50)}/100", 34, fg, "start", 900))
            add(text(tx + 78, ty + 96, str(tile.get("status", "Neutral")), 18, fg, "start", 800))
    return y + section_h


def draw_section_frame(add, x: int, y: int, width: int, height: int, fill: str, stroke: str, color: str, title: str, fg: str = "#ffffff") -> None:  # noqa: ANN001
    add(round_rect(x, y, width, height, 8, fill, stroke, 1, "softShadow2"))
    add(round_rect(x, y, width, 62, 8, color, color, 1))
    add(text(x + 24, y + 40, title, 28, fg, "start", 900))


def draw_us_long(add, market: dict[str, Any], x: int, y: int, width: int) -> int:  # noqa: ANN001
    local: list[str] = []
    ladd = local.append
    cy = y + 80
    cy = draw_full_card(ladd, x + 22, cy, width - 44, "重大政策 / 政策动向（中文）", market.get("macro_policy", []), "#1677f2", "#eef6ff")
    cy += 12
    col_w = (width - 58) / 2
    left_y = draw_full_card(ladd, x + 22, cy, col_w, "市场概览", market.get("market_overview", []), "#1677f2", "#ffffff")
    right_y = draw_full_card(ladd, x + 36 + col_w, cy, col_w, "板块轮动", market.get("sector_rotation", []), "#1677f2", "#ffffff")
    cy = max(left_y, right_y) + 12
    left_y = draw_full_card(ladd, x + 22, cy, col_w, "ETF Flow（成交额代理）", market.get("etf_flow", []), "#1677f2", "#ffffff")
    right_y = draw_full_card(ladd, x + 36 + col_w, cy, col_w, "AI Sector", market.get("ai_sector", []), "#1677f2", "#ffffff")
    cy = max(left_y, right_y) + 12
    left_y = draw_ranking_card(ladd, x + 22, cy, col_w, "领涨 TOP 5", market.get("top_gainers", []), "#079455")
    right_y = draw_ranking_card(ladd, x + 36 + col_w, cy, col_w, "领跌 TOP 5", market.get("top_losers", []), "#e03131")
    cy = max(left_y, right_y) + 22
    draw_section_frame(add, x, y, width, cy - y, "#f8fbff", "#72b7ff", "#1677f2", "🇺🇸  美国市场（S&P 500）")
    for item in local:
        add(item)
    return cy


def draw_china_long(add, market: dict[str, Any], x: int, y: int, width: int) -> int:  # noqa: ANN001
    local: list[str] = []
    ladd = local.append
    cy = y + 80
    cy = draw_full_card(ladd, x + 22, cy, width - 44, "政策更新（中文）", market.get("policy_update", []), "#ef343b", "#fff2f2")
    cy += 12
    col_w = (width - 58) / 2
    left_y = draw_full_card(ladd, x + 22, cy, col_w, "市场概览", market.get("market_overview", []), "#ef343b", "#ffffff")
    north = (market.get("northbound_capital_flow") or {}).get("text", "暂无数据")
    right_y = draw_full_card(ladd, x + 36 + col_w, cy, col_w, "北向资金", [north], "#ef343b", "#ffffff")
    cy = max(left_y, right_y) + 12
    left_y = draw_full_card(ladd, x + 22, cy, col_w, "热门板块", market.get("hot_sectors", []), "#ef343b", "#ffffff")
    right_y = draw_full_card(ladd, x + 36 + col_w, cy, col_w, "核心资产", market.get("core_assets", []), "#ef343b", "#ffffff")
    cy = max(left_y, right_y) + 12
    left_y = draw_ranking_card(ladd, x + 22, cy, col_w, "领涨 TOP 5", market.get("top_gainers", []), "#079455")
    right_y = draw_ranking_card(ladd, x + 36 + col_w, cy, col_w, "领跌 TOP 5", market.get("top_losers", []), "#e03131")
    cy = max(left_y, right_y) + 22
    draw_section_frame(add, x, y, width, cy - y, "#fffafa", "#ff8d91", "#ef343b", "🇨🇳  中国市场（中证500）")
    for item in local:
        add(item)
    return cy


def draw_crypto_long(add, market: dict[str, Any], x: int, y: int, width: int) -> int:  # noqa: ANN001
    local: list[str] = []
    ladd = local.append
    cy = y + 80
    stable = market.get("stablecoin_growth") or {}
    cex = market.get("cex_volume") or {}
    dex = market.get("dex_volume") or {}
    metrics_data = market.get("global_metrics") or {}
    fear = market.get("fear_greed") or {}
    metrics = [
        ("Total Market Cap", format_usd(metrics_data.get("market_cap"))),
        ("BTC Price", coin_card_brief(market.get("btc"))),
        ("ETH Price", coin_card_brief(market.get("eth"))),
        ("BTC Dominance", format_percent_value(metrics_data.get("btc_dominance"))),
        ("Fear & Greed", fear_greed_text(fear)),
    ]
    cy = draw_metric_grid(ladd, x + 22, cy, width - 44, metrics, "#f5b400", columns=5)
    cy += 12
    col_w = (width - 58) / 2
    left_y = draw_full_card(ladd, x + 22, cy, col_w, "市场概览", market.get("market_overview", []), "#f5b400", "#ffffff")
    right_y = draw_full_card(ladd, x + 36 + col_w, cy, col_w, "BTC / ETH", [coin_brief(market.get("btc")), coin_brief(market.get("eth"))], "#f5b400", "#ffffff")
    cy = max(left_y, right_y) + 12
    left_y = draw_full_card(ladd, x + 22, cy, col_w, "ETF Flow（成交额代理）", market.get("etf_flow", []), "#f5b400", "#ffffff")
    right_y = draw_full_card(ladd, x + 36 + col_w, cy, col_w, "稳定币 / CEX / DEX", [stable.get("text", "暂无数据"), cex.get("text", "暂无数据"), dex.get("text", "暂无数据")], "#f5b400", "#ffffff")
    cy = max(left_y, right_y) + 12
    third_w = (width - 68) / 3
    a_y = draw_full_card(ladd, x + 22, cy, third_w, "AI Agent Sector", [sector_plain(market.get("ai_agent_sector"))], "#f5b400", "#ffffff")
    b_y = draw_full_card(ladd, x + 34 + third_w, cy, third_w, "Meme Sector", [sector_plain(market.get("meme_sector"))], "#f5b400", "#ffffff")
    c_y = draw_full_card(ladd, x + 46 + third_w * 2, cy, third_w, "Layer1 Sector", [sector_plain(market.get("layer1_sector"))], "#f5b400", "#ffffff")
    cy = max(a_y, b_y, c_y) + 12
    left_y = draw_ranking_card(ladd, x + 22, cy, col_w, "Top100 领涨 TOP 5", (market.get("top100_ranking") or {}).get("gainers"), "#079455")
    right_y = draw_ranking_card(ladd, x + 36 + col_w, cy, col_w, "Top100 领跌 TOP 5", (market.get("top100_ranking") or {}).get("losers"), "#e03131")
    cy = max(left_y, right_y) + 22
    draw_section_frame(add, x, y, width, cy - y, "#fffdf2", "#ffd95c", "#f5b400", "₿  加密市场（Crypto Market）", "#111827")
    for item in local:
        add(item)
    return cy


def draw_rwa_long(add, market: dict[str, Any], x: int, y: int, width: int) -> int:  # noqa: ANN001
    local: list[str] = []
    ladd = local.append
    cy = y + 80
    metrics = [
        ("TVL", f"{format_usd((market.get('tvl') or {}).get('value'))} / {pct((market.get('tvl') or {}).get('change_1d'))}"),
        ("Market Cap", f"{format_usd((market.get('market_cap') or {}).get('value'))} / {pct((market.get('market_cap') or {}).get('change_24h'))}"),
        ("Volume", format_usd((market.get("volume") or {}).get("value"))),
        ("Capital Flow", format_usd((market.get("capital_flow") or {}).get("value"))),
    ]
    cy = draw_metric_grid(ladd, x + 22, cy, width - 44, metrics, "#169b62", columns=4)
    cy += 12
    col_w = (width - 58) / 2
    left_y = draw_ranking_card(ladd, x + 22, cy, col_w, "Top Projects", rwa_project_rows(market.get("top_projects")), "#169b62")
    right_y = draw_full_card(ladd, x + 36 + col_w, cy, col_w, "Major Events（中文）", market.get("major_events", []), "#169b62", "#ffffff")
    cy = max(left_y, right_y) + 22
    draw_section_frame(add, x, y, width, cy - y, "#f6fff9", "#75db9b", "#169b62", "🟢  RWA市场（Real World Assets）")
    for item in local:
        add(item)
    return cy


def draw_full_card(add, x: float, y: float, w: float, title: str, items: Any, accent: str, fill: str) -> int:  # noqa: ANN001
    values = [str(item) for item in as_list(items) if str(item).strip()]
    if not values:
        values = ["暂无数据"]
    max_chars = max(18, int((w - 48) / 17))
    prepared: list[tuple[str, bool]] = []
    for value in values:
        lines = wrap_text(value, max_chars)
        for index, line in enumerate(lines):
            prepared.append((line, index == 0))
        prepared.append(("", False))
    if prepared and prepared[-1][0] == "":
        prepared.pop()
    body_line_h = 24
    height = max(96, 58 + len(prepared) * body_line_h + 20)
    add(round_rect(x, y, w, height, 8, fill, "#dfe7ef", 1))
    add(text(x + 18, y + 31, title, 18, "#111827", "start", 900))
    add(f'<line x1="{x + 18:.1f}" y1="{y + 43:.1f}" x2="{x + w - 18:.1f}" y2="{y + 43:.1f}" stroke="{accent}" stroke-opacity=".36" stroke-width="2"/>')
    cy = y + 68
    for line, first in prepared:
        if not line:
            cy += 7
            continue
        prefix = "• " if first else "  "
        add(text(x + 22, cy, prefix + line, 17, "#17202a", "start", 600))
        cy += body_line_h
    return int(y + height)


def draw_ranking_card(add, x: float, y: float, w: float, title: str, rows: Any, accent: str) -> int:  # noqa: ANN001
    lines = []
    for index, row in enumerate(as_list(rows)[:5], 1):
        if isinstance(row, dict):
            symbol = row.get("symbol") or row.get("chain") or "-"
            name = row.get("name") or row.get("symbol") or "-"
            value = row.get("price") if row.get("price") is not None else row.get("tvl") or row.get("market_cap")
            lines.append(f"{index}. {symbol} {name}｜{pct(row.get('change_pct'))}｜{format_metric(value)}")
        else:
            lines.append(f"{index}. {row}")
    return draw_full_card(add, x, y, w, title, lines or ["暂无数据"], accent, "#ffffff")


def draw_metric_grid(add, x: float, y: float, w: float, metrics: list[tuple[str, str]], accent: str, columns: int) -> int:  # noqa: ANN001
    gap = 12
    card_w = (w - gap * (columns - 1)) / columns
    card_h = 88
    for index, (label, value) in enumerate(metrics):
        tx = x + index * (card_w + gap)
        add(round_rect(tx, y, card_w, card_h, 8, "#ffffff", "#dfe7ef", 1))
        add(text(tx + 14, y + 28, label, 15, "#52606d", "start", 800))
        for line_index, line in enumerate(wrap_text(str(value), max(12, int((card_w - 24) / 15)))[:2]):
            add(text(tx + 14, y + 58 + line_index * 22, line, 18, "#111827", "start", 900))
        add(f'<line x1="{tx + 14:.1f}" y1="{y + card_h - 10:.1f}" x2="{tx + card_w - 14:.1f}" y2="{y + card_h - 10:.1f}" stroke="{accent}" stroke-width="3" stroke-linecap="round"/>')
    return int(y + card_h)


def quote_line(quote: Quote, currency: str = "$") -> str:
    return f"{quote.name} {format_price(quote.price, currency if quote.currency != 'CNY' else '¥')} ({pct(quote.change_pct)})"


def etf_proxy_line(quote: Quote) -> str:
    return f"{quote.symbol} {pct(quote.change_pct)}，成交额约 {format_usd(quote.value_traded)}"


def board_line(item: dict[str, Any]) -> str:
    return f"{item.get('name')} {pct(item.get('change_pct'))}，龙头 {item.get('leader')} {pct(item.get('leader_change_pct'))}"


def quote_row(quote: Quote, currency: str = "$") -> dict[str, Any]:
    return {"symbol": quote.symbol, "name": quote.name, "change_pct": quote.change_pct, "price": quote.price, "reason": movement_reason(quote)}


def coin_row(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "symbol": str(item.get("symbol", "")).upper(),
        "name": item.get("name"),
        "change_pct": item.get("price_change_percentage_24h"),
        "price": item.get("current_price"),
        "market_cap": item.get("market_cap"),
    }


def rwa_project_rows(projects: Any) -> list[dict[str, Any]]:  # noqa: ANN401
    rows = []
    for item in as_list(projects):
        rows.append({"symbol": "RWA", "name": item.get("name"), "change_pct": item.get("change_1d"), "price": item.get("tvl"), "tvl": item.get("tvl")})
    return rows


def coin_summary(item: dict[str, Any] | None) -> dict[str, Any]:
    if not item:
        return {}
    return {
        "symbol": str(item.get("symbol", "")).upper(),
        "name": item.get("name"),
        "price": item.get("current_price"),
        "change_pct": item.get("price_change_percentage_24h"),
        "market_cap": item.get("market_cap"),
        "volume": item.get("total_volume"),
    }


def coin_quote_dict(item: dict[str, Any] | None) -> dict[str, Any]:
    summary = coin_summary(item)
    summary["label"] = summary.get("symbol")
    return summary


def quote_to_dict(quote: Quote | None) -> dict[str, Any]:
    if quote is None:
        return {}
    return {
        "symbol": quote.symbol,
        "name": quote.name,
        "price": quote.price,
        "change_pct": quote.change_pct,
        "change": quote.change,
        "volume": quote.volume,
        "value_traded": quote.value_traded,
        "currency": quote.currency,
        "sparkline": quote.sparkline or [],
    }


def sector_snapshot(name: str, top100: list[dict[str, Any]], categories: dict[str, dict[str, Any]], category_id: str, symbols: set[str]) -> dict[str, Any]:
    category = categories.get(category_id, {})
    coins = [coin for coin in top100 if str(coin.get("symbol", "")).upper() in symbols]
    coins.sort(key=lambda item: safe_float(item.get("price_change_percentage_24h")), reverse=True)
    return {
        "name": name,
        "market_cap": category.get("market_cap"),
        "change_24h": category.get("market_cap_change_24h"),
        "volume_24h": category.get("volume_24h"),
        "top": [coin_row(item) for item in coins[:5]],
    }


def crypto_global_metrics(global_data: dict[str, Any], defi_data: dict[str, Any]) -> dict[str, Any]:
    data = global_data.get("data", {}) if isinstance(global_data, dict) else {}
    return {
        "market_cap": first_number((data.get("total_market_cap") or {}).get("usd")),
        "volume_24h": first_number((data.get("total_volume") or {}).get("usd")),
        "btc_dominance": first_number((data.get("market_cap_percentage") or {}).get("btc")),
        "defi_market_cap": first_number((defi_data.get("data", {}) if isinstance(defi_data, dict) else {}).get("defi_market_cap")),
    }


def crypto_overview_from_metrics(metrics: dict[str, Any]) -> list[str]:
    return [
        f"总市值 {format_usd(metrics.get('market_cap'))}，24h 成交 {format_usd(metrics.get('volume_24h'))}",
        f"BTC 占比 {format_percent_value(metrics.get('btc_dominance'))}，DeFi 市值 {format_usd(metrics.get('defi_market_cap'))}",
    ]


def crypto_overview(global_data: dict[str, Any], defi_data: dict[str, Any]) -> list[str]:
    return crypto_overview_from_metrics(crypto_global_metrics(global_data, defi_data))


def news_lines(items: list[dict[str, Any]], keywords: tuple[str, ...], limit: int) -> list[str]:
    scored = []
    for item in items:
        text_value = str(item.get("text", "")).lower()
        hits = sum(1 for keyword in keywords if keyword.lower() in text_value)
        score = hits + safe_float(item.get("weight")) if hits else 0
        scored.append((score, item))
    scored.sort(key=lambda entry: (entry[0], entry[1].get("published_at") or datetime.now(timezone.utc)), reverse=True)
    lines = [translate_for_display(str(item.get("title", ""))) for score, item in scored if score > 0][:limit]
    if not lines:
        lines = [translate_for_display(str(item.get("title", ""))) for item in items[:limit]]
    return lines or ["暂无高优先级资讯，等待下一轮抓取。"]


def translate_for_display(value: str) -> str:
    text_value = re.sub(r"\s+", " ", value or "").strip()
    if not text_value or has_cjk(text_value):
        return text_value
    cache = RUN_CACHE.setdefault("translations", {})
    if text_value in cache:
        return cache[text_value]
    translated = ""
    if os.getenv("WILSON_TRANSLATE_NEWS", "1") != "0":
        translated = try_google_translate(text_value)
    if not translated:
        translated = localize_english_headline(text_value)
    cache[text_value] = translated
    return translated


def try_google_translate(value: str) -> str:
    url = "https://translate.googleapis.com/translate_a/single?" + urllib.parse.urlencode(
        {"client": "gtx", "sl": "auto", "tl": "zh-CN", "dt": "t", "q": value}
    )
    data = safe_call(lambda: http_json(url, timeout=8), None)
    try:
        translated = "".join(part[0] for part in data[0] if part and part[0])
    except Exception:
        return ""
    translated = re.sub(r"\s+", " ", translated).strip()
    return translated if has_cjk(translated) else ""


def localize_english_headline(value: str) -> str:
    replacements = [
        ("US Stock Market Today", "美国股市今日"),
        ("Stock Market Today", "股市今日"),
        ("S&P 500 Futures", "标普500期货"),
        ("S&P 500", "标普500"),
        ("Nasdaq", "纳斯达克"),
        ("Dow Jones", "道琼斯"),
        ("Fed Chair", "美联储主席"),
        ("Federal Reserve", "美联储"),
        ("Fed", "美联储"),
        ("FOMC", "FOMC会议"),
        ("PCE Inflation Data", "PCE通胀数据"),
        ("Inflation Data", "通胀数据"),
        ("rate cut", "降息"),
        ("rate cuts", "降息"),
        ("traders eye", "交易员关注"),
        ("futures ease", "期货走低"),
        ("trade talks", "贸易谈判"),
        ("rare earth", "稀土"),
        ("Pentagon", "五角大楼"),
        ("security", "安全"),
        ("withdraw", "撤出"),
        ("launches", "推出"),
        ("launch", "推出"),
        ("tokenized equity", "代币化股票"),
        ("funding rate", "资金费率"),
        ("hits", "触及"),
        ("next", "下一目标"),
    ]
    output = value
    for source, target in replacements:
        output = re.sub(re.escape(source), target, output, flags=re.I)
    if output == value:
        return f"海外资讯：{value}"
    return output


def has_cjk(value: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", value or ""))


def movement_reason(quote: Quote) -> str:
    change = safe_float(quote.change_pct)
    if abs(change) >= 5:
        return "价格异动明显，需结合公告、成交量与板块消息确认。"
    if quote.value_traded and quote.value_traded > 5_000_000_000:
        return "成交额较高，资金关注度上升。"
    return "相对标的池表现突出，作为短线强弱信号观察。"


def http_json(url: str, timeout: int = TIMEOUT, referer: str | None = None) -> Any:
    return json.loads(http_bytes(url, timeout=timeout, referer=referer).decode("utf-8", "ignore"))


def http_bytes(url: str, timeout: int = TIMEOUT, referer: str | None = None) -> bytes:
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json,text/xml,application/xml,text/html,*/*"}
    if referer:
        headers["Referer"] = referer
    request = urllib.request.Request(url, headers=headers)
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            last_error = exc
            if exc.code == 429 and attempt < 2:
                time.sleep(1.5 * (attempt + 1))
                continue
            raise
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if attempt < 2:
                time.sleep(0.5 * (attempt + 1))
                continue
            raise
    raise last_error or RuntimeError(f"failed to fetch {url}")


def push_to_telegram(markdown: str, image_paths: list[Path], output_dir: Path) -> dict[str, Any]:
    log_path = output_dir / TELEGRAM_LOG_NAME
    status: dict[str, Any] = {
        "enabled": True,
        "documents": [],
        "message": {"ok": False, "message_ids": []},
        "errors": [],
        "log_path": str(log_path),
    }

    for image_path in image_paths:
        try:
            document_response = telegram_service_send_document(image_path)
            message_id = telegram_message_id(document_response)
            result = {"ok": True, "path": str(image_path), "message_id": message_id}
            status["documents"].append(result)
            append_telegram_log(log_path, {"event": "sendDocument", **result})
        except Exception as exc:  # noqa: BLE001
            error = str(exc)
            result = {"ok": False, "path": str(image_path), "message_id": None, "error": error}
            status["documents"].append(result)
            status["errors"].append(f"sendDocument {image_path.name}: {error}")
            append_telegram_log(log_path, {"event": "sendDocument", **result})

    for index, chunk in enumerate(split_message(markdown), 1):
        try:
            message_response = telegram_service_send_message(chunk)
            message_id = telegram_message_id(message_response)
            status["message"]["message_ids"].append(message_id)
            append_telegram_log(log_path, {"event": "sendMessage", "ok": True, "chunk": index, "message_id": message_id})
        except Exception as exc:  # noqa: BLE001
            error = str(exc)
            status["errors"].append(f"sendMessage chunk {index}: {error}")
            append_telegram_log(log_path, {"event": "sendMessage", "ok": False, "chunk": index, "error": error})
    status["message"]["ok"] = bool(status["message"]["message_ids"])
    return status


def telegram_message_id(response: dict[str, Any]) -> int | None:
    result = response.get("result") if isinstance(response, dict) else None
    if isinstance(result, dict):
        value = result.get("message_id")
        try:
            return int(value)
        except (TypeError, ValueError):
            return None
    return None


def append_telegram_log(log_path: Path, payload: dict[str, Any]) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    entry = {"time": datetime.now(timezone.utc).isoformat(), **payload}
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


def multipart_form_data(fields: dict[str, str], files: dict[str, Path]) -> tuple[bytes, str]:
    boundary = f"----WilsonBoundary{int(time.time() * 1000)}"
    chunks: list[bytes] = []
    for name, value in fields.items():
        chunks.extend(
            [
                f"--{boundary}\r\n".encode(),
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode(),
                str(value).encode("utf-8"),
                b"\r\n",
            ]
        )
    for name, path in files.items():
        chunks.extend(
            [
                f"--{boundary}\r\n".encode(),
                f'Content-Disposition: form-data; name="{name}"; filename="{path.name}"\r\n'.encode(),
                b"Content-Type: image/png\r\n\r\n",
                path.read_bytes(),
                b"\r\n",
            ]
        )
    chunks.append(f"--{boundary}--\r\n".encode())
    return b"".join(chunks), f"multipart/form-data; boundary={boundary}"


def prepare_output_dirs(output_dir: Path, generated_at: datetime) -> tuple[Path, Path]:
    latest_dir = output_dir / "latest"
    iso_year, iso_week, _ = generated_at.isocalendar()
    archive_dir = (
        output_dir
        / "archive"
        / generated_at.strftime("%Y")
        / generated_at.strftime("%Y-%m")
        / f"{iso_year}-W{iso_week:02d}"
        / generated_at.strftime("%Y-%m-%d")
        / generated_at.strftime("%H00")
    )
    latest_dir.mkdir(parents=True, exist_ok=True)
    archive_dir.mkdir(parents=True, exist_ok=True)
    return latest_dir, archive_dir


def organize_archive_run(archive_dir: Path) -> None:
    folders = {
        "00_raw_data": ["snapshot.json"],
        "01_market_heat_map": ["infographic_01_overview.png", "infographic_01_overview.svg"],
        "02_us_china_market": ["infographic_02_us_china.png", "infographic_02_us_china.svg"],
        "03_crypto_rwa_market": ["infographic_03_crypto_rwa.png", "infographic_03_crypto_rwa.svg"],
        "04_telegram_summary": ["telegram.md"],
        "05_status_logs": ["status.json"],
        "99_legacy_preview": ["infographic.png", "infographic.svg"],
    }
    for folder, filenames in folders.items():
        target_dir = archive_dir / folder
        target_dir.mkdir(parents=True, exist_ok=True)
        for filename in filenames:
            source = archive_dir / filename
            if source.exists():
                target = target_dir / filename
                target.write_bytes(source.read_bytes())
                source.unlink()


def convert_html_to_pdf(html_path: Path, pdf_path: Path) -> str | None:
    if not CHROME_PATH.exists():
        return "Google Chrome.app not found; report.html was generated without PDF."
    pdf_path.unlink(missing_ok=True)
    profile_dir = html_path.parent / ".chrome-profile"
    command = [
        str(CHROME_PATH),
        "--headless",
        "--disable-gpu",
        "--disable-extensions",
        "--no-first-run",
        "--no-default-browser-check",
        f"--user-data-dir={profile_dir}",
        f"--print-to-pdf={pdf_path}",
        f"file://{html_path.resolve()}",
    ]
    try:
        process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        deadline = time.time() + 20
        while time.time() < deadline:
            if pdf_path.exists() and pdf_path.stat().st_size > 1024:
                process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
                return None
            if process.poll() is not None:
                break
            time.sleep(0.5)
        if pdf_path.exists() and pdf_path.stat().st_size > 1024:
            return None
        if process.poll() is None:
            process.kill()
            return "Chrome PDF conversion timed out before report.pdf was written."
        stderr = process.stderr.read().decode("utf-8", "ignore") if process.stderr else ""
        if process.returncode:
            return stderr.strip()[:500] or "Chrome PDF conversion failed."
    except subprocess.CalledProcessError as exc:
        return exc.stderr.decode("utf-8", "ignore").strip()[:500] or "Chrome PDF conversion failed."
    except Exception as exc:  # noqa: BLE001
        return str(exc)
    return None if pdf_path.exists() else "Chrome finished but report.pdf was not created."


def convert_svg_to_png(svg_path: Path, png_path: Path) -> None:
    subprocess.run(["/usr/bin/sips", "-s", "format", "png", str(svg_path), "--out", str(png_path)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def now_in_timezone(timezone_name: str) -> datetime:
    if ZoneInfo is None:
        return datetime.now(timezone.utc)
    try:
        return datetime.now(ZoneInfo(timezone_name))
    except Exception:
        return datetime.now(timezone.utc)


def first_quote(quotes: list[Quote], symbol: str) -> Quote | None:
    normalized = symbol.replace("^", "")
    for quote in quotes:
        if quote.symbol == normalized or quote.symbol == symbol:
            return quote
    return quotes[0] if quotes else None


def coin_by_symbol(coins: list[dict[str, Any]], symbol: str) -> dict[str, Any] | None:
    for coin in coins:
        if str(coin.get("symbol", "")).lower() == symbol.lower():
            return coin
    return None


def is_stablecoin(coin: dict[str, Any]) -> bool:
    symbol = str(coin.get("symbol", "")).lower()
    name = str(coin.get("name", "")).lower()
    return symbol in STABLE_SYMBOLS or ("stable" in name and symbol.startswith("usd"))


def safe_call(fn, default: Any) -> Any:  # noqa: ANN001
    try:
        return fn()
    except Exception:
        return default


def safe_float(value: Any) -> float:
    try:
        if value in (None, "", "-"):
            return 0.0
        number = float(value)
        if math.isnan(number) or math.isinf(number):
            return 0.0
        return number
    except (TypeError, ValueError):
        return 0.0


def first_number(*values: Any) -> float | None:
    for value in values:
        try:
            if value in (None, "", "-"):
                continue
            number = float(value)
            if math.isnan(number) or math.isinf(number):
                continue
            return number
        except (TypeError, ValueError):
            continue
    return None


def pct_change(current: float, previous: float) -> float | None:
    if not previous:
        return None
    return (current - previous) / previous * 100


def weighted_average(values: list[float], weights: list[float]) -> float:
    pairs = [(value, weight) for value, weight in zip(values, weights) if weight > 0]
    total_weight = sum(weight for _, weight in pairs)
    if not total_weight:
        return 0.0
    return sum(value * weight for value, weight in pairs) / total_weight


def format_usd(value: Any) -> str:
    value_float = first_number(value)
    if value_float is None:
        return "-"
    prefix = "-" if value_float < 0 else ""
    value_float = abs(value_float)
    if value_float >= 1_000_000_000_000:
        return f"{prefix}${value_float / 1_000_000_000_000:.2f}T"
    if value_float >= 1_000_000_000:
        return f"{prefix}${value_float / 1_000_000_000:.2f}B"
    if value_float >= 1_000_000:
        return f"{prefix}${value_float / 1_000_000:.2f}M"
    if value_float >= 1_000:
        return f"{prefix}${value_float / 1_000:.2f}K"
    return f"{prefix}${value_float:.2f}"


def format_cny_wan(value: Any) -> str:
    value_float = first_number(value)
    if value_float is None:
        return "-"
    # Eastmoney capital-flow amounts are exposed in ten-thousand yuan units.
    yuan = value_float * 10_000
    prefix = "-" if yuan < 0 else ""
    yuan = abs(yuan)
    if yuan >= 100_000_000:
        return f"{prefix}¥{yuan / 100_000_000:.2f}亿"
    return f"{prefix}¥{yuan / 10_000:.2f}万"


def format_price(value: Any, currency: str = "$") -> str:
    value_float = first_number(value)
    if value_float is None:
        return "-"
    if abs(value_float) >= 1000:
        return f"{currency}{value_float:,.2f}"
    if abs(value_float) >= 1:
        return f"{currency}{value_float:.2f}"
    return f"{currency}{value_float:.5f}"


def format_compact_price(value: Any) -> str:
    value_float = first_number(value)
    if value_float is None:
        return "-"
    prefix = "-" if value_float < 0 else ""
    value_float = abs(value_float)
    if value_float >= 1_000_000:
        return f"{prefix}${value_float / 1_000_000:.2f}M"
    if value_float >= 1000:
        return f"{prefix}${value_float / 1000:.2f}K"
    if value_float >= 1:
        return f"{prefix}${value_float:.2f}"
    return f"{prefix}${value_float:.4f}"


def format_metric(value: Any) -> str:
    value_float = first_number(value)
    if value_float is None:
        return "-"
    if abs(value_float) >= 1_000_000:
        return format_usd(value_float)
    if abs(value_float) >= 1000:
        return f"{value_float:,.2f}"
    if abs(value_float) >= 1:
        return f"{value_float:.2f}"
    return f"{value_float:.5f}"


def pct(value: Any) -> str:
    value_float = first_number(value)
    if value_float is None:
        return "-"
    return f"{value_float:+.2f}%"


def trim(value: str, width: int) -> str:
    text_value = re.sub(r"\s+", " ", value or "").strip()
    if len(text_value) <= width:
        return text_value
    return text_value[: max(0, width - 1)] + "…"


def wrap_text(value: str, width: int) -> list[str]:
    text_value = re.sub(r"\s+", " ", value or "").strip()
    if not text_value:
        return []
    lines = []
    current = ""
    for char in text_value:
        if len(current) >= width:
            lines.append(current)
            current = char
        else:
            current += char
    if current:
        lines.append(current)
    return lines


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def first_line(value: Any) -> str:
    items = as_list(value)
    return str(items[0]) if items else "-"


def join_short(value: Any, limit: int) -> str:
    return " | ".join(trim(str(item), 24) for item in as_list(value)[:limit])


def coin_brief(value: Any) -> str:
    if not isinstance(value, dict) or not value:
        return "暂无数据"
    return f"{value.get('symbol', '')} {format_price(value.get('price'))} {pct(value.get('change_pct'))}"


def coin_card_brief(value: Any) -> str:
    if not isinstance(value, dict) or not value:
        return "暂无数据"
    return f"{value.get('symbol', '')} {format_compact_price(value.get('price'))} {pct(value.get('change_pct'))}"


def heatmap_text_line(label: str, card: Any) -> str:
    if not isinstance(card, dict):
        return f"{label}：50/100，Neutral"
    return f"{label}：{card.get('score', 50)}/100，{card.get('status', 'Neutral')}"


def bullet_lines(items: Any, limit: int = 2) -> list[str]:
    values = [str(item).strip() for item in as_list(items) if str(item).strip()]
    if not values:
        return ["• 数据状态：本轮暂未返回高优先级资讯"]
    return [f"• {value}" for value in values[:limit]]


def bullet_plain(items: Any, limit: int = 2) -> list[str]:
    values = [str(item).strip() for item in as_list(items) if str(item).strip()]
    if not values:
        return ["本轮暂未返回有效数据"]
    return values[:limit]


def find_quote(items: Any, symbol: str, name: str = "") -> dict[str, Any]:
    symbol_value = symbol.replace("^", "")
    for item in as_list(items):
        if not isinstance(item, dict):
            continue
        item_symbol = str(item.get("symbol", "")).replace("^", "")
        item_name = str(item.get("name", ""))
        if item_symbol == symbol_value or item_symbol == symbol or item_name == name:
            return item
    return {}


def quote_text(item: Any, currency: str = "$") -> str:
    if not isinstance(item, dict) or not item:
        return "暂未返回有效数据"
    return f"{format_price(item.get('price'), currency)}，{pct(item.get('change_pct'))}"


def china_data_unavailable(china: dict[str, Any]) -> bool:
    has_indices = bool(as_list(china.get("indices")))
    has_gainers = bool(as_list(china.get("top_gainers")))
    has_losers = bool(as_list(china.get("top_losers")))
    return not (has_indices or has_gainers or has_losers)


def ranking_text_lines(rows: Any) -> list[str]:
    output = []
    for row in as_list(rows)[:5]:
        if not isinstance(row, dict):
            output.append(f"• {row}")
            continue
        symbol = row.get("symbol") or row.get("name") or "-"
        change = pct(row.get("change_pct"))
        price = row.get("price")
        if price is None:
            price = row.get("tvl") or row.get("market_cap")
        reason = row.get("reason") or market_move_reason(row)
        output.append(f"• {symbol} {change} {format_metric(price)} {reason}")
    return output or ["• 数据状态：本轮暂未返回有效榜单"]


def ranking_compact(rows: Any, limit: int = 3, label: str = "symbol") -> list[str]:
    output = []
    for row in as_list(rows)[:limit]:
        if not isinstance(row, dict):
            output.append(str(row))
            continue
        name = row.get(label) or row.get("symbol") or row.get("name") or "-"
        price = row.get("price")
        if price is None:
            price = row.get("tvl") or row.get("market_cap")
        output.append(f"{name} {pct(row.get('change_pct'))} / {format_metric(price)}")
    return output or ["本轮暂未返回有效榜单"]


def market_move_reason(row: dict[str, Any]) -> str:
    change = safe_float(row.get("change_pct"))
    if abs(change) >= 8:
        return "价格波动显著，短线关注成交与消息催化。"
    if change > 0:
        return "相对强势，资金偏好改善。"
    if change < 0:
        return "相对弱势，风险偏好回落。"
    return "价格变化有限，等待新催化。"


def ranking_inline(rows: Any, label: str = "symbol") -> str:
    items = []
    for row in as_list(rows)[:5]:
        if isinstance(row, dict):
            items.append(f"{row.get(label) or row.get('symbol') or row.get('name')} {pct(row.get('change_pct'))}")
        else:
            items.append(str(row))
    return "；".join(items) or "暂未返回有效数据"


def inline_items(items: Any, limit: int = 3) -> str:
    values = [str(item).strip() for item in as_list(items) if str(item).strip()]
    return "；".join(values[:limit]) or "暂无重大事件"


def rwa_summary_line(rwa: dict[str, Any]) -> str:
    return (
        f"TVL {format_usd((rwa.get('tvl') or {}).get('value'))}，"
        f"MCAP {format_usd((rwa.get('market_cap') or {}).get('value'))}，"
        f"Volume {format_usd((rwa.get('volume') or {}).get('value'))}，"
        f"Flow {format_usd((rwa.get('capital_flow') or {}).get('value'))}"
    )


def format_percent_value(value: Any) -> str:
    number = first_number(value)
    if number is None:
        return "-"
    return f"{number:.2f}%"


def fear_greed_text(value: Any) -> str:
    if not isinstance(value, dict) or not value:
        return "暂未返回有效数据"
    return str(value.get("text") or f"{value.get('value', '-')}（{value.get('classification', 'N/A')}）")


def sector_brief(value: Any) -> str:
    if not isinstance(value, dict):
        return "-"
    return f"{format_usd(value.get('market_cap'))} {pct(value.get('change_24h'))}"


def section_line(title: str, value: Any) -> str:
    return f"• *{md(title)}*: {md('；'.join(str(item) for item in as_list(value)[:3]) or '暂无数据')}"


def ranking_line(title: str, rows: Any) -> str:
    items = []
    for row in as_list(rows)[:5]:
        if isinstance(row, dict):
            label = row.get("name") if "Project" in title else row.get("symbol")
            items.append(f"{label or row.get('name') or row.get('symbol')} {pct(row.get('change_pct'))}")
        else:
            items.append(str(row))
    return f"• *{md(title)}*: {md('，'.join(items) or '暂无数据')}"


def sector_line(title: str, sector: Any) -> str:
    if not isinstance(sector, dict):
        return f"• *{md(title)}*: {md('暂无数据')}"
    top = "，".join(f"{row.get('symbol')} {pct(row.get('change_pct'))}" for row in as_list(sector.get("top"))[:3])
    body = f"市值 {format_usd(sector.get('market_cap'))} / {pct(sector.get('change_24h'))}"
    if top:
        body += f"；Top: {top}"
    return f"• *{md(title)}*: {md(body)}"


def split_message(value: str) -> list[str]:
    if len(value) <= 3900:
        return [value]
    chunks = []
    current = []
    length = 0
    for line in value.splitlines():
        if length + len(line) + 1 > 3800 and current:
            chunks.append("\n".join(current))
            current = []
            length = 0
        current.append(line)
        length += len(line) + 1
    if current:
        chunks.append("\n".join(current))
    return chunks


def md(value: Any) -> str:
    return re.sub(r"([_*\[\]()~`>#+\-=|{}.!])", r"\\\1", str(value))


def h(value: Any) -> str:
    return html.escape(str(value or ""), quote=True)


def text(x: float, y: float, value: str, size: int, fill: str, anchor: str = "start", weight: int = 500) -> str:
    return f'<text x="{x:.1f}" y="{y:.1f}" font-family="PingFang SC,Hiragino Sans GB,Arial Unicode MS,Arial,sans-serif" font-size="{size}" font-weight="{weight}" fill="{fill}" text-anchor="{anchor}" letter-spacing="0">{html.escape(value)}</text>'


def round_rect(x: float, y: float, w: float, h: float, radius: int, fill: str, stroke: str, opacity: float = 1, filter_id: str | None = None) -> str:
    filter_attr = f' filter="url(#{filter_id})"' if filter_id else ""
    return f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{radius}" fill="{fill}" stroke="{stroke}" opacity="{opacity}"{filter_attr}/>'


def sparkline_path(values: list[float], x: float, y: float, w: float, h: float, color: str) -> str:
    if len(values) < 2:
        return ""
    low = min(values)
    high = max(values)
    spread = high - low or 1
    points = []
    for index, value in enumerate(values):
        px = x + (w * index / (len(values) - 1))
        py = y + h - ((value - low) / spread * h)
        points.append(f"{px:.1f},{py:.1f}")
    return f'<polyline points="{" ".join(points)}" fill="none" stroke="{color}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>'


def first_text(entry: ET.Element, tags: list[str]) -> str:
    for tag in tags:
        node = entry.find(tag)
        if node is not None and node.text:
            return node.text
    return ""


def first_link(entry: ET.Element) -> str:
    text_link = first_text(entry, ["link", "{http://www.w3.org/2005/Atom}link"])
    if text_link:
        return text_link.strip()
    atom_link = entry.find("{http://www.w3.org/2005/Atom}link")
    if atom_link is not None:
        return atom_link.attrib.get("href", "").strip()
    return ""


def parse_datetime(value: str) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    try:
        parsed = email.utils.parsedate_to_datetime(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except Exception:
        return datetime.now(timezone.utc)


def clean_text(value: str) -> str:
    text_value = html.unescape(value or "")
    text_value = re.sub(r"<[^>]+>", " ", text_value)
    return re.sub(r"\s+", " ", text_value).strip()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Wilson's Market News MVP bot")
    parser.add_argument("--output", type=Path, default=Path(os.getenv("WILSON_OUTPUT_DIR", str(DEFAULT_OUTPUT))).expanduser())
    parser.add_argument("--timezone", default=os.getenv("WILSON_TIMEZONE", DEFAULT_TIMEZONE))
    parser.add_argument("--send", action="store_true", help="Push generated Markdown and PNG to Telegram")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("run-once", help="Generate one Wilson report")
    watch_parser = subparsers.add_parser("watch", help="Run forever on an interval")
    watch_parser.add_argument("--interval-minutes", type=int, default=240)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.command == "run-once":
        status = run_once(args.output, send=args.send, timezone_name=args.timezone)
        print(json.dumps(status, ensure_ascii=False, indent=2))
    elif args.command == "watch":
        watch(args.output, send=args.send, interval_minutes=args.interval_minutes, timezone_name=args.timezone)


if __name__ == "__main__":
    main()
