# Fiona Product Roadmap

版本：V1.0.0  
状态：Active  
负责人：Wilson  
更新时间：2026-06-26

## 产品定位

Fiona 是 AI Market Intelligence Product。她不是新闻机器人，而是 Market Intelligence Officer，负责情报筛选、风险提示、叙事跟踪和市场判断。

## 当前版本

当前生产版本：V1.0.0 Production Foundation

完成度：80%

已完成：

- Railway 7×24 Runtime。
- Telegram Group 推送。
- Fiona Market News / Morning / Evening / Daily / Weekly。
- Alert Engine 代码保留，生产默认关闭。
- Telegram 发送链路统一为 `telegram_service`。
- Production 配置命名初步统一。
- Documentation System 初始化。

## 当前优先级

P0：

- 生产稳定性。
- Telegram 文本内容质量。
- 日志和配置可维护性。

P1：

- Alert Engine 生产前验证。
- Narrative Engine 叙事质量提升。
- 图片拆图与高清导出。

P2：

- Web Dashboard。
- 数据库持久化。
- 多用户/多频道配置。

## Roadmap

### V1.0.0 Production Foundation

目标：让 Fiona 稳定运行，形成可维护的生产基础。

状态：Active

### V1.1.0 Alert Readiness

目标：完善 Alert 评分、去重、生命周期、Dry Run 审计。

状态：Planned

### V1.2.0 Content Intelligence

目标：提升内容表达，从数据拼接升级为 Market Intelligence Analyst。

状态：Planned

### V1.3.0 Visual Intelligence

目标：恢复高清图片推送，采用 1080×1350 拆图与 sendDocument。

状态：Planned

### V2.0.0 Product Platform

目标：引入数据库、Dashboard、权限和多用户配置。

状态：Future

## 下一阶段

下一阶段：V1.1.0 Alert Readiness

进入条件：

- Production V1 连续稳定运行。
- Telegram 文本质量达标。
- Alert Dry Run 输出可审计。

退出条件：

- Alert Engine 可按环境变量安全开启。
- S/A/B/C 事件分类稳定。
- 去重、冷却、生命周期日志完整。
