# Fiona V2 Phase 2A Prototype Report

- Version: V2 Phase 2A
- Status: Product Review
- Owner: Fiona Product / Engineering
- Updated: 2026-07-24

## Scope

本阶段只为 Fiona Market News 建立智能图文卡片原型。没有修改 Scheduler、Ledger、Arbitration、Occurrence、Retry、Railway、Telegram 生产发送、Morning、Evening、Daily、Weekly 或 Alert。

## Current Content Pipeline Audit

```text
Railway
  → app.fiona_runtime.run_scheduler
  → app.fiona_scheduler
  → app.fiona_runtime.execute_scheduled_occurrence
  → app.fiona_runtime.run_once
  → app.fiona_runtime.build_payload
  → app.fiona_runtime.build_brief
  → app.fiona_briefing.build_market_news_brief
  → app.fiona_runtime.push_text
  → app.telegram_service.send_message
  → Telegram Bot API
```

审计结论：

- 当前 Market News 是纯文字发送。
- `telegram_service` 已有 `send_message`、`send_photo`、`send_document`。
- `app.wilson` 已有 HTML、SVG 和 PNG 原型能力。
- `app.render` 是旧 MarketReport HTML renderer，不属于 Fiona Market News 图卡链路。
- `app.desktop_export` 主要负责桌面 PDF/CSV/XLSX 输出。
- 当前 Railway runtime 的 `requirements.txt` 声明只依赖 Python 标准库。
- 本地环境没有 Pillow、ReportLab、CairoSVG 或 Playwright。
- macOS 有 `sips`，Railway Linux 不具备这一命令。

## Prototype Implementation

新增独立模块：

- `app/fiona_market_news_image.py`

能力：

- `MarketNewsViewModel`
- Caption Composer
- Controlled Tag Composer
- SVG Card Renderer
- PNG Prototype Renderer
- Data Quality State
- Text Fallback Contract

新增本地生成脚本：

- `scripts/generate_fiona_market_news_prototypes.py`

## Prototype Outputs

- `reports/prototypes/fiona_market_news/market_news_full.png`
- `reports/prototypes/fiona_market_news/market_news_missing.png`
- `reports/prototypes/fiona_market_news/market_news_long_text.png`
- `reports/prototypes/fiona_market_news/caption_examples.md`

三张 PNG 均为 1080×1350。

## Test Coverage

新增专项测试：

- ViewModel 数据一致性
- Caption 长度
- Caption 缺失数据 fallback
- Tag 分类、去重和数量限制
- PNG 1080×1350
- 中文 SVG 内容
- 长文本换行
- Renderer 失败时保留原文字
- Morning / Evening / Daily / Weekly 构建器回归

## Renderer Decision

Phase 2A 原型：

- 标准库 SVG
- macOS `sips` → PNG

Phase 2B 生产推荐：

- Pillow 直接生成 PNG
- 随部署提供确定版本的 CJK 字体
- 先验证 Railway 构建与字体渲染

不建议直接在生产引入 Playwright；当前卡片不需要浏览器布局引擎，其依赖和运行成本高于需求。

## Telegram Decision

推荐：

```text
sendDocument(PNG, caption)
```

原因：

- 保留原图清晰度。
- Caption 与图片保持在同一条 Telegram 内容中。
- 符合“先读摘要，再点击深读”的产品路径。

Phase 2A 没有修改 `telegram_service`，没有真实发送 Telegram。

## Fallback Decision

生产接入时：

1. 先生成并保留原 Market News 文字。
2. 图片成功时发送 Document + Caption。
3. Renderer 或 Document 发送失败时，继续发送原文字。
4. 图片失败不改变 Scheduler occurrence 的可靠性语义。

## Validation Summary

- Python compile: Passed
- Unit tests: 114 passed
- Caption lengths: 249–303 characters
- PNG dimensions: 1080×1350
- PNG sizes: approximately 0.56 MB each
- Prototype-only: Yes
- Production output changed: No
- Scheduler changed: No
- Telegram production changed: No
- Alert changed: No
- Railway changed: No
- Real Telegram sent: No
- Commit: No
- Push: No
- Deploy: No
