from __future__ import annotations

import argparse
import json
import os
import time as time_module
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any, Union

from app.fiona_briefing import (
    BRIEF_SCHEDULES,
    FionaBrief,
    FionaBriefKind,
    build_daily_brief,
    build_evening_brief,
    build_market_news_brief,
    build_morning_brief,
    build_weekly_brief,
)
from app.fiona_classifier import render_alert
from app.fiona_engine import FionaAlertEngine
from app.fiona_lifecycle import LifecycleManager
from app.fiona_memory import DecisionMemoryRecord, FionaMemory
from app.fiona_narrative import NarrativeEngine
from app.fiona_types import EventCategory, FionaEvent, MarketDirection, PushDecision
from app.telegram_service import send_message as telegram_send_message
from app.wilson import (
    DEFAULT_TIMEZONE,
    append_telegram_log,
    build_snapshot,
    prepare_output_dirs,
    render_markdown as render_wilson_markdown,
    split_message,
    telegram_message_id,
)

ROOT = Path(__file__).resolve().parent.parent


def load_env_file(path: Path = ROOT / ".env") -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


load_env_file()
DEFAULT_OUTPUT = Path(os.getenv("FIONA_OUTPUT_DIR", str(ROOT / "reports" / "fiona"))).expanduser()
TELEGRAM_LOG_NAME = "fiona_telegram_push.log"
MEMORY_NAME = "fiona_memory.json"

BriefSelector = Union[FionaBriefKind, str]


@dataclass
class FionaPayload:
    snapshot: dict[str, Any]
    events: list[FionaEvent]
    narratives: list[Any]
    brief: FionaBrief | None
    alert_messages: list[str]


def run_once(
    output_dir: Path = DEFAULT_OUTPUT,
    brief: BriefSelector = "auto",
    send: bool = False,
    timezone_name: str = DEFAULT_TIMEZONE,
    snapshot_builder: Callable[[datetime], dict[str, Any]] = build_snapshot,
    fallback_to_wilson: bool = True,
) -> dict[str, Any]:
    generated_at = now_in_timezone(timezone_name)
    latest_dir, archive_dir = prepare_output_dirs(output_dir, generated_at)
    memory_path = output_dir / MEMORY_NAME
    log_path = output_dir / TELEGRAM_LOG_NAME
    status: dict[str, Any] = {
        "ok": True,
        "generated_at": generated_at.isoformat(),
        "brief": str(brief),
        "output_dir": str(latest_dir),
        "archive_dir": str(archive_dir),
        "memory_path": str(memory_path),
        "telegram_log_path": str(log_path),
        "send": send,
        "database_url_configured": bool(os.getenv("DATABASE_URL", "").strip()),
        "alerts": {"enabled": alert_enabled(), "dry_run": alert_dry_run(), "count": 0, "pushed": []},
        "scheduled_briefs": [],
        "errors": [],
        "fallback": None,
    }

    snapshot: dict[str, Any] | None = None
    try:
        snapshot = snapshot_builder(generated_at)
        payload = build_payload(snapshot, generated_at, memory_path, brief)
        write_payload(latest_dir, archive_dir, payload, status)
        if send and should_push_alerts(brief):
            status["alerts"]["pushed"] = push_alerts(payload.alert_messages, log_path)
        if send and payload.brief is not None:
            status["brief_push"] = push_text(payload.brief.render_text(), log_path, scope=payload.brief.title)
    except Exception as exc:  # noqa: BLE001 - runtime must not kill the scheduler on one bad cycle.
        status["ok"] = False
        status["errors"].append(str(exc))
        append_runtime_log(log_path, {"event": "fionaRuntimeError", "ok": False, "error": str(exc)})
        if fallback_to_wilson and snapshot is not None:
            fallback_text = render_wilson_markdown(snapshot)
            for base in (latest_dir, archive_dir):
                (base / "fiona_fallback_telegram.md").write_text(fallback_text, encoding="utf-8")
            fallback_status: dict[str, Any] = {"used": True, "markdown": str(latest_dir / "fiona_fallback_telegram.md")}
            if send:
                fallback_status["push"] = push_text(fallback_text, log_path, scope="Wilson fallback")
            status["fallback"] = fallback_status
        else:
            status["fallback"] = {"used": False}

    for base in (latest_dir, archive_dir):
        (base / "fiona_status.json").write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
    return status


