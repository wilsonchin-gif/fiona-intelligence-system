# Fiona Railway Deployment

版本：V1.0.0  
状态：Active  
负责人：Wilson  
更新时间：2026-06-26

## 1. Railway 启动命令

```bash
python3 -m app.fiona_runtime --send run-scheduler
```

## 2. 部署来源

```text
GitHub main -> Railway deploy
```

## 3. 生产建议

- 使用 `WILSON_SEND=1` 控制是否真实推送。
- Alert 默认关闭。
- 所有变量在 Railway Variables 中配置，不写入代码。
