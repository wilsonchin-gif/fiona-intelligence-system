# ADR 006 - Reusable Token-Driven Card System

- Date: 2026-08-05
- Status: Accepted for Production
- Owner: Wilson / Fiona Engineering

## Decision

Fiona Intelligence Card 使用集中式 immutable design tokens、独立组件和薄 Renderer Orchestrator。Today's Judgement 固定为主视觉层，Evidence 与 Market Regime 为次级层。

## Why

Renderer 内部分散的色彩、字号和布局常量难以复用与一致验证。Fiona 需要长期支持多种 Intelligence Card，同时保持判断优先、移动端可读和稳定品牌人格。

## Impact

- 视觉常量统一进入 `app/design_tokens.py`。
- 绘制能力拆分进入 `app/fiona_card_components.py`。
- `app/fiona_card_renderer.py` 只负责组装、渲染和验证。
- 现有 ViewModel 和生产交付接口保持兼容。
- Future cards 可复用组件，但必须单独经过产品与生产 Gate。

## Alternatives

- 继续在单一 Renderer 中维护所有常量和绘制逻辑。
- 引入 Web/CSS renderer 或外部设计框架。
- 为每种 Brief 建立独立视觉系统。

## Consequences

组件和 token 数量增加，但视觉一致性、测试隔离、变更审计和复用能力显著提升。该决策不授权修改 Scheduler、Runtime、Telegram 或 Railway。
