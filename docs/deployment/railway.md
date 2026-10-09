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

## Gate 2.3 状态连续性（2026-10-09）

生产需要专用 Railway Volume 挂载 `/data`；不能覆盖 `/app`。
自动 `RAILWAY_VOLUME_MOUNT_PATH=/data` 解析为 `/data/fiona`，无需改变产品变量。
可选 `FIONA_STATE_DIR` 只能在该 Volume 内。
新容器不会把缺失状态当成新安装：缺失挂载、manifest、关键账本/记忆或损坏时暂停发送。
上线先部署 fail-safe，再挂载、迁移真实账本与 Alert 记忆，manifest 最后写入。
正常重启/替换实例保留成功记录、冷却和生命周期。
迁移使用 `python3 -m app.fiona_state_migration --bundle <私有备份> --root /data/fiona --boundary <含时区时间>`。
该命令不运行任务、不发送 Telegram；已过未知任务由明确切换边界排除，不伪造成功。
异常损坏需要人工审阅备份恢复，不能自动清空；保留 Volume，不盲目回滚到旧 ephemeral runtime。
详见 [Gate 2.3](../v3_1/gates/GATE_2_3_PRODUCTION_STATE_CONTINUITY.md)。
