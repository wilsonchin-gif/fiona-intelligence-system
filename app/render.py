from __future__ import annotations

import html
import json
from datetime import datetime
from pathlib import Path

from app.models import MarketReport


def write_reports(reports: list[MarketReport], output_dir: Path) -> None:
    latest_dir = output_dir / "latest"
    archive_dir = output_dir / "archive" / datetime.now().strftime("%Y-%m-%d") / datetime.now().strftime("%H00")
    latest_dir.mkdir(parents=True, exist_ok=True)
    archive_dir.mkdir(parents=True, exist_ok=True)

    for report in reports:
        html_text = render_market_report(report)
        json_text = json.dumps(report.to_dict(), ensure_ascii=False, indent=2)
        for base in (latest_dir, archive_dir):
            (base / f"{report.market}.html").write_text(html_text, encoding="utf-8")
            (base / f"{report.market}.json").write_text(json_text, encoding="utf-8")
    (latest_dir / "index.html").write_text(render_index(reports), encoding="utf-8")


def render_index(reports: list[MarketReport]) -> str:
    cards = "\n".join(
        f"""
        <a class="market-card" href="{report.market}.html">
          <span>{escape(report.title)}</span>
          <strong>{len(report.items)}</strong>
          <small>{escape(report.briefing[:90])}</small>
        </a>
        """
        for report in reports
    )
    return page_shell(
        "每日金融情报台",
        f"""
        <main class="hub">
          <section class="hero">
            <p class="eyebrow">HOURLY MARKET INTELLIGENCE</p>
            <h1>每日金融情报台</h1>
            <p>每小时聚合美国股市、中国股市与加密货币市场动态，按影响力排序并生成客观点评。</p>
          </section>
          <section class="market-grid">{cards}</section>
        </main>
        """,
    )


def render_market_report(report: MarketReport) -> str:
    items_html = "\n".join(render_item(index + 1, item) for index, item in enumerate(report.items))
    risks = "\n".join(f"<li>{escape(flag)}</li>" for flag in report.risk_flags) or "<li>暂无高优先级偏利空信号。</li>"
    return page_shell(
        report.title,
        f"""
        <main class="report">
          <header class="report-header">
            <a class="back" href="index.html">← 返回总览</a>
            <p class="eyebrow">生成时间 {escape(report.generated_at.astimezone().strftime('%Y-%m-%d %H:%M:%S %Z'))}</p>
            <h1>{escape(report.title)}</h1>
            <p>{escape(report.briefing)}</p>
          </header>
          <section class="summary-band">
            <div>
              <span>客观建议</span>
              <strong>{escape(report.advice)}</strong>
            </div>
            <div>
              <span>风险提示</span>
              <ul>{risks}</ul>
            </div>
          </section>
          <section class="ticker-list">{items_html}</section>
        </main>
        """,
    )


def render_item(index: int, item) -> str:
    tags = "".join(f"<span>{escape(tag)}</span>" for tag in item.tags) or "<span>general</span>"
    reasons = "".join(f"<li>{escape(reason)}</li>" for reason in item.reasons)
    summary = f"<p>{escape(item.summary[:260])}</p>" if item.summary else ""
    return f"""
    <article class="news-item priority-{escape(item.priority)}">
      <div class="rank">{index:02d}</div>
      <div class="content">
        <div class="meta">
          <strong>{escape(item.priority)}</strong>
          <span>{escape(item.source)}</span>
          <span>{escape(item.published_at.astimezone().strftime('%H:%M'))}</span>
          <span>{escape(item.stance)}</span>
          <span>Score {item.score:.1f}</span>
        </div>
        <h2><a href="{escape(item.url)}" target="_blank" rel="noreferrer">{escape(item.title)}</a></h2>
        {summary}
        <div class="tags">{tags}</div>
        <ul class="reasons">{reasons}</ul>
      </div>
    </article>
    """