def build_payload(snapshot: dict[str, Any], generated_at: datetime, memory_path: Path, brief: BriefSelector) -> FionaPayload:
    memory = FionaMemory.load(memory_path)
    raw_events = snapshot_to_events(snapshot, generated_at)
    engine = FionaAlertEngine(LifecycleManager(memory.event_memory))
    events = [engine.process(event) for event in raw_events]
    memory.event_memory = engine.lifecycle_manager.records
    narratives = memory.update_narratives(events, now=generated_at)
    alert_messages = [render_alert(event) for event in events if event.push_decision == PushDecision.SEND_NOW]

    brief_obj = build_selected_brief(brief, events, narratives, snapshot, generated_at)
    if brief_obj is not None:
        memory.remember_decision(
            DecisionMemoryRecord(
                created_at=generated_at,
                scope=brief_obj.title,
                direction=dominant_direction(events),
                conviction_score=average_conviction(events),
                reasoning=brief_obj.fiona_view,
                linked_event_ids=brief_obj.linked_event_ids,
                linked_narrative_ids=brief_obj.linked_narrative_ids,
            )
        )
    memory.save(memory_path)
    return FionaPayload(snapshot=snapshot, events=events, narratives=narratives, brief=brief_obj, alert_messages=alert_messages)


def build_selected_brief(
    brief: BriefSelector,
    events: list[FionaEvent],
    narratives: list[Any],
    snapshot: dict[str, Any],
    generated_at: datetime,
) -> FionaBrief | None:
    if str(brief).lower() == "alert":
        return None
    if str(brief).lower() == "auto":
        due = due_brief_kinds(generated_at)
        if not due:
            return None
        return build_brief(due[0], events, narratives, snapshot, generated_at)
    return build_brief(brief_kind_from_name(brief), events, narratives, snapshot, generated_at)


def should_push_alerts(brief: BriefSelector) -> bool:
    if not alert_enabled():
        return False
    if alert_dry_run():
        return False
    return bool(str(brief).strip().lower().replace("-", "_") == "alert" or alert_enabled())


def alert_enabled() -> bool:
    value = first_runtime_env("FIONA_ALERT_ENABLED", "FIONAALERTENABLED") or "0"
    return value.strip().lower() in {"1", "true", "yes", "on"}


def alert_dry_run() -> bool:
    value = first_runtime_env("FIONA_ALERT_DRY_RUN", "FIONAALERTDRYRUN") or "1"
    return value.strip().lower() not in {"0", "false", "no", "off"}


def run_scheduler(
    output_dir: Path = DEFAULT_OUTPUT,
    send: bool = False,
    timezone_name: str = DEFAULT_TIMEZONE,
    interval_minutes: int | None = None,
    max_cycles: int | None = None,
) -> None:
    interval = scheduler_interval_minutes(interval_minutes)
    cycle = 0
    while True:
        cycle += 1
        status = run_once(
            output_dir=output_dir,
            brief="auto",
            send=send,
            timezone_name=timezone_name,
            fallback_to_wilson=True,
        )
        print(json.dumps({"scheduler_cycle": cycle, **status}, ensure_ascii=False, indent=2), flush=True)
        if max_cycles is not None and cycle >= max_cycles:
            return
        time_module.sleep(interval * 60)


