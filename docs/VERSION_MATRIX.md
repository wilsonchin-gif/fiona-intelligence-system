# Fiona Version Matrix

版本：V3.1-alpha.1.1
状态：Gate 1.1 local PASS; Production observation pending
负责人：Wilson / Codex
更新时间：2026-09-02

## 1. 版本总览

| 版本 | 状态 | 核心范围 | 代码状态 | 文档状态 | Railway | Telegram |
|---|---|---|---|---|---|---|
| V1.0.0 | Released | Fiona Production V1：定时任务、Telegram、Railway、基础文档 | 已完成 | 已完成 | 已部署 | 已接入 |
| V1.0.1 | Local Commit Pending Push | Workspace 迁移、路径文档同步、Wilson AI Lab 管理体系 | 本地完成，待 Push | 本地完成 | 待 GitHub Push 后触发 | 逻辑未变 |
| V1.1.0 | Planned | Alert Engine V2 | 未开始 | PRD 已有基础 | 未部署 | 默认关闭 |
| V1.2.0 | Planned | Narrative Intelligence 与内容质量升级 | 未开始 | PRD 已有基础 | 未部署 | 继承现有链路 |
| V2.4 | Superseded | Railway image delivery、Caption RC、Scheduler reliability | 已完成 | 已同步 | Historical baseline | Image mode |
| V3.0.0 | Production | Judgment-first Visual Experience + Design System 1.0 | 已完成 | 已同步 | Production | Image mode |
| V3.1-alpha.1 | Production - PASS WITH CONDITIONS | Native Telegram Photo + Market News `en-US` | 已实现并上线 | 已同步 | Production | photo + en-US |
| V3.1-alpha.1.1 | Release Candidate | Morning / Evening / Daily / Weekly / Alert `en-US` completion | 本地实现与验证完成 | 已同步 | 待自动部署和生产观察 | 继承 photo + en-US |
| V3.1.0 | Planning | Global 4H Intelligence complete product | Gate 2-4 未开始 | Gate 0/1 已记录 | 未进入 GA | 未进入 GA |

## 2. 当前生产版本

当前生产版本为 V3.0.0，生产基线由 V2.4 Commit `0738adb` 升级。Railway 继续使用 `image` 模式；本次只发布 Renderer、组件、tokens、相关测试与文档，不改变交付链路。

V3.1-alpha.1 已完成并激活 Market News 原生 1440 x 1800 photo transport 与
集中式 `en-US` 输出层。Gate 1.1 将同一语言边界扩展至 Morning、Evening、
Daily、Weekly 与 Alert；本地验证通过，等待精确发布与生产自然消息观察。
Scheduler、Railway Variables、来源覆盖、cadence、delta 与 Telegram transport
语义均未改变。

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
- User Surface Matrix：`docs/v3_1/FIONA_USER_VISIBLE_SURFACE_MATRIX.md`
- Gate 1.1：`docs/v3_1/gates/GATE_1_1_EN_US_SURFACE_COMPLETION.md`
