# Fiona Telegram Deployment

版本：V1.0.0  
状态：Active  
负责人：Wilson  
更新时间：2026-06-26

## 1. 发送目标

生产推荐：

```env
TELEGRAM_GROUP_ID=
```

兼容：

```env
TELEGRAM_CHAT_ID=
TELEGRAM_CHANNEL_ID=
```

## 2. 发送链路

```text
Fiona Runtime -> telegram_service -> Telegram Bot API
```

## 3. 当前发送方式

Production V1 以文字推送为主。

图片恢复时使用：

```text
sendDocument
```