def scheduler_interval_minutes(interval_minutes: int | None = None) -> int:
    if interval_minutes is not None:
        return max(1, interval_minutes)
    configured = first_runtime_env("WILSON_INTERVAL_MINUTES", "FIONA_RUNTIME_INTERVAL_MINUTES", "FIONA_ALERT_INTERVAL_MINUTES")
    return max(1, int(configured or "15"))


def build_brief(
    kind: FionaBriefKind,
    events: list[FionaEvent],
    narratives: list[Any],
    snapshot: dict[str, Any],
    generated_at: datetime,
) -> FionaBrief:
    if kind == FionaBriefKind.MORNING:
        return build_morning_brief(events, narratives, generated_at=generated_at)
    if kind == FionaBriefKind.EVENING:
        return build_evening_brief(events, narratives, generated_at=generated_at)
    if kind == FionaBriefKind.MARKET_NEWS:
        return build_market_news_brief(events, narratives, snapshot=snapshot, generated_at=generated_at)
    if kind == FionaBriefKind.DAILY:
        return build_daily_brief(events, narratives, snapshot=snapshot, generated_at=generated_at)
    if kind == FionaBriefKind.WEEKLY:
        return build_weekly_brief(events, narratives, snapshot=snapshot, generated_at=generated_at)
    raise ValueError(f"Unsupported Fiona brief kind: {kind}")


def due_brief_kinds(now: datetime, tolerance_minutes: int = 15) -> list[FionaBriefKind]:
    current = now if now.tzinfo else now.replace(tzinfo=timezone.utc)
    due: list[FionaBriefKind] = []
    for kind, schedule in BRIEF_SCHEDULES.items():
        if kind == FionaBriefKind.WEEKLY and current.isoweekday() != 7:
            continue
        scheduled = current.replace(hour=schedule.send_time.hour, minute=schedule.send_time.minute, second=0, microsecond=0)
        if abs(current - scheduled) <= timedelta(minutes=tolerance_minutes):
            due.append(kind)
    return due


def brief_kind_from_name(value: BriefSelector) -> FionaBriefKind:
    if isinstance(value, FionaBriefKind):
        return value
    normalized = str(value).strip().lower().replace("-", "_")
    aliases = {
        "morning": FionaBriefKind.MORNING,
        "evening": FionaBriefKind.EVENING,
        "market": FionaBriefKind.MARKET_NEWS,
        "market_news": FionaBriefKind.MARKET_NEWS,
        "news": FionaBriefKind.MARKET_NEWS,
        "daily": FionaBriefKind.DAILY,
        "weekly": FionaBriefKind.WEEKLY,
    }
    if normalized not in aliases:
        raise ValueError(f"Unsupported brief selector: {value}")
    return aliases[normalized]


def snapshot_to_events(snapshot: dict[str, Any], generated_at: datetime) -> list[FionaEvent]:
    heatmap = {str(item.get("key")): item for item in snapshot.get("heatmap", []) if isinstance(item, dict)}
    events = [
        us_event(snapshot.get("us_market", {}), heatmap.get("us", {}), generated_at),
        china_event(snapshot.get("china_market", {}), heatmap.get("china", {}), generated_at),
        btc_event(snapshot.get("crypto_market", {}), heatmap.get("crypto", {}), generated_at),
        eth_event(snapshot.get("crypto_market", {}), generated_at),
        rwa_event(snapshot.get("rwa_market", {}), heatmap.get("rwa", {}), generated_at),
    ]
    return [event for event in events if event is not None]