def page_shell(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)}</title>
  <style>
    :root {{
      color-scheme: light;
      --ink: #17202a;
      --muted: #5f6c78;
      --line: #d9e0e7;
      --paper: #f7f9fb;
      --panel: #ffffff;
      --accent: #0f766e;
      --hot: #b42318;
      --warn: #b7791f;
      --cool: #1f5eff;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "PingFang SC", "Microsoft YaHei", sans-serif;
      color: var(--ink);
      background: var(--paper);
    }}
    a {{ color: inherit; text-decoration: none; }}
    .hub, .report {{ width: min(1180px, calc(100% - 32px)); margin: 0 auto; padding: 28px 0 44px; }}
    .hero, .report-header {{ padding: 30px 0 24px; border-bottom: 1px solid var(--line); }}
    .eyebrow {{ color: var(--accent); font-size: 12px; font-weight: 800; letter-spacing: .08em; margin: 0 0 10px; }}
    h1 {{ font-size: clamp(34px, 5vw, 68px); line-height: 1.02; margin: 0 0 16px; letter-spacing: 0; }}
    .hero p, .report-header p:last-child {{ max-width: 780px; color: var(--muted); font-size: 18px; line-height: 1.7; }}
    .market-grid {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 14px; margin-top: 18px; }}
    .market-card {{ background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 18px; min-height: 180px; display: grid; gap: 10px; }}
    .market-card span {{ font-weight: 800; }}
    .market-card strong {{ font-size: 52px; color: var(--accent); }}
    .market-card small {{ color: var(--muted); line-height: 1.55; }}
    .back {{ display: inline-flex; align-items: center; color: var(--muted); margin-bottom: 18px; }}
    .summary-band {{ display: grid; grid-template-columns: 1.25fr .75fr; gap: 14px; margin: 18px 0; }}
    .summary-band > div {{ background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 18px; }}
    .summary-band span {{ display: block; color: var(--muted); font-size: 13px; margin-bottom: 8px; }}
    .summary-band strong {{ font-size: 18px; line-height: 1.7; }}
    .summary-band ul {{ margin: 0; padding-left: 18px; color: var(--muted); line-height: 1.65; }}
    .ticker-list {{ display: grid; gap: 10px; }}
    .news-item {{ display: grid; grid-template-columns: 58px 1fr; gap: 14px; background: var(--panel); border: 1px solid var(--line); border-left: 5px solid var(--cool); border-radius: 8px; padding: 14px; }}
    .priority-一级关注 {{ border-left-color: var(--hot); }}
    .priority-二级关注 {{ border-left-color: var(--warn); }}
    .rank {{ font-size: 24px; font-weight: 900; color: var(--muted); font-variant-numeric: tabular-nums; }}
    .meta {{ display: flex; flex-wrap: wrap; gap: 8px; color: var(--muted); font-size: 12px; align-items: center; }}
    .meta strong {{ color: var(--hot); }}
    .news-item h2 {{ font-size: 20px; line-height: 1.35; margin: 8px 0; letter-spacing: 0; }}
    .news-item p {{ color: var(--muted); line-height: 1.65; margin: 0 0 10px; }}
    .tags {{ display: flex; flex-wrap: wrap; gap: 6px; margin: 8px 0; }}
    .tags span {{ border: 1px solid var(--line); border-radius: 999px; padding: 3px 8px; color: var(--accent); font-size: 12px; }}
    .reasons {{ color: var(--muted); display: grid; gap: 4px; margin: 8px 0 0; padding-left: 18px; line-height: 1.5; }}
    @media (max-width: 780px) {{
      .market-grid, .summary-band {{ grid-template-columns: 1fr; }}
      .news-item {{ grid-template-columns: 1fr; }}
      .rank {{ font-size: 16px; }}
      h1 {{ font-size: 38px; }}
    }}
  </style>
</head>
<body>
{body}
</body>
</html>"""


def escape(value: object) -> str:
    return html.escape(str(value), quote=True)

