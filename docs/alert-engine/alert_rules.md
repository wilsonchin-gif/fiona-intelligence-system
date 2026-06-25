# Fiona Alert Rules

版本：V1.1.0  
状态：Planned  
负责人：Wilson  
更新时间：2026-06-26

## 1. Alert 类型

- Price Alert
- ETF Alert
- Macro Alert
- Institution Alert
- Risk Alert
- On-chain Alert
- Narrative Alert

## 2. 等级

S 级：

- `intelligence_score >= 85`
- 或 `impact_score >= 9` 且 `urgency_score >= 8`
- 或重大风险事件

A 级：

- `intelligence_score 70-84`
- 需要冷却与去重

B 级：

- `intelligence_score 40-69`
- 进入 Brief Pool

C 级：

- `< 40`
- 记录或忽略

## 3. 冷却

- 同资产同方向 Price Alert：60 分钟最多 1 条。
- 同宏观事件：只推 1 条。
- 同机构同主题：240 分钟最多 1 条。
- 同 Narrative：24 小时最多 2 条。
