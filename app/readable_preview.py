from __future__ import annotations

import argparse
import html
import json
from collections import Counter
from datetime import datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.desktop_export import DESKTOP_REPORT_DIR, PDF_FONT_NAME, register_pdf_font
from app.main import DEFAULT_OUTPUT
from app.market_universe import build_universe_snapshot, money, pct, price

MARKETS = ["us_equities", "china_equities", "crypto"]
MARKET_NAMES = {
    "us_equities": "美股",
    "china_equities": "中国股市",
    "crypto": "加密货币",
}
MARKET_COLORS = {
    "us_equities": {"accent": "#075BA8", "soft": "#EAF4FA", "deep": "#073B57", "on": "#FFFFFF"},
    "china_equities": {"accent": "#B42318", "soft": "#FFF0EA", "deep": "#72170F", "on": "#FFE082"},
    "crypto": {"accent": "#087568", "soft": "#EAF4F2", "deep": "#06483F", "on": "#FFFFFF"},
}
TAG_NAMES = {
    "macro": "宏观",
    "policy": "政策/监管",
    "market": "市场走势",
    "markets": "市场走势",
    "leaders": "龙头公司",
    "sectors": "行业轮动",
    "risk": "风险事件",
    "data-heavy": "关键数据",
    "high-impact": "高冲击",
}


def load_reports(latest_dir: Path) -> list[dict[str, object]]:
    return [json.loads((latest_dir / f"{market}.json").read_text(encoding="utf-8")) for market in MARKETS]


def signal_for(report: dict[str, object]) -> tuple[str, str, int]:
    items = list(report.get("items", []))
    top_score = max([float(item.get("score", 0)) for item in items] or [0])
    high_count = sum(1 for item in items if item.get("priority") in {"一级关注", "二级关注"})
    negative_count = sum(1 for item in items if item.get("stance") == "偏利空")
    heat = min(100, int(top_score + high_count * 4 + negative_count * 3))
    if heat >= 82:
        return "高热", "需要优先阅读", heat
    if heat >= 65:
        return "活跃", "有明显主线", heat
    return "观察", "信号分散", heat


def market_story(report: dict[str, object]) -> dict[str, object]:
    items = list(report.get("items", []))
    tags = Counter(tag for item in items for tag in item.get("tags", []))
    themes = [TAG_NAMES.get(tag, tag) for tag, _ in tags.most_common(3)]
    priority_items = [item for item in items if item.get("priority") in {"一级关注", "二级关注"}]
    negative = [item for item in items if item.get("stance") == "偏利空"]
    top = items[0] if items else {}
    signal, signal_note, heat = signal_for(report)
    return {
        "market": str(report.get("market", "")),
        "name": MARKET_NAMES.get(str(report.get("market", "")), str(report.get("market", ""))),
        "signal": signal,
        "signal_note": signal_note,
        "heat": heat,
        "themes": themes or ["暂无明显主线"],
        "what_happened": build_what_happened(top, themes, priority_items),
        "why_matters": build_why_matters(str(report.get("market", "")), priority_items, negative),
        "watch_next": build_watch_next(str(report.get("market", "")), themes, negative),
        "advice": str(report.get("advice", "")),
        "top_items": items[:3],
        "top_title": str(top.get("title", "暂无明确最高优先级事件")),
        "top_source": str(top.get("source", "未知来源")),
        "negative_count": len(negative),
        "priority_count": len(priority_items),
        "policy_macro": policy_macro_items(items),
        "equity_focus": None,
        "crypto_focus": None,
    }


def build_what_happened(top: dict[str, object], themes: list[str], priority_items: list[dict[str, object]]) -> str:
    theme_text = "、".join(themes[:3])
    events = priority_items[:3] or ([top] if top else [])
    lines = [f"主线：{theme_text}。高优先级事件 {len(priority_items)} 条。"]
    for index, item in enumerate(events, 1):
        source = str(item.get("source", "未知来源"))
        title = str(item.get("title", "暂无标题"))
        stance = str(item.get("stance", "待确认"))
        lines.append(f"{index}. {source}: {title}（{stance}）。")
    return "\n".join(lines)


def build_why_matters(market: str, priority_items: list[dict[str, object]], negative: list[dict[str, object]]) -> str:
    if market == "us_equities":
        base = "美股对利率预期、权重科技股和地缘风险更敏感，相关消息会先影响指数风险偏好。"
    elif market == "china_equities":
        base = "中国股市更看重政策兑现、流动性边际变化和行业轮动，单条消息需要结合资金面确认。"
    else:
        base = "加密市场会快速放大流动性、监管、ETF 和安全事件，短线价格容易先反应后修正。"
    if negative:
        return base + f" 当前有 {len(negative)} 条偏利空信号，说明消息面里已经出现风险项；重点判断它是个别事件，还是会扩散到资金流、监管预期或指数风险偏好。"
    if priority_items:
        return base + " 当前有高优先级事件，但方向未完全单边；如果价格、成交量和资金流没有同步确认，单条标题不应直接外推成趋势。"
    return base + " 当前更适合做背景跟踪，优先看是否出现新的政策、资金或龙头公司催化。"


