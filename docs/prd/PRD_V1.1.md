# Fiona PRD V1.1 - Alert Readiness

版本：V1.1.0  
状态：Planned  
负责人：Wilson  
更新时间：2026-06-26

## 1. 目标

让 Fiona Alert Engine 从代码可用进入生产前可审计状态。

## 2. 范围

包含：

- Alert 评分审计。
- 冷却与去重验证。
- 生命周期管理。
- Dry Run 日志。
- Telegram 文案模板。

不包含：

- 默认开启真实 Alert。
- 新增高风险数据源。

## 3. 验收标准

- S/A/B/C 事件分类稳定。
- 同类事件不会刷屏。
- NEW / ONGOING / RESOLVED 状态可追踪。
- Dry Run 输出可复盘。
- 生产默认仍关闭真实 Alert。
