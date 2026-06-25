from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from app.fiona_classifier import render_alert
from app.fiona_engine import FionaAlertEngine
from app.fiona_lifecycle import LifecycleManager
from app.fiona_memory import FionaMemory
from app.fiona_types import EventCategory, FionaEvent, MarketDirection, PushDecision
from app.telegram_service import send_message as telegram_send_message
from app.wilson import append_telegram_log, telegram_message_id

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ALERT_OUTPUT = Path(os.getenv("FIONA_ALERT_OUTPUT_DIR", str(ROOT / "reports" / "fiona" / "alerts"))).expanduser()
ALERT_LOG_NAME = "fiona_alert_push.log"
ALERT_MEMORY_NAME = "fiona_alert_memory.json"


@dataclass
class AlertRunItem:
    event: FionaEvent
    message: str
    sent: bool
    reason: str
    telegram_message_id: int | None = None
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event.event_id,
            "level": self.event.level.value,
            "category": self.event.category.value,
            "intelligence_score": self.event.intelligence_score,
            "conviction_score": self.event.conviction_score,
            "lifecycle_status": self.event.lifecycle_status.value,
            "push_decision": self.event.push_decision.value,
            "sent": self.sent,
            "reason": self.reason,
            "telegram_message_id": self.telegram_message_id,
            "error": self.error,
            "created_at": self.event.created_at.astimezone(timezone.utc).isoformat(),
            "preview": self.message,
        }


def alert_enabled() -> bool:
    return os.getenv("FIONA_ALERT_ENABLED", "0").strip().lower() in {"1", "true", "yes", "on"}


def alert_dry_run() -> bool:
    return os.getenv("FIONA_ALERT_DRY_RUN", "1").strip().lower() not in {"0", "false", "no", "off"}


def process_alert_events(
    events: list[FionaEvent],
    output_dir: Path = DEFAULT_ALERT_OUTPUT,
    send_func: Callable[[str], dict[str, Any]] = telegram_send_message,
    dry_run: bool | None = None,
    enabled: bool | None = None,
) -> list[AlertRunItem]:
    output_dir.mkdir(parents=True, exist_ok=True)
    memory_path = output_dir / ALERT_MEMORY_NAME
    log_path = output_dir / ALERT_LOG_NAME
    memory = FionaMemory.load(memory_path)
    engine = FionaAlertEngine(LifecycleManager(memory.event_memory))
    dry = alert_dry_run() if dry_run is None else dry_run
    active = alert_enabled() if enabled is None else enabled
    results: list[AlertRunItem] = []

    for raw_event in events:
        event = engine.process(raw_event)
        message = render_alert(event)
        should_send = active and not dry and event.push_decision == PushDecision.SEND_NOW
        reason = decision_reason(event, enabled=active, dry_run=dry)
        item = AlertRunItem(event=event, message=message, sent=False, reason=reason)
        if should_send:
            try:
                response = send_func(message)
                item.telegram_message_id = telegram_message_id(response)
                item.sent = item.telegram_message_id is not None
            except Exception as exc:  # noqa: BLE001 - alert push must never kill Fiona.
                item.error = str(exc)
        append_alert_log(log_path, item)
        results.append(item)

    memory.event_memory = engine.lifecycle_manager.records
    memory.save(memory_path)
    write_alert_outputs(output_dir, results)
    return results


def decision_reason(event: FionaEvent, enabled: bool, dry_run: bool) -> str:
    if event.push_decision == PushDecision.SEND_NOW:
        if not enabled:
            return "Alert enabled=0，已生成预览但不发送。"
        if dry_run:
            return "Dry run=1，符合推送条件但不真实发送。"
        return "符合 S/A 级推送条件。"
    if event.push_decision == PushDecision.BRIEF_POOL:
        return "未达到实时推送阈值，进入 Brief Pool。"
    if event.push_decision == PushDecision.SUPPRESS_DUPLICATE:
        return "命中冷却/去重规则，本轮不重复推送。"
    return "C 级或低价值噪音，仅记录。"


def append_alert_log(log_path: Path, item: AlertRunItem) -> None:
    append_telegram_log(
        log_path,
        {
            "event": "fionaAlert",
            "event_id": item.event.event_id,
            "level": item.event.level.value,
            "category": item.event.category.value,
            "intelligence_score": item.event.intelligence_score,
            "telegram_message_id": item.telegram_message_id,
            "success": item.sent,
            "error": item.error,
            "created_at": item.event.created_at.astimezone(timezone.utc).isoformat(),
            "reason": item.reason,
        },
    )


