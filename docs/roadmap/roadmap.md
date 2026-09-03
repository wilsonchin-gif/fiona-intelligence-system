# Fiona Product Roadmap

版本：V3.1-alpha.2
状态：Active  
负责人：Wilson  
更新时间：2026-09-03

## 产品定位

Fiona 是 AI Market Intelligence Product。她不是新闻机器人，而是 Market Intelligence Officer，负责情报筛选、风险提示、叙事跟踪和市场判断。

## 当前版本

当前生产基线：V3.0.0 Design System + V3.1-alpha.1 Native Photo / en-US。

当前工作里程碑：V3.1-alpha.2 Global Coverage Engine，Implemented / Shadow Candidate。

完成度按 Gate 记录，不以未经度量的百分比替代验收：Gate 0/1 CLOSED；
Gate 2 本地实现完成，生产观测待验收；Gate 3 LOCKED。

已完成：

- Railway 7×24 Runtime。
- Telegram Group 推送。
- Fiona Market News / Morning / Evening / Daily / Weekly。
- Alert Engine 代码与既有生产开关保留，本轮不调整。
- Telegram 发送链路统一为 `telegram_service`。
- Production 配置命名初步统一。
- Documentation System 初始化。
- Wilson AI Lab Workspace V2 初始化。
- Fiona 本地仓库迁移到统一 Workspace。
- 原生 1440 x 1800 Photo、统一 en-US 输出、真实 iPhone QA。
- Gate 2 单一 Source Registry、官方来源扩展、provenance、聚类与 Shadow 排序。

## 当前优先级

P0：

- 生产稳定性。
- Telegram 文本内容质量。
- 日志和配置可维护性。
- Workspace 统一管理。

P1：

- Alert Engine 生产前验证。
- Narrative Engine 叙事质量提升。
- 图片拆图与高清导出。

P2：

- Web Dashboard。
- 数据库持久化。
- 多用户/多频道配置。

## 历史规划

下列早期版本规划作为历史保留，不代表当前生产状态；当前权威路线为
[V3.1 Gate Roadmap](../v3_1/FIONA_V3_1_IMPLEMENTATION_ROADMAP.md)。

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

下一阶段：完成 Gate 2 生产 Shadow 观察与 Product Review。

进入条件：

- Gate 1 已关闭，production 继续 photo/en-US。
- Global Coverage 保持 legacy authority；不得修改 cadence 或 Delta。

退出条件：

- 至少 14 天 Shadow 与 100 个不同合格事件簇。
- 官方来源健康、ROW 覆盖改善、地区缺口与转载误判有可审核证据。
- Product 明确批准后才讨论 global_631 激活；Gate 3 不自动开始。
