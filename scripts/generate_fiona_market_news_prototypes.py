from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.fiona_market_news_image import (
    build_market_news_prototype,
    build_market_news_view_model,
)
from app.fiona_narrative import NarrativeEngine
from app.fiona_types import EventCategory, FionaEvent, MarketDirection


OUTPUT_DIR = ROOT / "reports" / "prototypes" / "fiona_market_news"
NOW = datetime(2026, 7, 24, 16, 0, tzinfo=ZoneInfo("Asia/Hong_Kong"))


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    scenarios = {
        "market_news_full.png": full_snapshot(),
        "market_news_missing.png": missing_snapshot(),
        "market_news_long_text.png": long_text_snapshot(),
    }
    events = prototype_events()
    narratives = NarrativeEngine().build(events, now=NOW)
    captions: list[str] = []
    for filename, snapshot in scenarios.items():
        view_model = build_market_news_view_model(snapshot, events, narratives, generated_at=NOW)
        result = build_market_news_prototype(
            view_model,
            OUTPUT_DIR / filename,
            original_text="Fiona Market News 文字模式回退内容。",
        )
        if result.mode != "image_with_caption" or result.image_path is None:
            raise RuntimeError(f"{filename}: {result.error}")
        captions.extend(
            [
                f"## {filename}",
                "",
                result.caption,
                "",
                f"- Data quality: {view_model.data_quality.status}",
                f"- Image: {result.image_path}",
                "",
            ]
        )
    (OUTPUT_DIR / "caption_examples.md").write_text("\n".join(captions).strip() + "\n", encoding="utf-8")


def prototype_events() -> list[FionaEvent]:
    return [
        FionaEvent(
            event_id="phase2a_fed",
            created_at=NOW,
            source="prototype_macro",
            category=EventCategory.MACRO,
            title="美债收益率上行影响跨市场风险偏好",
            what_happened="美债收益率抬升，美股科技与加密风险偏好同步降温",
            why_important="利率重新定价正在影响高估值资产与美元流动性",
            affected_assets=["SPX", "QQQ", "BTC", "DXY", "US10Y"],
            watch_next=["美债收益率与美元是否继续同向上行"],
            fiona_view="宏观流动性仍是本周期的首要确认变量。",
            intelligence_score=84,
            confidence_score=8,
            impact_score=8,
            urgency_score=7,
            market_direction=MarketDirection.BEARISH,
            raw_data={"narratives": ["macro_liquidity_repricing"], "funds_score": 36},
        ),
        FionaEvent(
            event_id="phase2a_btc",
            created_at=NOW,
            source="prototype_crypto",
            category=EventCategory.ETF,
            title="BTC资金流尚未确认价格修复",
            what_happened="BTC价格小幅修复，但ETF与稳定币资金尚未同步转强",
            why_important="缺少资金确认时，单一价格反弹难以代表风险偏好切换",
            affected_assets=["BTC", "ETH", "ETF"],
            watch_next=["ETF是否恢复净流入，稳定币供给是否同步扩张"],
            fiona_view="价格改善需要资金流共同验证。",
            intelligence_score=79,
            confidence_score=8,
            impact_score=7,
            urgency_score=6,
            market_direction=MarketDirection.NEUTRAL,
            raw_data={"narratives": ["btc_etf_flow_weakness"], "funds_score": 38},
        ),
        FionaEvent(
            event_id="phase2a_rwa",
            created_at=NOW,
            source="prototype_rwa",
            category=EventCategory.RWA,
            title="RWA资金结构保持稳定",
            what_happened="RWA TVL保持温和流入，机构化叙事未出现明显退潮",
            why_important="稳定的TVL与机构采用比短期代币涨跌更能说明叙事持续性",
            affected_assets=["RWA", "ONDO", "BUIDL"],
            watch_next=["TVL流入能否延续，并转化为真实使用与成交"],
            fiona_view="RWA仍属于慢变量，需要持续数据验证。",
            intelligence_score=72,
            confidence_score=7,
            impact_score=6,
            urgency_score=5,
            market_direction=MarketDirection.BULLISH,
            raw_data={"narratives": ["rwa_institutional_adoption"], "funds_score": 67},
        ),
    ]