def build_watch_next(market: str, themes: list[str], negative: list[dict[str, object]]) -> str:
    if market == "us_equities":
        watch = "预估事件：美债收益率、美元指数、纳指/标普期货和大型科技股开盘承接会先给方向。可能结果：若收益率回落且科技权重承接，偏利多；若收益率上行或地缘风险继续发酵，偏利空。"
    elif market == "china_equities":
        watch = "预估事件：政策口径、北向/港股资金反馈、核心行业轮动会决定持续性。可能结果：若政策预期配合放量上涨，偏利多；若高开低走或资金流出，偏利空。"
    else:
        watch = "预估事件：BTC/ETH 关键价位、ETF 资金流、交易所公告和链上安全事件会继续影响风险偏好。可能结果：若资金流入且安全事件不扩散，偏利多；若清算/黑客/监管标题增加，偏利空。"
    if negative:
        watch += " 当前已有偏利空标题，若同类消息继续增加，应把仓位防守放在第一位。"
    return watch


def policy_macro_items(items: list[dict[str, object]]) -> list[dict[str, str]]:
    output: list[dict[str, str]] = []
    for item in items:
        tags = set(item.get("tags", []))
        if not ({"macro", "policy"} & tags):
            continue
        stance = str(item.get("stance", "中性/待确认"))
        if stance == "偏利好":
            bias = "利多"
        elif stance == "偏利空":
            bias = "利空"
        else:
            bias = "待确认"
        output.append(
            {
                "bias": bias,
                "title": str(item.get("title", "")),
                "source": str(item.get("source", "")),
                "why": "宏观/政策变量会影响估值、风险偏好和资金流，需看价格是否同步确认。",
            }
        )
    return output[:5]


def enrich_stories_with_universe(stories: list[dict[str, object]], universe: dict[str, object]) -> list[dict[str, object]]:
    for story in stories:
        market = story.get("market")
        if market == "us_equities":
            story["equity_focus"] = equity_focus(universe.get("sp500", {}), "$")
        elif market == "china_equities":
            story["equity_focus"] = equity_focus(universe.get("csi500", {}), "¥")
        elif market == "crypto":
            story["crypto_focus"] = crypto_focus(universe)
    return stories


def equity_focus(raw: object, currency: str) -> dict[str, object]:
    payload = raw if isinstance(raw, dict) else {}
    return {
        "quote_count": payload.get("quote_count", 0),
        "gainers": list(payload.get("gainers", []))[:3],
        "losers": list(payload.get("losers", []))[:3],
        "currency": currency,
    }


def crypto_focus(universe: dict[str, object]) -> dict[str, object]:
    top100 = universe.get("crypto_top100", {})
    new_onchain = universe.get("new_onchain", {})
    rwa = universe.get("rwa", {})
    dex = universe.get("dex", {})
    return {
        "gainers": list(top100.get("gainers", [])) if isinstance(top100, dict) else [],
        "losers": list(top100.get("losers", [])) if isinstance(top100, dict) else [],
        "new_items": list(new_onchain.get("items", [])) if isinstance(new_onchain, dict) else [],
        "rwa_summary": rwa.get("summary", "") if isinstance(rwa, dict) else "",
        "dex_summary": dex.get("summary", "") if isinstance(dex, dict) else "",
        "rwa_items": list(rwa.get("items", [])) if isinstance(rwa, dict) else [],
        "dex_items": list(dex.get("items", [])) if isinstance(dex, dict) else [],
    }