def us_event(market: Any, heat: dict[str, Any], generated_at: datetime) -> FionaEvent:
    data = market if isinstance(market, dict) else {}
    overview = as_text_list(data.get("market_overview"))
    macro = as_text_list(data.get("macro_policy"))
    ai = as_text_list(data.get("ai_sector"))
    title = "US market macro and AI sector update"
    what = first_or_default(macro, first_or_default(overview, "美国市场出现新的宏观与指数信号。"))
    direction = direction_from_heat(heat)
    score = heat_score(heat)
    return FionaEvent(
        event_id=f"us_{generated_at.strftime('%Y%m%d%H%M')}",
        created_at=generated_at,
        source="wilson_snapshot",
        category=EventCategory.MACRO,
        title=title,
        what_happened=what,
        why_important="美股会通过利率预期、科技权重和美元流动性影响全球风险偏好。",
        affected_assets=["SPY", "QQQ", "DXY", "US10Y", "BTC"],
        watch_next=["美债收益率和美元是否继续同向上行", "AI龙头是否获得成交量确认"],
        fiona_view="美股信号需要同时看宏观、ETF和AI龙头承接，不能只看指数涨跌。",
        impact_score=impact_from_heat(score),
        urgency_score=6,
        confidence_score=7,
        market_direction=direction,
        raw_data={
            "narratives": ["macro_liquidity_repricing", "ai_valuation_reset"] if ai else ["macro_liquidity_repricing"],
            "narrative_strength": 12,
            "novelty": 6,
            "funds_score": funds_score_from_direction(direction),
            "fed_rate_related": contains_any(macro, ("fed", "fomc", "rate", "cpi", "ppi", "美联储", "利率", "通胀")),
            "signals": signals_for(direction),
        },
    )


def china_event(market: Any, heat: dict[str, Any], generated_at: datetime) -> FionaEvent:
    data = market if isinstance(market, dict) else {}
    policy = as_text_list(data.get("policy_update"))
    overview = as_text_list(data.get("market_overview"))
    direction = direction_from_heat(heat)
    score = heat_score(heat)
    return FionaEvent(
        event_id=f"china_{generated_at.strftime('%Y%m%d%H%M')}",
        created_at=generated_at,
        source="wilson_snapshot",
        category=EventCategory.REGULATION,
        title="China market policy and flow update",
        what_happened=first_or_default(policy, first_or_default(overview, "中国市场等待政策与资金承接确认。")),
        why_important="中国市场更依赖政策预期、流动性边际变化和核心资产承接。",
        affected_assets=["CSI500", "ASHR", "MCHI", "CNH"],
        watch_next=["政策口径是否转化为成交量", "核心资产和人民币汇率是否同步确认"],
        fiona_view="中国市场先看政策和资金是否形成闭环，单日涨跌不应直接外推。",
        impact_score=impact_from_heat(score),
        urgency_score=5,
        confidence_score=6,
        market_direction=direction,
        raw_data={
            "narratives": ["china_policy_flow_watch"],
            "narrative_strength": 8,
            "novelty": 5,
            "funds_score": funds_score_from_direction(direction),
            "major_regulatory_action": contains_any(policy, ("央行", "证监", "政策", "lpr", "rrr", "pboc", "csrc")),
            "signals": signals_for(direction),
        },
    )


def btc_event(crypto: Any, heat: dict[str, Any], generated_at: datetime) -> FionaEvent:
    data = crypto if isinstance(crypto, dict) else {}
    btc = data.get("btc") if isinstance(data.get("btc"), dict) else {}
    change = first_number(btc.get("change_pct"), btc.get("price_change_percentage_24h"))
    direction = direction_from_change(change, direction_from_heat(heat))
    return FionaEvent(
        event_id=f"btc_{generated_at.strftime('%Y%m%d%H%M')}",
        created_at=generated_at,
        source="wilson_snapshot",
        category=EventCategory.PRICE,
        title="BTC price and ETF confirmation watch",
        what_happened=f"BTC本周期变化 {format_pct(change)}。",
        why_important="BTC是加密风险偏好的核心锚，1小时或短周期波动需要看ETF、稳定币和杠杆是否同步确认。",
        affected_assets=["BTC", "ETH", "SOL"],
        watch_next=["BTC关键支撑/压力是否被放量突破", "ETF资金流和稳定币供给是否同步恶化"],
        fiona_view="BTC波动本身不是结论，只有资金流和风险指标共振时才提高情报权重。",
        impact_score=impact_from_change(change),
        urgency_score=8 if abs(change or 0) >= 1.5 else 5,
        confidence_score=8,
        market_direction=direction,
        raw_data={
            "symbol": "BTC",
            "change_pct": change or 0,
            "support_break": bool((change or 0) <= -1.5),
            "narratives": ["btc_etf_flow_weakness"] if (change or 0) < 0 else [],
            "narrative_strength": 14 if abs(change or 0) >= 1.5 else 8,
            "novelty": 7,
            "funds_score": funds_score_from_direction(direction),
            "signals": signals_for(direction),
        },
        evidence=["price_move"] if abs(change or 0) >= 1.5 else [],
    )


