# Fiona Architecture Snapshot - Visual V3 / Design System 1.0

- Version: V3.0.0 Production base + V3.1-alpha.1 Gate 1
- Status: Native photo + all active en-US surfaces production validated; Gate 1 CLOSED
- Owner: Fiona Engineering
- Updated: 2026-09-03

## Production Pipeline

```mermaid
flowchart LR
    Scheduler["Fiona Scheduler"] --> Runtime["Fiona Runtime"]
    Runtime --> ViewModel["MarketNewsViewModel"]
    ViewModel --> Renderer["Renderer Orchestrator"]
    Renderer --> Components["Reusable Card Components"]
    Components --> Tokens["Immutable Design Tokens"]
    ViewModel --> Caption["Existing Caption Composer"]
    Components --> PNG["Native 1440 x 1800 PNG"]
    PNG --> Delivery["Telegram Photo Delivery"]
    Caption --> Delivery
    Delivery --> API["Telegram Bot API"]
```

## V3.1-alpha.1 Optional Market News Profile

```mermaid
flowchart LR
    Runtime["Existing Runtime"] --> Flags["Media + Locale Boundary"]
    Flags --> VM["MarketNewsViewModel"]
    VM --> Locale["zh-CN or en-US projection"]
    Locale --> Renderer["Token-driven Renderer"]
    Renderer --> Document["1080 x 1350 document"]
    Renderer --> Photo["Native 1440 x 1800 photo"]
    Document --> Coordinator["Existing Delivery Coordinator"]
    Photo --> Coordinator
    Coordinator --> Telegram["telegram_service"]
    Telegram -->|definite photo failure| Text["One text fallback"]
    Telegram -->|unknown photo state| Stop["No second send"]
```

`FIONA_TELEGRAM_MEDIA_MODE` defaults to `document` and
`FIONA_OUTPUT_LOCALE` defaults to `zh-CN`. The alpha path reuses the existing
runtime, coordinator, delivery result, temporary-file lifecycle, and occurrence
arbitration. It does not introduce another scheduler, ledger, or sender.

The effective production settings are `photo + en-US`. Coverage and cadence
remain on their `legacy` defaults, and 4H Delta remains `off`.

## Change Boundary

V3 与 Design System 1.0 只替换 Renderer 内部的视觉表现和工程组织：布局、字体层级、色彩、间距、密度、品牌签名、tokens 与组件。Scheduler、Runtime、ViewModel contract、Caption Composer、Telegram Service、Railway command、ledger 与 arbitration 均未改变。

## V3.1 Gate 1.1 Language Boundary

```mermaid
flowchart TD
    Scheduler[Existing Scheduler] --> Runtime[run_once]
    Runtime --> Locale[Resolve FIONA_OUTPUT_LOCALE once]
    Runtime --> Events[Existing events, scores, narratives]
    Events --> Briefs[Morning / Evening / Daily / Weekly]
    Events --> Alert[Existing Alert classifier]
    Events --> Market[Market News ViewModel]
    Locale --> Briefs
    Locale --> Alert
    Locale --> Market
    Briefs --> Guard[Final en-US CJK guard]
    Alert --> Guard
    Market --> Guard
    Guard --> Service[telegram_service]
    Service --> API[Telegram Bot API]
```

Original source-language fields remain in events, snapshot data, memory, and
provenance. Locale projection occurs only after existing business decisions.
No score, route, alert threshold, schedule, ledger, or delivery transport is
changed. The final text boundary performs at most one deterministic repair and
one safe English fallback.

## Compatibility

- 输入仍为 `MarketNewsViewModel`。
- 输出仍为 RGB PNG；V3 基础 profile 为 1080×1350，生产 iOS photo profile 为直接渲染的 1440×1800，最大 1.5 MB。
- 缺失数据和长文本继续使用确定性规则。
- 生产 Feature Flag 与 fallback 行为不变。
- `app/fiona_card_renderer.py` 保留旧公开 helper 的兼容 wrapper。
- 组件只消费 ViewModel 派生输入、RenderContext 与 `FIONA_TOKENS`，不产生外部副作用。
- `FIONA_IOS_TOKENS` 是直接 1440 x 1800 渲染 profile，不是 1080 图像放大。
- `app/fiona_locale.py` 只负责输出边界、共享术语、确定性英文投影与语言验证，不承担评分或路由判断。
- Market News、Morning、Evening、Daily、Weekly 与 Alert 已接入同一 `en-US` 边界；Gate 1 生产验收完成。
- Gate 2 尚未开始，Global 6:3:1、Global 4H cadence 与 4H Delta 均未激活。
