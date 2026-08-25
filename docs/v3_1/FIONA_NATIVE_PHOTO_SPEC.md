# Fiona Native Photo Specification

- Version: V3.1-alpha.1
- Status: Implemented behind legacy-safe flag
- Updated: 2026-08-25

## Product Contract

Native photo mode delivers one 4:5 PNG through Telegram `sendPhoto` with a short
plain-text caption. The image is the product; the caption is its editorial
summary. Gate 1 does not activate this mode in production.

## Transport Flag

`FIONA_TELEGRAM_MEDIA_MODE=document|photo`

- Default and invalid fallback: `document`.
- Parsing: trim whitespace, case-insensitive.
- Scope: transport and render profile only.
- It must not alter cadence, content selection, sources, or ViewModel inputs.

## Native Image Profile

| Property | Contract |
|---|---|
| Canvas | 1440 x 1800 |
| Aspect | 4:5 |
| Renderer | Direct Pillow render |
| Format | PNG |
| Color | RGB or validated RGBA |
| File boundary | Greater than 0 and less than 1.5 MB |
| Outer margin | At least 72 px |
| Safe top/bottom | At least 48 px |
| Minimum token text | At least 17 px |

The renderer must not resize or upscale a 1080 x 1350 card. Design System 1.0
tokens and components remain authoritative; the iOS profile changes scale and
safe geometry, not information density.

## Telegram Request

`send_photo_with_caption(path, caption, parse_mode=None)` uses multipart form
data with `chat_id`, `photo`, optional `caption`, and optional `parse_mode`.
Files are read inside a context manager. Responses are parsed as structured
JSON and must contain a usable `message_id` before the coordinator declares
success.

## Failure Semantics

| Result | Classification | Action |
|---|---|---|
| Success + message ID | success | terminal photo |
| HTTP 4xx | definite failure | one text fallback |
| Telegram `ok=false` | definite failure | one text fallback |
| Timeout | unknown | no retry/fallback |
| Network/connection loss | unknown | no retry/fallback |
| HTTP 5xx | unknown | no retry/fallback |
| Malformed/invalid response | unknown | no retry/fallback |
| Renderer/caption/PNG failure | definite local failure | one text fallback |

There is no photo -> document -> text chain and no Telegram-service retry.

## Temporary Files

Each render uses an isolated temporary directory. Cleanup runs after success,
failure, or unknown delivery. Cleanup failure is observable but does not cause
a second Telegram send.

## Observability and Security

Allowed telemetry includes mode, locale, dimensions, bytes, durations, caption
length, send status, fallback, final channel, terminal state, cleanup, and error
category. Bot Token, Chat ID, full caption, credentials, and full source payload
are prohibited. Telegram URLs and token-shaped strings are sanitized.

## Rollback

Set `FIONA_TELEGRAM_MEDIA_MODE=document`. No code, Scheduler, or ledger migration
is required.