def eth_event(crypto: Any, generated_at: datetime) -> FionaEvent:
    data = crypto if isinstance(crypto, dict) else {}
    eth = data.get("eth") if isinstance(data.get("eth"), dict) else {}
    change = first_number(eth.get("change_pct"), eth.get("price_change_percentage_24h"))
    direction = direction_from_change(change, MarketDirection.NEUTRAL)
    return FionaEvent(
        event_id=f"eth_{generated_at.strftime('%Y%m%d%H%M')}",
        created_at=generated_at,
        source="wilson_snapshot",
        category=EventCategory.PRICE,
        title="ETH price confirmation watch",
        what_happened=f"ETH本周期变化 {format_pct(change)}。",
        why_important="ETH波动会影响Layer1、DeFi和山寨风险偏好，需要和BTC及资金流一起判断。",
        affected_assets=["ETH", "L1", "DeFi"],
        watch_next=["ETH/BTC强弱是否继续变化", "链上活跃度和DEX成交是否确认"],
        fiona_view="ETH若没有资金流和链上活跃确认，单独波动更像风险偏好噪音。",
        impact_score=impact_from_change(change),
        urgency_score=8 if abs(change or 0) >= 3 else 5,
        confidence_score=7,
        market_direction=direction,
        raw_data={
            "symbol": "ETH",
            "change_pct": change or 0,
            "narrative_strength": 8,
            "novelty": 5,
            "funds_score": funds_score_from_direction(direction),
            "signals": signals_for(direction),
        },
        evidence=["price_move"] if abs(change or 0) >= 3 else [],
    )


def rwa_event(market: Any, heat: dict[str, Any], generated_at: datetime) -> FionaEvent:
    data = market if isinstance(market, dict) else {}
    direction = direction_from_heat(heat)
    score = heat_score(heat)
    events = rwa_relevant_lines(as_text_list(data.get("major_events")))
    return FionaEvent(
        event_id=f"rwa_{generated_at.strftime('%Y%m%d%H%M')}",
        created_at=generated_at,
        source="wilson_snapshot",
        category=EventCategory.RWA,
        title="RWA institutional adoption watch",
        what_happened=first_or_default(events, "RWA市场继续跟踪TVL、市值、成交和机构事件。"),
        why_important="RWA是机构资金链上化的重要线索，价值在持续性和资金确认，不在短线热度。",
        affected_assets=["RWA", "ONDO", "MKR", "BUIDL"],
        watch_next=["RWA TVL是否持续流入", "机构项目更新是否带来真实资金和使用场景"],
        fiona_view="RWA应看机构采用和资金持续性，避免把短期公告当作完整主线。",
        impact_score=impact_from_heat(score),
        urgency_score=5,
        confidence_score=7,
        market_direction=direction,
        raw_data={
            "narratives": ["rwa_institutional_adoption"],
            "notable_update": bool(events),
            "narrative_strength": 12,
            "novelty": 6,
            "funds_score": funds_score_from_direction(direction),
            "signals": signals_for(direction),
        },
    )


