from __future__ import annotations

import argparse
import json
import os
import subprocess
from datetime import datetime
from pathlib import Path
from textwrap import shorten

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import registerFont
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.main import DEFAULT_CONFIG, DEFAULT_OUTPUT, run_once

ROOT = Path(__file__).resolve().parent.parent
DESKTOP_REPORT_DIR = Path.home() / "Desktop" / "每日金融情报报表"
BUNDLED_NODE = Path("/Users/mac/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node")
EXCEL_BUILDER = ROOT / "tools" / "build_desktop_excel.mjs"
PDF_FONT_NAME = "FinancialDailySans"
PDF_FONT_PATHS = [
    Path("/System/Library/Fonts/STHeiti Medium.ttc"),
    Path("/System/Library/Fonts/Supplemental/Songti.ttc"),
    Path("/System/Library/Fonts/Hiragino Sans GB.ttc"),
    Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf"),
]
PDF_FONT_REGISTERED = False

MARKET_LABELS = {
    "cn": {
        "us_equities": "美国股市",
        "china_equities": "中国股市",
        "crypto": "加密货币",
    },
    "en": {
        "us_equities": "US Equities",
        "china_equities": "China Equities",
        "crypto": "Crypto",
    },
}

TEXT = {
    "cn": {
        "title": "每小时金融情报简报",
        "subtitle": "美国股市 / 中国股市 / 加密货币",
        "briefing": "核心摘要",
        "advice": "客观建议",
        "risks": "风险提示",
        "top": "重点动态",
        "none": "暂无高优先级风险提示。",
        "columns": ["级别", "评分", "来源", "倾向", "标题", "排序理由"],
        "note": "说明：本报表为自动资讯整理和规则化点评，不构成投资建议。",
    },
    "en": {
        "title": "Hourly Financial Intelligence Brief",
        "subtitle": "US Equities / China Equities / Crypto",
        "briefing": "Executive Briefing",
        "advice": "Objective View",
        "risks": "Risk Flags",
        "top": "Top Updates",
        "none": "No high-priority negative risk flags.",
        "columns": ["Priority", "Score", "Source", "Stance", "Headline", "Ranking Reasons"],
        "note": "Note: This report is an automated news digest with rules-based commentary. It is not investment advice.",
    },
}


def export_desktop_reports(config: Path, reports_root: Path, desktop_dir: Path) -> dict[str, object]:
    status = run_once(config, reports_root, limit=18)
    latest_dir = reports_root / "latest"
    reports = load_latest_reports(latest_dir)
    desktop_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    written: list[str] = []
    for lang in ("cn", "en"):
        pdf_path = desktop_dir / f"{timestamp}_{'中文' if lang == 'cn' else 'English'}_金融情报.pdf"
        write_pdf(reports, pdf_path, lang)
        written.append(str(pdf_path))

    written.extend(write_excel_files(latest_dir, desktop_dir, timestamp))
    manifest = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "desktop_folder": str(desktop_dir),
        "files": written,
        "source_status": status,
    }
    (reports_root / "latest" / "desktop_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def load_latest_reports(latest_dir: Path) -> list[dict[str, object]]:
    reports = []
    for market in ("us_equities", "china_equities", "crypto"):
        reports.append(json.loads((latest_dir / f"{market}.json").read_text(encoding="utf-8")))
    return reports


def write_pdf(reports: list[dict[str, object]], path: Path, lang: str) -> None:
    register_pdf_font()
    styles = build_styles(lang)
    doc = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        rightMargin=14 * mm,
        leftMargin=14 * mm,
        topMargin=14 * mm,
        bottomMargin=14 * mm,
        title=TEXT[lang]["title"],
    )
    story = [
        Paragraph(TEXT[lang]["title"], styles["title"]),
        Paragraph(TEXT[lang]["subtitle"], styles["subtitle"]),
        Paragraph(datetime.now().strftime("%Y-%m-%d %H:%M"), styles["small"]),
        Spacer(1, 6),
    ]

    for report in reports:
        market = str(report["market"])
        story.append(Paragraph(MARKET_LABELS[lang][market], styles["section"]))
        story.append(Paragraph(f"<b>{TEXT[lang]['briefing']}:</b> {text_for(report, 'briefing', lang)}", styles["body"]))
        story.append(Paragraph(f"<b>{TEXT[lang]['advice']}:</b> {text_for(report, 'advice', lang)}", styles["body"]))
        risks = report.get("risk_flags") or []
        risk_text = "<br/>".join(str(risk) for risk in risks[:4]) if risks else TEXT[lang]["none"]
        story.append(Paragraph(f"<b>{TEXT[lang]['risks']}:</b><br/>{risk_text}", styles["body"]))
        story.append(Spacer(1, 5))
        story.append(top_items_table(report, lang, styles))
        story.append(Spacer(1, 12))

    story.append(Paragraph(TEXT[lang]["note"], styles["small"]))
    doc.build(story)


