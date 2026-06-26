# Fiona Release v1.0.1

版本：V1.0.1  
状态：Active  
负责人：Wilson  
更新时间：2026-06-26

## Highlights

- 完成 Wilson AI Lab Workspace V2 本地工作空间重构。
- Fiona 本地仓库迁移到统一开发目录。
- 旧 runtime、reports、logs、launchd 模板已归档。

## New Features

- 新增 Wilson AI Lab Workspace 管理规范。
- 新增 Fiona Workspace Migration Report。
- 新增 Project Structure 文档。

## Fixes

- 修复本地 helper 默认输出路径，避免继续写入旧 `~/WilsonMarketNewsRuntime`。
- 更新历史文档中的旧 runtime 路径。

## Optimizations

- Desktop 不再保存 Fiona 项目目录。
- 本地资料分类到 Data / Deployment / Documents / Archive。

## Breaking Changes

- 本地 Fiona 仓库路径发生变化。
- 旧 `~/WilsonMarketNewsRuntime` 已迁入 Archive，不再作为本地默认 runtime。

## Known Issues

- `docs/fiona_project_memo.docx` 仍为未跟踪文件，需要人工确认是否纳入 Git。
- GitHub push 仍取决于本机 GitHub 凭据或 GitHub Desktop。

## Next Version

V1.1.0 Alert Readiness。