def rwa_relevant_lines(lines: list[str]) -> list[str]:
    keywords = ("rwa", "real world", "tokenized", "tokenization", "treasury", "blackrock", "franklin", "ondo", "buidl", "代币化", "国债")
    return [line for line in lines if contains_any([line], keywords)]


def write_payload(latest_dir: Path, archive_dir: Path, payload: FionaPayload, status: dict[str, Any]) -> None:
    for base in (latest_dir, archive_dir):
        base.mkdir(parents=True, exist_ok=True)
        (base / "fiona_snapshot.json").write_text(json.dumps(payload.snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
        (base / "fiona_events.json").write_text(json.dumps([event.to_dict() for event in payload.events], ensure_ascii=False, indent=2), encoding="utf-8")
        (base / "fiona_narratives.json").write_text(
            json.dumps([record.to_dict() for record in payload.narratives], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        if payload.alert_messages:
            (base / "fiona_alerts.md").write_text("\n\n---\n\n".join(payload.alert_messages), encoding="utf-8")
        else:
            (base / "fiona_alerts.md").unlink(missing_ok=True)
        if payload.brief is not None:
            (base / "fiona_telegram.md").write_text(payload.brief.render_text(), encoding="utf-8")
        else:
            (base / "fiona_telegram.md").unlink(missing_ok=True)
    status["alerts"]["count"] = len(payload.alert_messages)
    if payload.brief is not None:
        status["scheduled_briefs"].append(
            {
                "kind": payload.brief.kind.value,
                "title": payload.brief.title,
                "markdown": str(latest_dir / "fiona_telegram.md"),
            }
        )


def push_alerts(alert_messages: list[str], log_path: Path) -> list[dict[str, Any]]:
    results = []
    for index, message in enumerate(alert_messages, 1):
        result = push_text(message, log_path, scope=f"Fiona Alert {index}")
        results.append(result)
    return results


def push_text(text: str, log_path: Path, scope: str) -> dict[str, Any]:
    result: dict[str, Any] = {"scope": scope, "ok": False, "message_ids": [], "errors": []}
    for index, chunk in enumerate(split_message(text), 1):
        try:
            response = telegram_send_message(chunk)
            message_id = telegram_message_id(response)
            result["message_ids"].append(message_id)
            append_telegram_log(log_path, {"event": "sendMessage", "scope": scope, "ok": True, "chunk": index, "message_id": message_id})
        except Exception as exc:  # noqa: BLE001 - push failure must not stop Fiona.
            error = str(exc)
            result["errors"].append(error)
            append_telegram_log(log_path, {"event": "sendMessage", "scope": scope, "ok": False, "chunk": index, "error": error})
    result["ok"] = bool(result["message_ids"])
    return result


def append_runtime_log(log_path: Path, payload: dict[str, Any]) -> None:
    append_telegram_log(log_path, payload)


def dominant_direction(events: list[FionaEvent]) -> MarketDirection:
    scores = {MarketDirection.BULLISH: 0, MarketDirection.NEUTRAL: 0, MarketDirection.BEARISH: 0}
    for event in events:
        scores[event.market_direction] += max(1, event.intelligence_score)
    return max(scores, key=scores.get) if events else MarketDirection.NEUTRAL


def average_conviction(events: list[FionaEvent]) -> int:
    if not events:
        return 0
    return round(sum(event.conviction_score for event in events) / len(events))


def now_in_timezone(timezone_name: str) -> datetime:
    try:
        from zoneinfo import ZoneInfo

        return datetime.now(ZoneInfo(timezone_name))
    except Exception:
        return datetime.now(timezone.utc)


def as_text_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    if isinstance(value, dict):
        text = value.get("text")
        return [str(text)] if text else []
    return []


def first_or_default(values: list[str], default: str) -> str:
    return values[0] if values else default


def heat_score(heat: dict[str, Any]) -> int:
    try:
        return int(heat.get("score", 50))
    except (TypeError, ValueError):
        return 50


def direction_from_heat(heat: dict[str, Any]) -> MarketDirection:
    status = str(heat.get("status", "")).lower()
    if status == "bullish":
        return MarketDirection.BULLISH
    if status == "bearish":
        return MarketDirection.BEARISH
    return MarketDirection.NEUTRAL


def direction_from_change(change: float | None, default: MarketDirection) -> MarketDirection:
    if change is None:
        return default
    if change > 0.4:
        return MarketDirection.BULLISH
    if change < -0.4:
        return MarketDirection.BEARISH
    return MarketDirection.NEUTRAL


def impact_from_heat(score: int) -> int:
    return max(4, min(10, round(4 + abs(score - 50) / 6)))


def impact_from_change(change: float | None) -> int:
    absolute = abs(change or 0)
    if absolute >= 5:
        return 10
    if absolute >= 3:
        return 9
    if absolute >= 1.5:
        return 8
    if absolute >= 0.8:
        return 6
    return 4


def funds_score_from_direction(direction: MarketDirection) -> int:
    if direction == MarketDirection.BULLISH:
        return 70
    if direction == MarketDirection.BEARISH:
        return 28
    return 50


def signals_for(direction: MarketDirection) -> dict[str, str]:
    if direction == MarketDirection.BULLISH:
        return {"price": "bullish", "funds": "inflow", "narrative": "supportive"}
    if direction == MarketDirection.BEARISH:
        return {"price": "bearish", "funds": "outflow", "risk": "stress"}
    return {"price": "neutral", "funds": "neutral", "narrative": "mixed"}


def contains_any(lines: list[str], keywords: tuple[str, ...]) -> bool:
    text = " ".join(lines).lower()
    return any(keyword.lower() in text for keyword in keywords)


def first_number(*values: Any) -> float | None:
    for value in values:
        try:
            if value in (None, "", "-"):
                continue
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def format_pct(value: float | None) -> str:
    if value is None:
        return "-"
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.2f}%"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fiona Intelligence System runtime")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--timezone", default=first_runtime_env("FIONA_TIMEZONE", "WILSON_TIMEZONE") or DEFAULT_TIMEZONE)
    parser.add_argument("--brief", default=os.getenv("FIONA_BRIEF", "auto"), help="auto, alert, morning, evening, market-news, daily, weekly")
    parser.add_argument("--send", action="store_true", help="Push generated Fiona text to Telegram")
    parser.add_argument("--no-fallback", action="store_true", help="Disable Wilson text fallback if Fiona generation fails")
    parser.add_argument("--interval-minutes", type=int, default=None, help="Scheduler polling interval")
    parser.add_argument("--max-cycles", type=int, default=None, help="Testing only: stop scheduler after N cycles")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("run-once", help="Generate one Fiona cycle")
    subparsers.add_parser("run-scheduler", help="Run Fiona continuously for Railway production")
    return parser.parse_args()


def resolve_send(send_flag: bool) -> bool:
    for env_name in ("WILSON_SEND", "FIONA_SEND", "FIONA_SEND_TELEGRAM"):
        env_value = os.getenv(env_name)
        if env_value is not None and env_value.strip() != "":
            return env_value.strip() == "1"
    return bool(send_flag)


def first_runtime_env(*names: str) -> str:
    for name in names:
        value = os.getenv(name, "").strip()
        if value:
            return value
    return ""


def main() -> None:
    args = parse_args()
    send = resolve_send(args.send)
    if args.command == "run-scheduler":
        run_scheduler(
            output_dir=args.output.expanduser(),
            send=send,
            timezone_name=args.timezone,
            interval_minutes=args.interval_minutes,
            max_cycles=args.max_cycles,
        )
        return
    status = run_once(
        output_dir=args.output.expanduser(),
        brief=args.brief,
        send=send,
        timezone_name=args.timezone,
        fallback_to_wilson=not args.no_fallback,
    )
    print(json.dumps(status, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
