import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const [latestDir, desktopDir, timestamp] = process.argv.slice(2);

const markets = ["us_equities", "china_equities", "crypto"];
const marketLabels = {
  cn: { us_equities: "美国股市", china_equities: "中国股市", crypto: "加密货币" },
  en: { us_equities: "US Equities", china_equities: "China Equities", crypto: "Crypto" },
};
const labels = {
  cn: {
    file: `${timestamp}_中文_金融情报.xlsx`,
    overview: "总览",
    briefing: "核心摘要",
    advice: "客观建议",
    risk: "风险提示",
    headers: ["级别", "评分", "时间", "来源", "倾向", "标题", "摘要", "排序理由", "链接"],
  },
  en: {
    file: `${timestamp}_English_Financial_Intelligence.xlsx`,
    overview: "Overview",
    briefing: "Executive Briefing",
    advice: "Objective View",
    risk: "Risk Flags",
    headers: ["Priority", "Score", "Time", "Source", "Stance", "Headline", "Summary", "Ranking Reasons", "URL"],
  },
};

function translateCell(value, lang) {
  const text = String(value || "");
  if (lang === "cn") return text;
  const replacements = {
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
    "本小时共筛出": "This hour, the system selected",
    "条有效动态": "valid updates",
    "其中一级/二级关注": "with priority 1/2 items",
    "主线集中在": "Main themes are",
    "最高优先级消息来自": "Top-priority update comes from",
    "当前": "Current",
    "建议": "Suggested approach",
  };
  let output = text;
  for (const [source, target] of Object.entries(replacements)) {
    output = output.split(source).join(target);
  }
  return output;
}

async function loadReports() {
  const reports = {};
  for (const market of markets) {
    reports[market] = JSON.parse(await fs.readFile(path.join(latestDir, `${market}.json`), "utf8"));
  }
  return reports;
}

function writeTopBlock(sheet, report, lang, row) {
  const l = labels[lang];
  const market = marketLabels[lang][report.market];
  sheet.getRange(`A${row}:I${row}`).merge();
  sheet.getRange(`A${row}`).values = [[market]];
  sheet.getRange(`A${row}`).format.font = { bold: true, size: 15, color: "#0F766E" };
  sheet.getRange(`A${row + 1}:I${row + 1}`).merge();
  sheet.getRange(`A${row + 1}`).values = [[`${l.briefing}: ${translateCell(report.briefing, lang)}`]];
  sheet.getRange(`A${row + 2}:I${row + 2}`).merge();
  sheet.getRange(`A${row + 2}`).values = [[`${l.advice}: ${translateCell(report.advice, lang)}`]];
  sheet.getRange(`A${row + 3}:I${row + 3}`).merge();
  const riskText = report.risk_flags?.length ? report.risk_flags.slice(0, 3).join(" | ") : "None";
  sheet.getRange(`A${row + 3}`).values = [[`${l.risk}: ${riskText}`]];
  sheet.getRange(`A${row + 1}:A${row + 3}`).format.wrapText = true;
  return row + 5;
}

function writeTable(sheet, report, lang, startRow) {
  const rows = [labels[lang].headers];
  for (const item of report.items || []) {
    rows.push([
      translateCell(item.priority, lang),
      Number(item.score || 0),
      item.published_at || "",
      item.source || "",
      translateCell(item.stance, lang),
      item.title || "",
      item.summary || "",
      translateCell((item.reasons || []).join("; "), lang),
      item.url || "",
    ]);
  }
  const range = sheet.getRangeByIndexes(startRow - 1, 0, rows.length, labels[lang].headers.length);
  range.values = rows;
  sheet.getRangeByIndexes(startRow - 1, 0, 1, labels[lang].headers.length).format.fill = { color: "#EAF4F2" };
  sheet.getRangeByIndexes(startRow - 1, 0, 1, labels[lang].headers.length).format.font = { bold: true, color: "#17202A" };
  sheet.getRangeByIndexes(startRow, 0, Math.max(rows.length - 1, 1), labels[lang].headers.length).format.wrapText = true;
  sheet.getRangeByIndexes(startRow - 1, 0, rows.length, labels[lang].headers.length).format.borders = {
    insideHorizontal: { style: "thin", color: "#D9E0E7" },
    top: { style: "thin", color: "#9FB8B4" },
    bottom: { style: "thin", color: "#9FB8B4" },
  };
}

async function buildWorkbook(lang, reports) {
  const wb = Workbook.create();
  const overview = wb.worksheets.add(labels[lang].overview);
  overview.showGridLines = false;
  overview.getRange("A1:I1").merge();
  overview.getRange("A1").values = [[lang === "cn" ? "每小时金融情报简报" : "Hourly Financial Intelligence Brief"]];
  overview.getRange("A1").format.font = { bold: true, size: 20, color: "#17202A" };
  overview.getRange("A2").values = [[new Date().toISOString()]];
  overview.getRange("A2").format.font = { color: "#5F6C78" };
  let row = 4;
  for (const market of markets) {
    row = writeTopBlock(overview, reports[market], lang, row);
  }
  overview.getRange("A1:I22").format.autofitColumns();
  overview.getRange("A1:A22").format.columnWidth = 18;
  overview.getRange("B1:B22").format.columnWidth = 16;
  overview.getRange("C1:I22").format.columnWidth = 22;

  for (const market of markets) {
    const sheet = wb.worksheets.add(marketLabels[lang][market]);
    sheet.showGridLines = false;
    sheet.freezePanes.freezeRows(1);
    writeTable(sheet, reports[market], lang, 1);
    sheet.getRange("A1:A80").format.columnWidth = 14;
    sheet.getRange("B1:B80").format.columnWidth = 9;
    sheet.getRange("C1:C80").format.columnWidth = 24;
    sheet.getRange("D1:E80").format.columnWidth = 16;
    sheet.getRange("F1:F80").format.columnWidth = 50;
    sheet.getRange("G1:H80").format.columnWidth = 44;
    sheet.getRange("I1:I80").format.columnWidth = 48;
  }

  const out = await SpreadsheetFile.exportXlsx(wb);
  await out.save(path.join(desktopDir, labels[lang].file));
}

const reports = await loadReports();
await fs.mkdir(desktopDir, { recursive: true });
await buildWorkbook("cn", reports);
await buildWorkbook("en", reports);
