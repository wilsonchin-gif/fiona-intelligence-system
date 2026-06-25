# Fiona Alert Engine PRD

版本：V1.1.0  
状态：Planned  
负责人：Wilson  
更新时间：2026-06-26

## 1. 定位

Fiona Alert 不是新闻快讯，而是重大市场情报提醒。

## 2. 原则

- 宁可少推，不滥推。
- 正常情况下每天 0-5 条。
- 只推真正重要的 S/A 级事件。
- 默认生产关闭。

## 3. 输出必须回答

- What Happened
- Why It Matters
- Affected Assets
- What To Watch
- Fiona's View

## 4. 当前状态

代码存在，生产默认关闭：

```env
FIONA_ALERT_ENABLED=0
FIONA_ALERT_DRY_RUN=1
```
