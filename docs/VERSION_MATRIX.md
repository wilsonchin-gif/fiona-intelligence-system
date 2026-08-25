# Fiona Version Matrix

版本：V3.1-alpha.1
状态：Gate 1 PASS WITH CONDITIONS; Production remains V3.0.0 defaults
负责人：Wilson / Codex
更新时间：2026-08-25

## 1. 版本总览

| 版本 | 状态 | 核心范围 | 代码状态 | 文档状态 | Railway | Telegram |
|---|---|---|---|---|---|---|
| V1.0.0 | Released | Fiona Production V1：定时任务、Telegram、Railway、基础文档 | 已完成 | 已完成 | 已部署 | 已接入 |
| V1.0.1 | Local Commit Pending Push | Workspace 迁移、路径文档同步、Wilson AI Lab 管理体系 | 本地完成，待 Push | 本地完成 | 待 GitHub Push 后触发 | 逻辑未变 |
| V1.1.0 | Planned | Alert Engine V2 | 未开始 | PRD 已有基础 | 未部署 | 默认关闭 |
| V1.2.0 | Planned | Narrative Intelligence 与内容质量升级 | 未开始 | PRD 已有基础 | 未部署 | 继承现有链路 |
| V2.4 | Superseded | Railway image delivery、Caption RC、Scheduler reliability | 已完成 | 已同步 | Historical baseline | Image mode |
| V3.0.0 | Production | Judgment-first Visual Experience + Design System 1.0 | 已完成 | 已同步 | Production | Image mode |
| V3.1-alpha.1 | Local alpha - PASS WITH CONDITIONS | Native Telegram Photo + Market News `en-US` | 已实现，待 Product Review | 已同步 | 可在 legacy defaults 下部署；未授权激活 | 默认仍为 document + zh-CN |
| V3.1.0 | Planning | Global 4H Intelligence complete product | Gate 2-4 未开始 | Gate 0/1 已记录 | 未进入 GA | 未进入 GA |

## 2. 当前生产版本

当前生产版本为 V3.0.0，生产基线由 V2.4 Commit `0738adb` 升级。Railway 继续使用 `image` 模式；本次只发布 Renderer、组件、tokens、相关测试与文档，不改变交付链路。

V3.1-alpha.1 已完成 Market News 原生 1440 x 1800 photo transport 与集中式
`en-US` 输出层，但新能力仍由 legacy-safe defaults 保护。Scheduler、Railway
Variables、来源覆盖、其他 Brief 与 Alert 均未改变；`photo + en-US` 尚未授权生产激活。

## 3. 相关文档

- Roadmap：`docs/roadmap/roadmap.md`
- Deployment：`docs/deployment/production.md`
- V3 Release Plan：`docs/v3/FIONA_RELEASE_PLAN_V3.md`
- Design System：`docs/v3/FIONA_DESIGN_SYSTEM_1_0.md`
- Component Library：`docs/v3/FIONA_COMPONENT_LIBRARY.md`
- Token Guide：`docs/v3/FIONA_DESIGN_TOKEN_GUIDE.md`
- V3.1 Product Freeze：`docs/v3_1/FIONA_V3_1_PRODUCT_FREEZE.md`
- V3.1 Implementation Roadmap：`docs/v3_1/FIONA_V3_1_IMPLEMENTATION_ROADMAP.md`
- V3.1 Release Strategy：`docs/v3_1/FIONA_V3_1_RELEASE_STRATEGY.md`
- Gate 0 Closeout：`docs/v3_1/gates/GATE_0_CLOSEOUT.md`
- Gate 1 Implementation：`docs/v3_1/gates/GATE_1_IMPLEMENTATION.md`
- Native Photo Spec：`docs/v3_1/FIONA_NATIVE_PHOTO_SPEC.md`
- en-US Standard：`docs/v3_1/FIONA_EN_US_OUTPUT_STANDARD.md`
