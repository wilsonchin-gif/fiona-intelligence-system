# Fiona Design Token Guide

- Version: V3.0.0 / Design System 1.0
- Status: Production
- Owner: Wilson / Fiona Design Engineering
- Updated: 2026-08-05

## Source of Truth

Design tokens 的唯一代码来源：`app/design_tokens.py`。

Renderer 和 components 不得定义重复颜色、字体尺寸或布局常量。

## Token Groups

| Group | Purpose |
|---|---|
| Canvas | width, height, maximum PNG size |
| Colors | brand, surfaces, text, semantic states, confidence states |
| Typography | display, heading, body, data, label, caption, footer |
| Spacing | micro spacing through section gap |
| Radius | card and badge radius |
| Border | width and semantic border colors |
| Shadow | enabled state, offset and color |
| Icon Size | small, medium and large |
| Grid | outer margin, gutter, columns |
| Surface | named section regions |
| Footer Style | brand signature and disclaimer behavior |

## Semantic Color Rules

- Positive：只表示正向市场变化。
- Negative：只表示负向市场变化或风险。
- Neutral：表示方向未形成。
- Unknown：表示数据或判断不足。
- High Confidence：表示证据充分，不代表结果确定。
- Limited Confidence：表示证据有限，不可替代为乐观或悲观颜色。

## Typography Rules

- 使用 token 语义名，不直接传入数字字号。
- Hero 判断优先于市场数据。
- Footer 和签名为最低视觉权重。
- CJK 文本在固定字号下换行；超限后语义截断。

## Change Control

Token 变更需要：视觉回归测试、Full/Missing/Stress 原型、移动端可读性检查和 ADR（若改变产品层级）。单个组件不得通过局部常量绕过 token 系统。