def write_html(stories: list[dict[str, object]], universe: dict[str, object], path: Path) -> None:
    cards = "\n".join(render_market_card(story) for story in stories)
    radar = "\n".join(render_radar_card(story) for story in stories)
    universe_html = render_universe_html(universe)
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    path.write_text(
        f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>优化预览 - 每4小时金融情报</title>
  <style>
    :root {{
      --ink: #17202a;
      --muted: #667481;
      --line: #d9e2e8;
      --paper: #f3f6f8;
      --panel: #ffffff;
      --danger: #b42318;
      --warn: #b7791f;
      --blue: #2855d9;
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; background: var(--paper); color: var(--ink); font-family: Inter, -apple-system, BlinkMacSystemFont, "PingFang SC", "Microsoft YaHei", sans-serif; }}
    main {{ width: min(1120px, calc(100% - 32px)); margin: 0 auto; padding: 28px 0 48px; }}
    header {{ background: #ffffff; border: 1px solid var(--line); border-radius: 8px; padding: 24px; margin-bottom: 16px; }}
    .eyebrow {{ color: #087568; font-size: 12px; font-weight: 900; letter-spacing: .08em; }}
    h1 {{ margin: 8px 0 10px; font-size: 46px; line-height: 1.06; letter-spacing: 0; }}
    .lead {{ color: var(--muted); font-size: 16px; line-height: 1.75; max-width: 860px; }}
    .radar {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; margin: 0 0 16px; }}
    .radar-card {{ background: var(--panel); border: 1px solid var(--line); border-top: 4px solid var(--accent); border-radius: 8px; padding: 14px; min-height: 142px; }}
    .radar-top {{ display: flex; justify-content: space-between; align-items: baseline; gap: 12px; }}
    .radar-top b {{ font-size: 20px; }}
    .heat-number {{ color: var(--accent); font-size: 30px; font-weight: 900; font-variant-numeric: tabular-nums; }}
    .radar-card p {{ margin: 8px 0 0; color: var(--muted); line-height: 1.55; font-size: 13px; }}
    .grid {{ display: grid; gap: 18px; }}
    .market {{ --accent: #087568; --soft: #EAF4F2; --deep: #06483F; --on: #ffffff; background: var(--panel); border: 1px solid var(--line); border-radius: 8px; overflow: hidden; box-shadow: 0 10px 24px rgba(23, 32, 42, .05); }}
    .market-head {{ display: grid; grid-template-columns: 1fr 240px; gap: 18px; padding: 18px 20px; border-bottom: 1px solid var(--line); background: var(--accent); color: var(--on); }}
    h2 {{ margin: 0 0 10px; font-size: 28px; letter-spacing: 0; color: var(--on); }}
    .chips {{ display: flex; gap: 8px; flex-wrap: wrap; }}
    .chip {{ border: 1px solid rgba(255,255,255,.45); background: rgba(255,255,255,.12); color: var(--on); padding: 4px 9px; border-radius: 999px; font-size: 12px; font-weight: 800; }}
    .gauge {{ align-self: center; }}
    .gauge-row {{ display: flex; justify-content: space-between; color: var(--on); font-size: 12px; margin-bottom: 6px; opacity: .95; }}
    .bar {{ height: 10px; background: rgba(255,255,255,.22); border-radius: 999px; overflow: hidden; }}
    .bar span {{ display: block; height: 100%; background: var(--on); }}
    .topline {{ margin-top: 12px; color: var(--on); line-height: 1.55; opacity: .92; }}
    .body {{ display: grid; grid-template-columns: .86fr 1.14fr; gap: 18px; padding: 18px; }}
    .brief {{ display: grid; gap: 12px; align-content: start; }}
    .brief-block {{ border: 1px solid var(--line); border-left: 4px solid var(--accent); border-radius: 8px; padding: 12px; background: #fbfcfd; }}
    .brief-block b {{ display: block; margin-bottom: 5px; color: var(--deep); }}
    .brief-block p {{ margin: 0; color: var(--muted); line-height: 1.65; font-size: 14px; white-space: pre-line; }}
    .events {{ display: grid; gap: 10px; }}
    .event {{ border: 1px solid var(--line); border-radius: 8px; padding: 13px; background: #ffffff; }}
    .event:first-child {{ border-color: color-mix(in srgb, var(--accent) 34%, #ffffff); background: var(--soft); }}
    .event-meta {{ display: flex; flex-wrap: wrap; gap: 8px; color: var(--muted); font-size: 12px; margin-bottom: 6px; }}
    .event-meta strong {{ color: #ffffff; background: var(--accent); border-radius: 999px; padding: 2px 8px; }}
    .event h3 {{ margin: 0 0 7px; font-size: 16px; line-height: 1.35; letter-spacing: 0; }}
    .event p {{ margin: 0; color: var(--muted); line-height: 1.55; }}
    .note {{ margin-top: 18px; color: var(--muted); font-size: 12px; }}
    .universe {{ margin-top: 18px; display: grid; gap: 14px; }}
    .universe h2 {{ color: var(--ink); margin: 8px 0 0; }}
    .data-grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }}
    .data-card {{ background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 14px; }}
    .data-card h3 {{ margin: 0 0 8px; font-size: 18px; letter-spacing: 0; }}
    .data-card p {{ margin: 0 0 10px; color: var(--muted); line-height: 1.55; }}
    .mini-table {{ width: 100%; border-collapse: collapse; font-size: 12px; }}
    .mini-table th {{ text-align: left; color: var(--muted); border-bottom: 1px solid var(--line); padding: 6px 4px; }}
    .mini-table td {{ border-bottom: 1px solid #edf1f4; padding: 6px 4px; vertical-align: top; }}
    .pill-line {{ display: flex; flex-wrap: wrap; gap: 6px; }}
    .pill-line span {{ background: #f2f6f8; border: 1px solid var(--line); border-radius: 999px; padding: 3px 8px; color: var(--muted); font-size: 12px; }}
    @media (max-width: 860px) {{ .radar, .market-head, .body, .data-grid {{ grid-template-columns: 1fr; }} h1 {{ font-size: 34px; }} }}
  </style>
</head>
<body>
<main>
  <header>
    <div class="eyebrow">READABLE PREVIEW</div>
    <h1>每4小时金融情报 - VP 阅读版</h1>
    <p class="lead">生成时间：{html.escape(now)}。这版面向持续关注市场动态的投行 VP：先过滤，再汇报；优先给结论、影响路径、可能结果和需要盯的变量。</p>
  </header>
  <section class="radar">{radar}</section>
  <section class="grid">{cards}</section>
  {universe_html}
  <p class="note">说明：这是自动资讯整理与规则化点评，不构成投资建议。标题保留来源原文，观点为系统基于优先级、标签和风险信号生成。</p>
</main>
</body>
</html>""",
        encoding="utf-8",
    )


def render_market_card(story: dict[str, object]) -> str:
    chips = "".join(f'<span class="chip">{html.escape(str(theme))}</span>' for theme in story["themes"])
    events = "\n".join(render_decision_card(index + 1, card, story) for index, card in enumerate(decision_cards(story)))
    colors_for_market = MARKET_COLORS.get(str(story["market"]), MARKET_COLORS["china_equities"])
    return f"""
    <article class="market" style="--accent:{colors_for_market['accent']};--soft:{colors_for_market['soft']};--deep:{colors_for_market['deep']};--on:{colors_for_market['on']}">
      <div class="market-head">
        <div>
          <h2>{html.escape(str(story["name"]))}</h2>
          <div class="chips">{chips}</div>
          <div class="topline">本小时最需要先看的事件：{html.escape(str(story["top_title"]))}</div>
        </div>
        <div class="gauge">
          <div class="gauge-row"><b>{html.escape(str(story["signal"]))}</b><span>{html.escape(str(story["signal_note"]))}</span></div>
          <div class="bar"><span style="width:{int(story["heat"])}%"></span></div>
        </div>
      </div>
      <div class="body">
        <div class="brief">
          <div class="brief-block"><b>发生了什么</b><p>{html.escape(str(story["what_happened"]))}</p></div>
          <div class="brief-block"><b>为什么重要</b><p>{html.escape(str(story["why_matters"]))}</p></div>
          <div class="brief-block"><b>接下来盯什么</b><p>{html.escape(str(story["watch_next"]))}</p></div>
        </div>
        <div class="events">{events}</div>
      </div>
    </article>
    """


def decision_cards(story: dict[str, object]) -> list[dict[str, str]]:
    if isinstance(story.get("equity_focus"), dict):
        focus = story["equity_focus"]
        currency = str(focus.get("currency", ""))
        return [
            {
                "label": "领涨企业",
                "title": "谁在带动风险偏好",
                "body": plain_mover_line("领涨", list(focus.get("gainers", [])), currency),
            },
            {
                "label": "领跌企业",
                "title": "哪里在释放压力",
                "body": plain_mover_line("领跌", list(focus.get("losers", [])), currency),
            },
            {
                "label": "政策 / 宏观",
                "title": "利多、利空与待确认",
                "body": plain_policy_macro_text(story),
            },
        ]
    if isinstance(story.get("crypto_focus"), dict):
        focus = story["crypto_focus"]
        return [
            {
                "label": "Top100 代币",
                "title": "非稳定币头部资产温度",
                "body": "领涨: " + "、".join(focus.get("gainers", [])[:5]) + "；领跌: " + "、".join(focus.get("losers", [])[:5]),
            },
            {
                "label": "新上链观察",
                "title": "尚未充分二级市场定价的线索",
                "body": format_new_onchain_text(list(focus.get("new_items", []))),
            },
            {
                "label": "RWA / DEX",
                "title": "链上真实资产与交易活跃度",
                "body": f"{focus.get('rwa_summary', '')} {focus.get('dex_summary', '')}",
            },
        ]
    return [
        {
            "label": str(item.get("priority", "")),
            "title": str(item.get("title", "")),
            "body": str(item.get("summary", "")),
        }
        for item in list(story.get("top_items", []))[:3]
    ]


def render_decision_card(index: int, card: dict[str, str], story: dict[str, object]) -> str:
    return f"""
    <div class="event">
      <div class="event-meta">
        <strong>{index}</strong>
        <span>{html.escape(card.get("label", ""))}</span>
      </div>
      <h3>{html.escape(card.get("title", ""))}</h3>
      <p>{html.escape(card.get("body", ""))}</p>
    </div>
    """


def render_equity_focus_html(story: dict[str, object]) -> str:
    focus = story.get("equity_focus")
    if not isinstance(focus, dict):
        return ""
    currency = str(focus.get("currency", ""))
    gainers = focus.get("gainers", []) if isinstance(focus.get("gainers", []), list) else []
    losers = focus.get("losers", []) if isinstance(focus.get("losers", []), list) else []
    return f"""
    <div class="brief-block">
      <b>领涨 / 领跌企业</b>
      <p>{render_mover_lines("领涨", gainers, currency)}<br>{render_mover_lines("领跌", losers, currency)}</p>
    </div>
    """


def render_mover_lines(label: str, rows: list[object], currency: str) -> str:
    if not rows:
        return f"{label}: 暂无可用报价。"
    parts = []
    for item in rows[:3]:
        if not isinstance(item, dict):
            continue
        parts.append(
            f"{item.get('name')} ({item.get('symbol')}): {price(item.get('price'), currency)} / {pct(item.get('change_pct'))}，原因：{item.get('reason')}"
        )
    return html.escape(f"{label}: " + "；".join(parts))


def format_new_onchain_text(rows: list[object]) -> str:
    if not rows:
        return "暂无可用新上链观察数据。"
    parts = []
    for item in rows[:5]:
        if not isinstance(item, dict):
            continue
        parts.append(f"{item.get('name')}({item.get('category')}/{item.get('chain')}) - {item.get('secondary_hint')}")
    return "；".join(parts)


def render_policy_macro_html(story: dict[str, object]) -> str:
    rows = story.get("policy_macro", [])
    if not isinstance(rows, list) or not rows:
        return """
        <div class="brief-block"><b>政策 / 宏观</b><p>本小时暂无明确政策或宏观高权重信号，暂按待确认处理。</p></div>
        """
    lines = []
    for item in rows[:4]:
        if not isinstance(item, dict):
            continue
        lines.append(f"{item.get('bias')}: {item.get('title')}。解读：{item.get('why')}")
    return f"""
    <div class="brief-block">
      <b>政策 / 宏观：利多还是利空</b>
      <p>{html.escape('；'.join(lines))}</p>
    </div>
    """


def plain_policy_macro_text(story: dict[str, object]) -> str:
    rows = story.get("policy_macro", [])
    if not isinstance(rows, list) or not rows:
        return "本阶段暂无明确政策或宏观高权重信号，暂按待确认处理。"
    parts = []
    for item in rows[:5]:
        if not isinstance(item, dict):
            continue
        parts.append(f"{item.get('bias')}: {item.get('title')}。解读：{item.get('why')}")
    return "；".join(parts)


def render_radar_card(story: dict[str, object]) -> str:
    colors_for_market = MARKET_COLORS.get(str(story["market"]), MARKET_COLORS["china_equities"])
    themes = "、".join(str(theme) for theme in story["themes"][:2])
    return f"""
    <article class="radar-card" style="--accent:{colors_for_market['accent']}">
      <div class="radar-top">
        <b>{html.escape(str(story["name"]))}</b>
        <span class="heat-number">{int(story["heat"])}</span>
      </div>
      <div class="bar"><span style="width:{int(story["heat"])}%"></span></div>
      <p>{html.escape(str(story["signal"]))}。主线：{html.escape(themes)}。高优先级 {int(story["priority_count"])} 条，偏利空 {int(story["negative_count"])} 条。</p>
    </article>
    """


def render_universe_html(universe: dict[str, object]) -> str:
    return f"""
    <section class="universe">
      <h2>底层数据雷达</h2>
      <div class="data-grid">
        {render_equity_universe_card(universe.get("sp500", {}), "美股 - S&P 500 成分股", ["symbol", "name", "sector"])}
        {render_equity_universe_card(universe.get("csi500", {}), "中股 - 中证 500 成分股", ["symbol", "name", "exchange"])}
        {render_crypto_card(universe.get("crypto_top100", {}))}
        {render_new_onchain_card(universe.get("new_onchain", {}))}
        {render_rwa_card(universe.get("rwa", {}))}
        {render_dex_card(universe.get("dex", {}))}
      </div>
    </section>
    """


def render_equity_universe_card(data: object, title: str, columns: list[str]) -> str:
    payload = data if isinstance(data, dict) else {}
    rows = payload.get("items", []) if isinstance(payload.get("items", []), list) else []
    summary = payload.get("summary") or payload.get("error") or "数据暂不可用。"
    table_rows = "".join(
        "<tr>" + "".join(f"<td>{html.escape(str(item.get(column, '')))}</td>" for column in columns) + "</tr>"
        for item in rows[:8]
        if isinstance(item, dict)
    )
    headers = "".join(f"<th>{html.escape(column)}</th>" for column in columns)
    return f"""
    <article class="data-card">
      <h3>{html.escape(title)}</h3>
      <p>{html.escape(str(summary))}</p>
      <table class="mini-table"><thead><tr>{headers}</tr></thead><tbody>{table_rows}</tbody></table>
    </article>
    """


def render_crypto_card(data: object) -> str:
    payload = data if isinstance(data, dict) else {}
    rows = payload.get("items", []) if isinstance(payload.get("items", []), list) else []
    gainers = payload.get("gainers", []) if isinstance(payload.get("gainers", []), list) else []
    losers = payload.get("losers", []) if isinstance(payload.get("losers", []), list) else []
    table_rows = "".join(
        f"<tr><td>{item.get('rank')}</td><td>{html.escape(str(item.get('symbol')))}</td><td>{html.escape(str(item.get('name')))}</td><td>{pct(item.get('change_24h'))}</td><td>{money(item.get('market_cap'))}</td></tr>"
        for item in rows[:8]
        if isinstance(item, dict)
    )
    pills = "".join(f"<span>{html.escape(str(item))}</span>" for item in gainers[:5] + losers[:5])
    return f"""
    <article class="data-card">
      <h3>加密 - 非稳定币市值 Top 100</h3>
      <p>{html.escape(str(payload.get("summary") or payload.get("error") or "数据暂不可用。"))}</p>
      <div class="pill-line">{pills}</div>
      <table class="mini-table"><thead><tr><th>Rank</th><th>Symbol</th><th>Name</th><th>24h</th><th>MCap</th></tr></thead><tbody>{table_rows}</tbody></table>
    </article>
    """


def render_new_onchain_card(data: object) -> str:
    payload = data if isinstance(data, dict) else {}
    rows = payload.get("items", []) if isinstance(payload.get("items", []), list) else []
    table_rows = "".join(
        f"<tr><td>{html.escape(str(item.get('name')))}</td><td>{html.escape(str(item.get('category')))}</td><td>{html.escape(str(item.get('chain')))}</td><td>{html.escape(str(item.get('secondary_hint')))}</td></tr>"
        for item in rows[:10]
        if isinstance(item, dict)
    )
    return f"""
    <article class="data-card">
      <h3>新上链 / 未进入二级市场观察</h3>
      <p>{html.escape(str(payload.get("summary") or payload.get("error") or "数据暂不可用。"))}</p>
      <table class="mini-table"><thead><tr><th>项目</th><th>赛道</th><th>链</th><th>状态线索</th></tr></thead><tbody>{table_rows}</tbody></table>
    </article>
    """


def render_rwa_card(data: object) -> str:
    payload = data if isinstance(data, dict) else {}
    rows = payload.get("items", []) if isinstance(payload.get("items", []), list) else []
    table_rows = "".join(
        f"<tr><td>{html.escape(str(item.get('name')))}</td><td>{html.escape(str(item.get('chain')))}</td><td>{money(item.get('tvl'))}</td><td>{pct(item.get('change_7d'))}</td></tr>"
        for item in rows[:8]
        if isinstance(item, dict)
    )
    return f"""
    <article class="data-card">
      <h3>RWA 赛道</h3>
      <p>{html.escape(str(payload.get("summary") or payload.get("error") or "数据暂不可用。"))}</p>
      <table class="mini-table"><thead><tr><th>协议</th><th>链</th><th>TVL</th><th>7d</th></tr></thead><tbody>{table_rows}</tbody></table>
    </article>
    """


def render_dex_card(data: object) -> str:
    payload = data if isinstance(data, dict) else {}
    rows = payload.get("items", []) if isinstance(payload.get("items", []), list) else []
    table_rows = "".join(
        f"<tr><td>{html.escape(str(item.get('name')))}</td><td>{html.escape(str(item.get('chains')))}</td><td>{money(item.get('volume_24h'))}</td><td>{pct(item.get('change_1d'))}</td></tr>"
        for item in rows[:8]
        if isinstance(item, dict)
    )
    return f"""
    <article class="data-card">
      <h3>主流 DEX 交易所</h3>
      <p>{html.escape(str(payload.get("summary") or payload.get("error") or "数据暂不可用。"))}</p>
      <table class="mini-table"><thead><tr><th>DEX</th><th>链</th><th>24h</th><th>1d</th></tr></thead><tbody>{table_rows}</tbody></table>
    </article>
    """


def render_event(item: dict[str, object]) -> str:
    summary = str(item.get("summary", ""))[:180]
    return f"""
    <div class="event">
      <div class="event-meta">
        <strong>{html.escape(str(item.get("priority", "")))}</strong>
        <span>评分 {html.escape(str(item.get("score", "")))}</span>
        <span>{html.escape(str(item.get("source", "")))}</span>
        <span>{html.escape(str(item.get("stance", "")))}</span>
      </div>
      <h3>{html.escape(str(item.get("title", "")))}</h3>
      <p>{html.escape(summary)}</p>
    </div>
    """


def write_pdf(stories: list[dict[str, object]], universe: dict[str, object], path: Path) -> None:
    register_pdf_font()
    base = getSampleStyleSheet()
    styles = {
        "title": ParagraphStyle("ReadableTitle", parent=base["Title"], fontName=PDF_FONT_NAME, fontSize=21, leading=26, textColor=colors.HexColor("#17202A"), alignment=TA_CENTER),
        "lead": ParagraphStyle("ReadableLead", parent=base["BodyText"], fontName=PDF_FONT_NAME, fontSize=9.2, leading=13.5, textColor=colors.HexColor("#667481"), alignment=TA_CENTER),
        "h2": ParagraphStyle("ReadableH2", parent=base["Heading2"], fontName=PDF_FONT_NAME, fontSize=14.5, leading=18, textColor=colors.HexColor("#17202A"), spaceBefore=8),
        "body": ParagraphStyle("ReadableBody", parent=base["BodyText"], fontName=PDF_FONT_NAME, fontSize=8.4, leading=12.2, textColor=colors.HexColor("#17202A")),
        "small": ParagraphStyle("ReadableSmall", parent=base["BodyText"], fontName=PDF_FONT_NAME, fontSize=7.3, leading=10.3, textColor=colors.HexColor("#667481")),
        "white": ParagraphStyle("ReadableWhite", parent=base["BodyText"], fontName=PDF_FONT_NAME, fontSize=8.2, leading=12.5, textColor=colors.white, alignment=TA_CENTER),
        "yellow": ParagraphStyle("ReadableYellow", parent=base["BodyText"], fontName=PDF_FONT_NAME, fontSize=8.2, leading=12.5, textColor=colors.HexColor("#FFE082"), alignment=TA_CENTER),
    }
    doc = SimpleDocTemplate(str(path), pagesize=A4, rightMargin=14 * mm, leftMargin=14 * mm, topMargin=13 * mm, bottomMargin=13 * mm)
    story = [
        Paragraph("每4小时金融情报 - VP 阅读版", styles["title"]),
        Paragraph(f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}。结构：市场温度、具体事项、影响解读、预估事件、领涨领跌、政策宏观判断。", styles["lead"]),
        Spacer(1, 8),
        pdf_radar(stories, styles),
        Spacer(1, 8),
    ]
    for item in stories:
        story.extend(pdf_market_section(item, styles))
    story.extend(pdf_universe_section(universe, styles))
    story.append(Paragraph("说明：自动资讯整理与规则化点评，不构成投资建议。", styles["small"]))
    doc.build(story)


def pdf_radar(stories: list[dict[str, object]], styles: dict[str, ParagraphStyle]) -> Table:
    cells = []
    for story in stories:
        market = str(story["market"])
        colors_for_market = MARKET_COLORS.get(market, MARKET_COLORS["china_equities"])
        themes = "、".join(str(theme) for theme in story["themes"][:2])
        radar_style = styles["yellow"] if story.get("market") == "china_equities" else styles["white"]
        cells.append(
            Paragraph(
                f"<b>{story['name']}</b><br/>热度 {int(story['heat'])}/100<br/>{story['signal']} | {themes}",
                radar_style,
            )
        )
    table = Table([cells], colWidths=[60 * mm, 60 * mm, 60 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, 0), colors.HexColor(MARKET_COLORS["us_equities"]["accent"])),
                ("BACKGROUND", (1, 0), (1, 0), colors.HexColor(MARKET_COLORS["china_equities"]["accent"])),
                ("BACKGROUND", (2, 0), (2, 0), colors.HexColor(MARKET_COLORS["crypto"]["accent"])),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    return table


def pdf_market_section(story: dict[str, object], styles: dict[str, ParagraphStyle]) -> list[object]:
    heat = int(story["heat"])
    colors_for_market = MARKET_COLORS.get(str(story["market"]), MARKET_COLORS["china_equities"])
    rows = [
        [
            Paragraph("<b>发生了什么</b>", styles["small"]),
            Paragraph(str(story["what_happened"]), styles["small"]),
        ],
        [
            Paragraph("<b>为什么重要</b>", styles["small"]),
            Paragraph(str(story["why_matters"]), styles["small"]),
        ],
        [
            Paragraph("<b>接下来盯什么</b>", styles["small"]),
            Paragraph(str(story["watch_next"]), styles["small"]),
        ],
    ]
    table = Table(rows, colWidths=[24 * mm, 156 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor(colors_for_market["soft"])),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LINEBELOW", (0, 0), (-1, -2), 0.4, colors.HexColor("#D9E2E8")),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    output: list[object] = [
        Paragraph(f"{story['name']} | {story['signal']} | 热度 {heat}/100 | 主线：{'、'.join(story['themes'])}", styles["h2"]),
        table,
        Spacer(1, 6),
    ]
    for index, card in enumerate(decision_cards(story), 1):
        number_style = styles["yellow"] if story.get("market") == "china_equities" else styles["white"]
        event_table = Table(
            [
                [
                    Paragraph(f"<b>{index}</b>", number_style),
                    Paragraph(
                        f"<b>{html.escape(str(card.get('label', '')))} | {html.escape(str(card.get('title', '')))}</b><br/>"
                        f"{html.escape(str(card.get('body', ''))[:520])}",
                        styles["small"],
                    ),
                ]
            ],
            colWidths=[10 * mm, 170 * mm],
        )
        event_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (0, 0), colors.HexColor(colors_for_market["accent"])),
                    ("BACKGROUND", (1, 0), (1, 0), colors.HexColor("#FBFCFD")),
                    ("BOX", (0, 0), (-1, -1), 0.4, colors.HexColor("#D9E2E8")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 5),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ]
            )
        )
        output.append(event_table)
        output.append(Spacer(1, 4))
    output.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#D9E2E8"), spaceBefore=3, spaceAfter=5))
    return output


def pdf_movers_text(focus: dict[str, object]) -> str:
    currency = str(focus.get("currency", ""))
    gainers = focus.get("gainers", []) if isinstance(focus.get("gainers", []), list) else []
    losers = focus.get("losers", []) if isinstance(focus.get("losers", []), list) else []
    return html.escape(f"{plain_mover_line('领涨', gainers, currency)}\n{plain_mover_line('领跌', losers, currency)}")


def plain_mover_line(label: str, rows: list[object], currency: str) -> str:
    if not rows:
        return f"{label}: 暂无可用报价。"
    parts = []
    for item in rows[:2]:
        if not isinstance(item, dict):
            continue
        parts.append(
            f"{item.get('name')}({item.get('symbol')}) {price(item.get('price'), currency)} {pct(item.get('change_pct'))}，原因：{item.get('reason')}"
        )
    return f"{label}: " + "；".join(parts)


def pdf_policy_macro_text(story: dict[str, object]) -> str:
    rows = story.get("policy_macro", [])
    if not isinstance(rows, list) or not rows:
        return "暂无明确政策或宏观高权重信号，暂按待确认处理。"
    lines = []
    for item in rows[:3]:
        if not isinstance(item, dict):
            continue
        lines.append(f"{item.get('bias')}: {item.get('title')}。解读：{item.get('why')}")
    return html.escape("\n".join(lines))


def pdf_universe_section(universe: dict[str, object], styles: dict[str, ParagraphStyle]) -> list[object]:
    sections = [
        ("美股 - S&P 500", universe.get("sp500", {}), "items", ["symbol", "name", "sector"]),
        ("中股 - 中证 500", universe.get("csi500", {}), "items", ["symbol", "name", "exchange"]),
        ("加密 Top100", universe.get("crypto_top100", {}), "items", ["rank", "symbol", "name", "change_24h"]),
        ("新上链/未二级市场", universe.get("new_onchain", {}), "items", ["name", "category", "chain", "secondary_hint"]),
        ("RWA", universe.get("rwa", {}), "items", ["name", "chain", "tvl", "change_7d"]),
        ("DEX", universe.get("dex", {}), "items", ["name", "chains", "volume_24h", "change_1d"]),
    ]
    output: list[object] = [
        Paragraph("底层数据雷达", styles["h2"]),
        Paragraph("以下模块用于支撑后续自动推送：成分股池、非稳定币 Top100、新上链观察、RWA 与 DEX 数据。", styles["small"]),
        Spacer(1, 5),
    ]
    for title, raw_payload, key, columns in sections:
        payload = raw_payload if isinstance(raw_payload, dict) else {}
        output.append(Paragraph(f"<b>{html.escape(title)}</b> - {html.escape(str(payload.get('summary') or payload.get('error') or '数据暂不可用。'))}", styles["small"]))
        rows = [[Paragraph(f"<b>{column}</b>", styles["small"]) for column in columns]]
        for item in list(payload.get(key, []))[:5]:
            if not isinstance(item, dict):
                continue
            rows.append([Paragraph(format_pdf_cell(item.get(column)), styles["small"]) for column in columns])
        table = Table(rows, colWidths=[30 * mm, 50 * mm, 55 * mm, 45 * mm][: len(columns)])
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EEF3F6")),
                    ("BOX", (0, 0), (-1, -1), 0.35, colors.HexColor("#D9E2E8")),
                    ("LINEBELOW", (0, 0), (-1, -2), 0.25, colors.HexColor("#E4EAEE")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 4),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        output.extend([Spacer(1, 3), table, Spacer(1, 6)])
    return output


def format_pdf_cell(value: object) -> str:
    if isinstance(value, (int, float)) and abs(float(value)) > 100000:
        return money(float(value))
    if isinstance(value, float):
        return f"{value:.2f}"
    return html.escape(str(value if value is not None else ""))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a readable preview report from latest market JSON")
    parser.add_argument("--latest-dir", type=Path, default=DEFAULT_OUTPUT / "latest")
    parser.add_argument("--output-dir", type=Path, default=DESKTOP_REPORT_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    reports = load_reports(args.latest_dir)
    universe = build_universe_snapshot()
    stories = enrich_stories_with_universe([market_story(report) for report in reports], universe)
    html_path = args.output_dir / "样式预览_阅读型金融情报.html"
    pdf_path = args.output_dir / "样式预览_阅读型金融情报.pdf"
    write_html(stories, universe, html_path)
    write_pdf(stories, universe, pdf_path)
    print(json.dumps({"html": str(html_path), "pdf": str(pdf_path)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
