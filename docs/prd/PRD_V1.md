# Fiona PRD V1.0

版本：V1.0.0  
状态：Active  
负责人：Wilson  
更新时间：2026-06-26

## 1. 产品目标

Fiona 将 Wilson's Market News 升级为长期可运行的 AI Market Intelligence Product。

Fiona 的职责：

- 筛选市场情报。
- 降低信息噪音。
- 识别关键风险。
- 跟踪市场叙事。
- 输出可读、克制、可验证的市场观察。

## 2. 非目标

Fiona 不负责：

- 价格预测。
- 喊单。
- 制造焦虑。
- 高频刷屏。
- 替代投资决策。

## 3. 生产模块

当前保留 5 个定时模块：

- Fiona Market News：00:00
- Fiona Morning：07:30
- Fiona Evening：20:30
- Fiona Daily：22:30
- Fiona Weekly：周日 21:00

## 4. Alert Engine

Alert Engine 代码存在，但生产默认关闭。

默认变量：

```env
FIONA_ALERT_ENABLED=0
FIONA_ALERT_DRY_RUN=1
```

## 5. Telegram

生产推荐只配置：

```env
TELEGRAM_BOT_TOKEN=
TELEGRAM_GROUP_ID=
```

发送链路：

```text
Fiona Runtime -> telegram_service -> Telegram Bot API
```

## 6. 成功标准

- 7×24 小时运行。
- 定时任务不重复。
- Telegram 推送稳定。
- 文字内容具备判断力。
- Alert 不制造通知疲劳。
- 文档随版本同步更新。
