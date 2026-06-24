# 每日金融情报台

这个项目会每 4 小时抓取美国股市、中国股市、加密货币三类市场资讯，按影响力排序，并生成报表。

## Wilson's Market News MVP

新增的 Wilson MVP 会自动抓取美股、中国市场、Crypto、RWA 数据，生成：

- Telegram Markdown: `reports/wilson/latest/telegram.md`
- 竖版长图 PNG: `reports/wilson/latest/infographic.png`
- 原始快照 JSON: `reports/wilson/latest/snapshot.json`

手动生成一次：

```bash
python3 -m app.wilson run-once
```

生成并推送到 Telegram：

```bash
python3 -m app.wilson --send run-once
```

Telegram 配置：

```bash
cp config/wilson.env.example config/wilson.env
```

然后编辑 `config/wilson.env`，填入：

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHANNEL_ID`
- `TELEGRAM_GROUP_ID`

内测默认只生成不推送。确认可推送后，把 `config/wilson.env` 里的 `WILSON_SEND=1` 打开。

本地常驻每 4 小时运行：

```bash
chmod +x scripts/run_wilson_4h.sh
scripts/run_wilson_4h.sh
```

macOS 后台定时运行，按本机时间 00:00 / 04:00 / 08:00 / 12:00 / 16:00 / 20:00 执行：

```bash
chmod +x scripts/run_wilson_once.sh
cp scripts/launchd/com.local.wilson-market-news.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.local.wilson-market-news.plist
```

如需只生成不推送，在 `config/wilson.env` 设置 `WILSON_SEND=0`。

## 最简单用法

桌面文件夹：`~/Desktop/每日金融情报报表`

每 4 小时会自动生成：

- 中文 PDF
- English PDF
- 中文 Excel
- English Excel
- VP 阅读版 HTML/PDF 预览

手动立即生成一次：

```bash
scripts/run_desktop_hourly.sh
```

## 快速运行

```bash
python3 -m app.main run-once
python3 -m app.main serve --port 8765
```

打开 `http://127.0.0.1:8765/` 查看最新报表。

## 每 4 小时自动生成

```bash
python3 -m app.main watch --interval-minutes 240
```

macOS 后台运行可以使用项目内的 `launchd` 模板：

```bash
chmod +x scripts/run_hourly.sh
cp scripts/launchd/com.local.financial-daily.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.local.financial-daily.plist
```

输出文件：

- `reports/latest/us_equities.html`
- `reports/latest/china_equities.html`
- `reports/latest/crypto.html`
- `reports/archive/YYYY-MM-DD/HH00/*.html`

## 数据源配置

编辑 `config/sources.json` 可以添加、删除或调整数据源权重。推荐把 TechFlow、PANews、Odaily、今十数据等来源的授权 RSS、开放 API 或 RSSHub 源接入到对应市场。

字段说明：

- `market`: `us_equities`、`china_equities`、`crypto`
- `kind`: 当前支持 `rss` 和简单 `json`
- `weight`: 来源权重，越权威越高
- `enabled`: 设置为 `false` 可临时关闭

## 排序逻辑

系统综合以下信号打分：

- 消息新鲜度
- 来源权重
- 多来源重复/共振
- 宏观、政策、监管、流动性、龙头公司、交易所安全等关键词
- 高冲击词，如突发、批准、调查、禁令、大跌、黑客、清算
- 大额金额或大幅百分比

报表中的观点是规则化点评，不构成投资建议。
