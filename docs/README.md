# Fiona Documentation System

版本：V1.0.0  
状态：Active  
负责人：Wilson  
更新时间：2026-06-26

## 原则

Fiona 仓库同时是代码仓库、产品仓库和知识库。

所有开发遵循：

- Code First, Documentation Always.
- 没有文档同步的功能，不视为完成。
- 每次提交前必须执行 Documentation Sync。
- 所有长期文档使用 Markdown，确保 Git 可追踪。
- 如 Documents 能力可用，同步导出 `.docx` 到 `docs/export/`。

## Documentation Sync Checklist

每次开发结束后，在 commit 前检查：

- `docs/changelog/CHANGELOG.md` 是否更新。
- `docs/roadmap/roadmap.md` 是否更新。
- 相关 PRD 是否更新。
- 架构、Runtime、Deployment、Dataflow 是否需要更新。
- Decision Log 是否记录产品方向变化。
- UI Library 是否记录 Telegram / 图片 / 颜色 / 字体变化。
- Release Note 是否创建或更新。
- README 是否与当前生产版本一致。

## 目录

```text
docs/
├── roadmap/
├── changelog/
├── prd/
├── architecture/
├── ui/
├── alert-engine/
├── narrative/
├── api/
├── deployment/
├── decisions/
├── meeting/
├── releases/
└── export/
```
