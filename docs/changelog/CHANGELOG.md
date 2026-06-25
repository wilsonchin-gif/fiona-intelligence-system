# Fiona Version Changelog

版本：V1.0.0  
状态：Active  
负责人：Wilson  
更新时间：2026-06-26

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
