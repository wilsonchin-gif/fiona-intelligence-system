# Fiona Component Library

- Version: V3.0.0 / Design System 1.0
- Status: Production
- Owner: Wilson / Fiona Design Engineering
- Updated: 2026-08-05

## Component Contract

所有组件实现统一 `render(context) -> ComponentRenderResult` 合约。输入通过 dataclass 明确表达，输出包含组件名称、布局区域和绘制后的下一位置。

| Component | Input | Output responsibility |
|---|---|---|
| Header | title, timestamp, eyebrow | 品牌、版本语境与更新时间 |
| Market Regime | regime | Risk On / Risk Off / Neutral / Transition / Unknown |
| Evidence | evidence level | Verified / Strong / Moderate / Limited |
| Hero Judgment | view, driver, confirmation | Today's Judgement 核心阅读层 |
| Heat Map | market scores | 市场状态证据 |
| What Changed | change list | 本周期真实变化 |
| Key Markets | market rows | 核心市场快照 |
| Narrative | narrative rows | 当前叙事及强度 |
| Watch Next | confirmation list | 下一步可验证变量 |
| Historical Context | context text | 简单历史语境入口 |
| Brand Signature | fixed brand text | 低对比分享签名 |
| Footer | disclaimer | 非预测与免责声明 |

## Isolation Rules

- 组件不得读取环境变量、调用网络或发送 Telegram。
- 组件不得修改 ledger、memory 或 runtime state。
- 组件只消费 `RenderContext`、输入模型和 design tokens。
- 组件不得使用 renderer 内部的 raw color 或 typography constants。
- 每个组件必须能在独立 canvas 上渲染。

## Reuse

Morning、Evening、Daily 和 Weekly 未来可以复用 Header、Hero Judgment、Evidence、Watch Next、Brand Signature 与 Footer，但本阶段不修改这些产品模块。

## Extension Rule

新增组件必须先定义：产品问题、输入 contract、输出区域、缺失状态、长文本策略、token 使用和 isolation test。只有视觉差异、没有新信息责任时，不应创建新组件。
