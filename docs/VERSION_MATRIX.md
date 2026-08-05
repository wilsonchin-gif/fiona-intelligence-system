# Fiona Version Matrix

版本：V3.0.0
状态：Active
负责人：Wilson / Codex
更新时间：2026-08-05

## 1. 版本总览

| 版本 | 状态 | 核心范围 | 代码状态 | 文档状态 | Railway | Telegram |
|---|---|---|---|---|---|---|
| V1.0.0 | Released | Fiona Production V1：定时任务、Telegram、Railway、基础文档 | 已完成 | 已完成 | 已部署 | 已接入 |
| V1.0.1 | Local Commit Pending Push | Workspace 迁移、路径文档同步、Wilson AI Lab 管理体系 | 本地完成，待 Push | 本地完成 | 待 GitHub Push 后触发 | 逻辑未变 |
| V1.1.0 | Planned | Alert Engine V2 | 未开始 | PRD 已有基础 | 未部署 | 默认关闭 |
| V1.2.0 | Planned | Narrative Intelligence 与内容质量升级 | 未开始 | PRD 已有基础 | 未部署 | 继承现有链路 |
| V2.4 | Superseded | Railway image delivery、Caption RC、Scheduler reliability | 已完成 | 已同步 | Historical baseline | Image mode |
| V3.0.0 | Production | Judgment-first Visual Experience + Design System 1.0 | 已完成 | 已同步 | Production | Image mode |

## 2. 当前生产版本

当前生产版本为 V3.0.0，生产基线由 V2.4 Commit `0738adb` 升级。Railway 继续使用 `image` 模式；本次只发布 Renderer、组件、tokens、相关测试与文档，不改变交付链路。

## 3. 相关文档

- Roadmap：`docs/roadmap/roadmap.md`
- Deployment：`docs/deployment/production.md`
- V3 Release Plan：`docs/v3/FIONA_RELEASE_PLAN_V3.md`
- Design System：`docs/v3/FIONA_DESIGN_SYSTEM_1_0.md`
- Component Library：`docs/v3/FIONA_COMPONENT_LIBRARY.md`
- Token Guide：`docs/v3/FIONA_DESIGN_TOKEN_GUIDE.md`