def full_snapshot() -> dict[str, object]:
    return {
        "generated_at": NOW.isoformat(),
        "generated_at_display": NOW.strftime("%Y-%m-%d %H:%M"),
        "heatmap": [
            {"key": "us", "label": "US Market", "score": 54, "status": "Neutral", "summary": "S&P 500 -0.34%"},
            {"key": "china", "label": "China Market", "score": 58, "status": "Neutral", "summary": "中证500 +0.42%"},
            {"key": "crypto", "label": "Crypto Market", "score": 47, "status": "Neutral", "summary": "BTC +0.28%"},
            {"key": "rwa", "label": "RWA Market", "score": 66, "status": "Neutral", "summary": "TVL +0.31%"},
        ],
        "us_market": {"primary": {"name": "S&P 500", "price": 6376.21, "change_pct": -0.34}},
        "china_market": {"primary": {"name": "中证500", "price": 6238.44, "change_pct": 0.42}},
        "crypto_market": {
            "btc": {"current_price": 118420, "change_pct": 0.28},
            "eth": {"current_price": 3728.4, "change_pct": -0.61},
            "stablecoin_growth": {"current": 313_870_000_000, "change_1d": 0.08},
        },
        "rwa_market": {"tvl": {"value": 13_420_000_000, "change_1d": 0.31}},
        "daily_market": {
            "quotes": [
                {"symbol": "HSI", "name": "Hang Seng", "price": 25572.88, "change_pct": 0.73},
                {"symbol": "^TNX", "name": "US 10Y", "price": 4.32, "change_pct": 0.06},
                {"symbol": "GC=F", "name": "Gold", "price": 2450.5, "change_pct": 1.2},
            ]
        },
        "wilson_view": (
            "当前市场处于中性震荡，宏观利率仍压制高估值风险偏好，BTC价格修复尚未获得资金流确认。"
            "RWA保持相对稳定，但跨市场方向仍需等待美元、美债与ETF流向形成一致信号。"
        ),
        "errors": [],
    }


def missing_snapshot() -> dict[str, object]:
    snapshot = deepcopy(full_snapshot())
    snapshot["heatmap"] = [
        {"key": "us", "label": "US Market", "score": 54, "status": "Neutral", "summary": "S&P 500 -0.34%"},
        {"key": "crypto", "label": "Crypto Market", "score": 47, "status": "Neutral", "summary": "BTC +0.28%"},
    ]
    snapshot["daily_market"] = {"quotes": []}
    snapshot["rwa_market"] = {}
    snapshot["errors"] = ["China Market: upstream timeout", "RWA Market: source response incomplete"]
    snapshot["wilson_view"] = (
        "部分市场数据尚未完成交叉验证。现有信号显示风险偏好仍偏谨慎，"
        "但在中国市场与RWA数据恢复前，不宜把局部变化解释为完整的跨市场方向。"
    )
    return snapshot


def long_text_snapshot() -> dict[str, object]:
    snapshot = deepcopy(full_snapshot())
    snapshot["wilson_view"] = (
        "过去四小时的变化并不来自单一价格突破，而是来自美债收益率、美元流动性、美股科技权重、"
        "比特币ETF资金流、稳定币供给以及RWA机构采用之间的信号分化。当前价格表现并未形成足够强的"
        "跨市场共振，部分资产的短期修复更接近局部风险偏好回暖。下一轮需要继续验证ETF资金是否恢复、"
        "美元与美债是否同向上行、RWA TVL是否保持持续流入，以及中国核心资产能否获得成交量确认。"
    )
    return snapshot


if __name__ == "__main__":
    main()
