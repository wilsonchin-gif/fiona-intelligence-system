# Fiona Product Decision Log

版本：V1.0.0  
状态：Active  
负责人：Wilson  
更新时间：2026-06-26

## Decision 001 - Fiona 不是新闻机器人

日期：2026-06-24  
状态：Accepted

Decision：

Fiona 定位为 Market Intelligence Officer。

Why：

用户真正需要的是筛选、判断、风险提示和叙事跟踪，不是更多新闻。

Impact：

所有输出必须回答发生了什么、为什么重要、接下来关注什么、Fiona 如何理解。

Alternatives：

- 保持 Wilson's Market News 新闻机器人定位。
- 增加更多资讯推送量。

## Decision 002 - Alert 默认关闭

日期：2026-06-25  
状态：Accepted

Decision：

Alert Engine 代码保留，但生产默认关闭。

Why：

避免通知疲劳，先验证评分、去重和生命周期机制。

Impact：

生产变量默认：

```env
FIONA_ALERT_ENABLED=0
FIONA_ALERT_DRY_RUN=1
```

Alternatives：

- 立即开启实时 Alert。
- 只保留固定简报。

## Decision 003 - 文档系统成为完成标准

日期：2026-06-26  
状态：Accepted

Decision：

每次开发结束必须执行 Documentation Sync。

Why：

Fiona 需要从 Bot 项目升级为可长期管理的 AI Market Intelligence Product。

Impact：

没有文档同步的功能，不视为完成。

Alternatives：

- 只维护 README。
- 文档放在外部工具，不进入 Git。
