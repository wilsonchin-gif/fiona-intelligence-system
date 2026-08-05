# Fiona Version Changelog

版本：V3.0.0
状态：Active  
负责人：Wilson  
更新时间：2026-08-05

## V3.0.0 GA - Fiona Design System 1.0

发布日期：2026-08-05

Commit：由本次 GA release commit 记录

影响范围：Market News Renderer / Design Tokens / Component Library / Tests / Product Documentation

### 新增功能

- 新增集中式 immutable design tokens，统一颜色、字号、间距、圆角、边框、阴影、图标、网格、surface、品牌与置信状态。
- 新增可独立渲染和测试的 Intelligence Card 组件库。
- 新增 Design System 1.0 文档、Release Notes、Architecture Snapshot 更新与 ADR 006。

### 修复内容

- 移除 Renderer 中分散的视觉常量和重复字体配置。
- 保留缺失数据、中文换行和长文本语义裁剪的确定性行为。

### 优化内容

- Today's Judgement 固定为视觉中心，Market Regime 与 Evidence 调整为次级信号。
- 技术 Footer 替换为低对比 Fiona Brand Signature。
- Full、Missing、Stress 原型统一使用同一 Design System。

### 删除内容

- 未删除生产代码、数据字段或交付能力。

### 影响范围

- 不影响 Scheduler、Runtime、Telegram Delivery、Railway、环境变量、ledger 或 arbitration。
- V3.0.0 作为 Fiona 第一个完整产品版本进入 Production。

## V3.0.0-RC - Visual Experience

发布日期：2026-08-05

Commit：未创建

影响范围：Market News Renderer / Tests / Product Documentation

### 新增功能

- 建立 Fiona Visual System V3、Information Architecture V3、Telegram Card Spec V3 与 Brand Guideline V3。
- 新增 Full、Missing、Stress 三种本地产品级原型及视觉验收测试。
- 新增 Judgment-First ADR、V3 Architecture Snapshot 与 Release Plan。

### 修复内容

- 修复长中文判断换行时可能出现的行首孤立标点。
- 缺失数据继续保持固定布局，不以零值代替未知值。

### 优化内容

- Fiona's View 成为视觉中心，Heat Map 调整为证据层。
- 优化移动端字号、对比度、间距、数据密度、品牌识别和分享体验。

### 删除内容

- 未删除生产代码、数据字段或交付能力。

### 影响范围

- 不影响 Scheduler、Runtime、Telegram Delivery、Railway、环境变量及五个定时任务。
- 当前仅为本地 Release Candidate，未 Commit、Push 或 Deploy。

## V1.0.1 - Workspace V2 Migration

发布日期：2026-06-26  
Commit：待本次 Workspace Migration 提交后由 Git 历史确认  
影响范围：Local Workspace / Documentation / Development Path

### 新增功能

- 建立 `~/Documents/Wilson AI Lab/` 作为长期本地工作空间。
- 将 Fiona Git 仓库迁移到 `Fiona Intelligence Platform/03_Development/fiona-intelligence-system/`。
- 建立 Workspace 管理规范、项目模板、迁移计划和迁移报告。

### 修复内容

- 修复本地 Fiona helper 默认输出路径，避免继续写入旧 `~/WilsonMarketNewsRuntime`。
- 更新旧 phase 文档中的本地 runtime 路径。

### 优化内容

- 旧 runtime、历史 reports、logs、env、launchd 模板迁入 Wilson AI Lab 分类目录。
- Desktop 不再保留 Fiona 项目目录。

### 删除内容

- 未删除任何生产代码。
- 未删除任何历史资料。

### 影响范围

- Railway 云端生产不受影响。
- Telegram 配置不变。
- 本地开发路径已迁移。

## V1.0.0 - Production Foundation

发布日期：2026-06-26  
Commit：待本次 Documentation Sync 提交后由 Git 历史确认  
影响范围：Documentation / Product Management

### 新增功能

- 建立 Fiona Project Documentation System。
- 新增 Roadmap、PRD、Architecture、Deployment、Decision Log、UI Library、Release Notes 等文档目录。
- 新增 `.docx` 导出目录 `docs/export/`。

### 修复内容

- 无代码修复。本次仅建立文档体系。

### 优化内容

- 明确 Fiona 后续开发必须执行 Documentation Sync。
- 明确 Git 提交前必须同步 README、CHANGELOG、PRD、Architecture、Roadmap、Decision Log。

### 删除内容

- 无。

### 影响范围

- 不影响 Railway Runtime。
- 不影响 Telegram 推送。
- 不影响 Alert Engine。

## 历史基线

### V1.0.0 Production Runtime

发布日期：2026-06-25  
状态：已完成

主要内容：

- Railway 部署完成。
- Telegram 发送链路统一。
- Fiona 定时任务稳定运行。
- Alert Engine 代码保留，默认关闭。
- 配置兼容完成：`WILSON_SEND`、`TELEGRAM_GROUP_ID`、`WILSON_INTERVAL_MINUTES`。
