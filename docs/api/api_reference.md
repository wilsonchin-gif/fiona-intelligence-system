# Fiona API Reference

版本：V1.0.0  
状态：Draft  
负责人：Wilson  
更新时间：2026-06-26

## 1. 当前状态

Production V1 暂无对外 HTTP API。

## 2. 当前内部命令

运行 scheduler：

```bash
python3 -m app.fiona_runtime --send run-scheduler
```

运行一次：

```bash
python3 -m app.fiona_runtime --brief daily run-once
```

Dry Run：

```bash
WILSON_SEND=0 python3 -m app.fiona_runtime --brief daily --send run-once
```

## 3. 未来 API

规划：

- `/health`
- `/brief/latest`
- `/alerts`
- `/narratives`
- `/admin/runtime`