def build_styles(lang: str) -> dict[str, ParagraphStyle]:
    base_font = PDF_FONT_NAME
    styles = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("TitleCustom", parent=styles["Title"], fontName=base_font, fontSize=22, leading=28, textColor=colors.HexColor("#17202A")),
        "subtitle": ParagraphStyle("SubtitleCustom", parent=styles["Normal"], fontName=base_font, fontSize=10, leading=14, textColor=colors.HexColor("#5F6C78"), alignment=TA_LEFT),
        "section": ParagraphStyle("SectionCustom", parent=styles["Heading2"], fontName=base_font, fontSize=14, leading=18, textColor=colors.HexColor("#0F766E"), spaceBefore=8),
        "body": ParagraphStyle("BodyCustom", parent=styles["BodyText"], fontName=base_font, fontSize=8.8, leading=12.2, textColor=colors.HexColor("#17202A")),
        "small": ParagraphStyle("SmallCustom", parent=styles["BodyText"], fontName=base_font, fontSize=7.5, leading=10, textColor=colors.HexColor("#5F6C78")),
    }


def register_pdf_font() -> None:
    global PDF_FONT_REGISTERED
    if PDF_FONT_REGISTERED:
        return
    for font_path in PDF_FONT_PATHS:
        if not font_path.exists():
            continue
        for subfont_index in range(4):
            try:
                registerFont(TTFont(PDF_FONT_NAME, str(font_path), subfontIndex=subfont_index))
                PDF_FONT_REGISTERED = True
                return
            except Exception:
                continue
    raise FileNotFoundError("No usable Chinese-capable font was found for PDF export.")


def top_items_table(report: dict[str, object], lang: str, styles: dict[str, ParagraphStyle]) -> Table:
    headers = TEXT[lang]["columns"]
    rows = [[Paragraph(f"<b>{header}</b>", styles["small"]) for header in headers]]
    for item in list(report.get("items", []))[:6]:
        rows.append(
            [
                Paragraph(translate_cell(str(item.get("priority", "")), lang), styles["small"]),
                Paragraph(str(item.get("score", "")), styles["small"]),
                Paragraph(str(item.get("source", "")), styles["small"]),
                Paragraph(translate_cell(str(item.get("stance", "")), lang), styles["small"]),
                Paragraph(shorten(str(item.get("title", "")), width=95, placeholder="..."), styles["small"]),
                Paragraph(shorten(translate_cell("; ".join(item.get("reasons", [])), lang), width=80, placeholder="..."), styles["small"]),
            ]
        )
    table = Table(rows, colWidths=[20 * mm, 13 * mm, 24 * mm, 18 * mm, 70 * mm, 37 * mm], repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EAF4F2")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#17202A")),
                ("LINEBELOW", (0, 0), (-1, 0), 0.8, colors.HexColor("#9FB8B4")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F7F9FB")]),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return table


def text_for(report: dict[str, object], key: str, lang: str) -> str:
    value = str(report.get(key, ""))
    if lang == "cn":
        return value
    translations = {
        "本小时共筛出": "This hour, the system selected",
        "条有效动态": "valid updates",
        "其中一级/二级关注": "with priority 1/2 items",
        "主线集中在": "Main themes are",
        "最高优先级消息来自": "Top-priority update comes from",
        "当前": "Current",
        "建议": "Suggested approach",
        "不构成投资建议": "not investment advice",
    }
    for source, target in translations.items():
        value = value.replace(source, target)
    return value


def translate_cell(value: str, lang: str) -> str:
    if lang == "cn":
        return value
    replacements = {
        "一级关注": "P1 Focus",
        "二级关注": "P2 Focus",
        "三级关注": "P3 Watch",
        "观察": "Monitor",
        "偏利好": "Positive bias",
        "偏利空": "Negative bias",
        "中性/待确认": "Neutral/Pending",
        "来源权重": "Source weight",
        "近 2 小时新消息": "Fresh within 2 hours",
        "条相似消息共振": " similar updates confirmed",
        "命中": "Keyword hit",
        "高冲击词": "High-impact term",
        "包含大幅百分比或大额金额": "Large percentage or large amount mentioned",
    }
    for source, target in replacements.items():
        value = value.replace(source, target)
    return value


def write_excel_files(latest_dir: Path, desktop_dir: Path, timestamp: str) -> list[str]:
    node = BUNDLED_NODE if BUNDLED_NODE.exists() else Path("node")
    env = os.environ.copy()
    env["NODE_PATH"] = "/Users/mac/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules"
    subprocess.run(
        [str(node), str(EXCEL_BUILDER), str(latest_dir), str(desktop_dir), timestamp],
        check=True,
        cwd=str(ROOT),
        env=env,
    )
    for inspect_file in desktop_dir.glob("*.inspect.ndjson"):
        inspect_file.unlink(missing_ok=True)
    return [
        str(desktop_dir / f"{timestamp}_中文_金融情报.xlsx"),
        str(desktop_dir / f"{timestamp}_English_Financial_Intelligence.xlsx"),
    ]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate simple desktop financial reports")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--reports-root", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--desktop-dir", type=Path, default=DESKTOP_REPORT_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    manifest = export_desktop_reports(args.config, args.reports_root, args.desktop_dir.expanduser())
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
