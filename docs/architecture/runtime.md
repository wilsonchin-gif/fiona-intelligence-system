# Fiona Runtime

版本：V1.0.0  
状态：Active  
负责人：Wilson  
更新时间：2026-06-26

## 1. 生产入口

```bash
python3 -m app.fiona_runtime --send run-scheduler
```

## 2. Scheduler

Scheduler 轮询间隔读取优先级：

1. `WILSON_INTERVAL_MINUTES`
2. `FIONA_RUNTIME_INTERVAL_MINUTES`
3. Runtime default

固定任务时间不受轮询变量改变：

- 00:00 Fiona Market News
- 07:30 Fiona Morning
- 20:30 Fiona Evening
- 22:30 Fiona Daily
- 周日 21:00 Fiona Weekly

## 3. 发送开关

发送开关读取优先级：

1. `WILSON_SEND`
2. `FIONA_SEND`
3. `FIONA_SEND_TELEGRAM`

生产推荐只使用：

```env
WILSON_SEND=1
```

## 4. Alert

Alert Engine 默认关闭：

```env
FIONA_ALERT_ENABLED=0
FIONA_ALERT_DRY_RUN=1
```