def write_alert_outputs(output_dir: Path, results: list[AlertRunItem]) -> None:
    (output_dir / "fiona_alert_results.json").write_text(
        json.dumps([item.to_dict() for item in results], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    previews = []
    for item in results:
        previews.append(
            "\n".join(
                [
                    f"Event：{item.event.event_id}",
                    f"Triggered：{item.event.push_decision == PushDecision.SEND_NOW}",
                    f"Level：{item.event.level.value}",
                    f"Would Send：{item.event.push_decision == PushDecision.SEND_NOW and not item.sent}",
                    f"Reason：{item.reason}",
                    "",
                    item.message,
                ]
            )
        )
    (output_dir / "fiona_alert_previews.md").write_text("\n\n---\n\n".join(previews), encoding="utf-8")


def simulated_alert_events(now: datetime | None = None) -> list[FionaEvent]:
    current = now or datetime.now(timezone.utc)
    return [
        make_price_event(current, "BTC", -1.8, ["BTC", "ETH", "SOL"], "BTC 1小时下跌1.8%，触发价格异常波动。"),
        make_price_event(current, "ETH", -3.2, ["ETH", "BTC", "DeFi"], "ETH 1小时下跌3.2%，触发价格异常波动。"),
        make_etf_event(current),
        make_institution_event(current),
        make_risk_event(current),
        make_narrative_event(current),
    ]


def make_price_event(now: datetime, symbol: str, change: float, assets: list[str], what: str) -> FionaEvent:
    return FionaEvent(
        event_id=f"sim_price_{symbol.lower()}_{now.strftime('%Y%m%d%H%M')}",
        created_at=now,
        source="alert_simulator",
        category=EventCategory.PRICE,
        title=f"{symbol} abnormal 1h move",
        what_happened=what,
        why_important=f"{symbol}短周期波动已超过 Fiona 阈值，说明风险偏好或杠杆资金可能正在重新定价。",
        affected_assets=assets,
        watch_next=["相关资产是否同步扩大波动", "ETF资金流或链上成交是否确认", "波动是否扩散到美股风险资产"],
        fiona_view="这是需要记录的急性波动信号，但 Fiona 不把单一价格变化直接外推为趋势，后续要看资金和跨资产确认。",
        impact_score=8,
        urgency_score=9,
        confidence_score=9,
        market_direction=MarketDirection.BEARISH if change < 0 else MarketDirection.BULLISH,
        raw_data={
            "symbol": symbol,
            "change_pct": change,
            "support_break": change < 0,
            "narrative_strength": 10,
            "novelty": 8,
            "signals": {"price": "bearish" if change < 0 else "bullish", "risk": "stress"},
        },
        evidence=[f"{symbol}_1h_move"],
    )


def make_etf_event(now: datetime) -> FionaEvent:
    return FionaEvent(
        event_id=f"sim_etf_btc_outflow_{now.strftime('%Y%m%d%H%M')}",
        created_at=now,
        source="alert_simulator",
        category=EventCategory.ETF,
        title="BTC ETF net outflow exceeds threshold",
        what_happened="BTC ETF 单日净流出约 1.5 亿美元，超过 Fiona 实时阈值。",
        why_important="ETF资金是本轮 BTC 风险偏好的关键确认变量，单日大额流出会削弱市场对现货承接的信心。",
        affected_assets=["BTC", "ETH", "IBIT", "FBTC"],
        watch_next=["后续是否出现连续净流出", "BTC成交量是否同步放大", "稳定币供给是否同时走弱"],
        fiona_view="该事件比单纯价格波动更有情报价值，因为它反映了资金端的真实变化。下一步需要看流出是否持续。",
        impact_score=9,
        urgency_score=8,
        confidence_score=9,
        market_direction=MarketDirection.BEARISH,
        raw_data={
            "asset": "BTC",
            "net_flow_usd": -150_000_000,
            "narrative_strength": 18,
            "novelty": 8,
            "signals": {"funds": "outflow", "price": "bearish", "narrative": "bearish"},
        },
        evidence=["btc_etf_outflow_threshold"],
    )


def make_institution_event(now: datetime) -> FionaEvent:
    return FionaEvent(
        event_id=f"sim_blackrock_rwa_{now.strftime('%Y%m%d%H%M')}",
        created_at=now,
        source="alert_simulator",
        category=EventCategory.INSTITUTION,
        title="BlackRock RWA product update",
        what_happened="BlackRock RWA 产品出现重要更新，市场重新关注代币化资产的机构采用进度。",
        why_important="机构级 RWA 更新会影响市场对链上国债、代币化基金和合规资产发行的理解。",
        affected_assets=["RWA", "ONDO", "MKR", "BUIDL"],
        watch_next=["RWA TVL是否出现真实流入", "ONDO/MKR成交是否获得资金确认", "后续是否有更多机构跟进"],
        fiona_view="这是中高价值叙事事件，重点不在标题热度，而在 TVL、成交和机构持续动作是否同步。",
        impact_score=8,
        urgency_score=6,
        confidence_score=8,
        market_direction=MarketDirection.BULLISH,
        raw_data={
            "institution": "BlackRock",
            "major_event": True,
            "notable_update": True,
            "narrative_strength": 19,
            "novelty": 8,
            "signals": {"narrative": "bullish", "funds": "neutral"},
        },
        evidence=["blackrock_rwa_update"],
    )


def make_risk_event(now: datetime) -> FionaEvent:
    return FionaEvent(
        event_id=f"sim_liquidation_{now.strftime('%Y%m%d%H%M')}",
        created_at=now,
        source="alert_simulator",
        category=EventCategory.RISK,
        title="Crypto liquidation exceeds 100M in 1h",
        what_happened="全网 1 小时爆仓约 1.2 亿美元，超过 Fiona 重大风险阈值。",
        why_important="大额爆仓说明杠杆资金正在被动出清，短期波动可能从单一资产扩散到整个 Crypto 风险偏好。",
        affected_assets=["BTC", "ETH", "SOL", "Crypto"],
        watch_next=["爆仓是否继续扩大到4小时窗口", "主流币成交量是否异常放大", "稳定币是否出现脱锚或链上流动性压力"],
        fiona_view="这是急性风险事件，优先级高于普通行情波动。若后续没有继续扩散，事件会从风险状态降为观察状态。",
        impact_score=10,
        urgency_score=10,
        confidence_score=9,
        market_direction=MarketDirection.BEARISH,
        raw_data={
            "major_risk_event": True,
            "liquidation_usd_1h": 120_000_000,
            "narrative_strength": 16,
            "novelty": 9,
            "signals": {"risk": "stress", "price": "bearish", "funds": "outflow"},
        },
        evidence=["liquidation_1h_over_100m"],
    )


def make_narrative_event(now: datetime) -> FionaEvent:
    return FionaEvent(
        event_id=f"sim_narrative_emerging_{now.strftime('%Y%m%d%H%M')}",
        created_at=now,
        source="alert_simulator",
        category=EventCategory.NARRATIVE,
        title="Emerging narrative score exceeds 70",
        what_happened="Emerging Narrative 强度首次超过 70，市场叙事从零散讨论转向可追踪主题。",
        why_important="叙事强度越过阈值，说明多个事件开始指向同一市场主题，值得进入下一轮简报和实时观察。",
        affected_assets=["AI", "RWA", "BTC", "QQQ"],
        watch_next=["该叙事是否连续出现在后续简报", "资金流是否跟随主题变化", "是否出现伪叙事风险"],
        fiona_view="这是叙事层面的早期信号，不代表趋势已经成立。Fiona 会把它放入观察池，并等待资金和持续性确认。",
        impact_score=7,
        urgency_score=6,
        confidence_score=8,
        market_direction=MarketDirection.NEUTRAL,
        raw_data={
            "narrative_score": 72,
            "narrative_delta": 16,
            "narrative_strength": 18,
            "novelty": 9,
            "signals": {"narrative": "neutral", "funds": "mixed"},
        },
        evidence=["emerging_narrative_over_70"],
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Fiona Alert dry-run runtime")
    parser.add_argument("--simulate", action="store_true", help="Run built-in simulated alert events")
    parser.add_argument("--output-dir", default=str(DEFAULT_ALERT_OUTPUT))
    parser.add_argument("--send", action="store_true", help="Allow real Telegram send when env also enables it")
    args = parser.parse_args()
    if not args.simulate:
        raise SystemExit("Use --simulate for the V1.0 dry-run test.")
    events = simulated_alert_events()
    results = process_alert_events(events, Path(args.output_dir), dry_run=not args.send or alert_dry_run(), enabled=alert_enabled())
    print(json.dumps([item.to_dict() for item in results], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
