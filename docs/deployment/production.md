# Fiona Production Operations

版本：V1.0.0  
状态：Active  
负责人：Wilson  
更新时间：2026-06-26

## 1. 生产检查

每次部署后检查：

- Railway deploy 是否成功。
- `send` 是否符合变量预期。
- Telegram 是否成功发送。
- 日志是否有 error。
- Alert 是否按环境变量关闭或 dry-run。

## 2. 回滚策略

如果生产异常：

1. 在 Railway 回滚到上一 deploy。
2. 将 `WILSON_SEND=0` 暂停推送。
3. 检查 `fiona_status.json` 与 push log。

## 3. 日志

核心日志：

- `fiona_telegram_push.log`
- `fiona_status.json`
- Railway deploy logs
