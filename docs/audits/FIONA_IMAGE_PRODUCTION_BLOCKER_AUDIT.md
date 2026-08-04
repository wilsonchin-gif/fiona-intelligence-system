# Fiona Image Production Blocker Audit

版本：V2 Phase 2 Same-Day Launch
状态：Local remediation complete; production validation pending
负责人：Wilson / Codex
更新时间：2026-08-04 UTC+8

## 1. Executive Finding

The image pipeline was not the cause of the missing Market News shadow metrics.
The `2026-08-04 00:00` Market News occurrence was discovered at `00:48:10` with
a previous-day `22:30` Daily catch-up. The former arbitration formula favored
Daily's static priority even though Daily was older and crossed the local date.
Market News was therefore recorded as `suppressed_collision` before the delivery
coordinator could build a ViewModel, caption, or PNG.

## 2. Production Ground Truth

- Railway service: `fiona-intelligence-system`
- deployment status: `SUCCESS`
- source commit before remediation: `a7a584074d0747866ec5624abc8dd3482a5fa1a0`
- start command: `python3 -m app.fiona_runtime --send run-scheduler`
- replicas: `1`
- mode: `shadow`
- interval: `5 minutes`
- timezone: `Asia/Hong_Kong`
- scheduler: online; observed cycles returned `ok=true`
- observed deployment restart/crash loop: none

## 3. Old Decision Path

```text
Occurrence discovery
  -> Daily 22:30 (age 138m, catch-up)
  -> Market News 00:00 (age 48m, catch-up)
  -> 180m collision group
  -> old static-weight score
     Daily: 400 - 138/2 = 331
     Market News: 200 - 48/2 = 176
  -> Daily SEND
  -> Market News suppressed_collision
  -> DeliveryCoordinator never entered
```

`ScheduledOccurrence.catch_up` is true for any detection after its exact
scheduled instant, including an ordinary five-minute poll. The old formula's
normal bonus therefore did not distinguish a fresh five-minute occurrence from
an old catch-up reliably.

## 4. Historical Evidence Limit

One same-pattern collision is confirmed from the retained deployment logs:
`market_news:2026-08-04T00:00:00+08:00`. Exact counts and success rates for
2026-07-29 through 2026-08-04 cannot be reconstructed because removed Railway
deployment logs and the ephemeral local JSON ledger are no longer available.
No estimate is presented as a measured count.

The failure is deterministic when the same candidate ages are presented. A
restart at 00:48 exposed it, but restart timing was the trigger, not the root
cause.

## 5. Options Reviewed

| Option | Result |
|---|---|
| A. Raise Market News static priority | Rejected: swaps one hard-coded bias for another. |
| B. Shorten Daily catch-up only | Insufficient alone: other stale cross-day collisions remain possible. |
| C. Layer normal/date/freshness arbitration | Selected: matches product timeliness and is explainable. |
| D. Explicit previous-day Daily protection | Selected through expiry and current-day preference. |

## 6. Selected Remediation

1. Normal means occurrence age `<=10 minutes`, independent of the raw catch-up flag.
2. Normal candidates beat catch-up candidates.
3. Current-local-day candidates beat previous-day candidates.
4. Catch-up candidates use lower age before static priority.
5. All-normal ties use semantic static priority.
6. Daily catch-up is limited to 120 minutes and never survives after next-day 00:30.
7. Expired candidates are filtered and recorded before arbitration.
8. Collision losers are terminally suppressed; no new deferral is emitted.

## 7. Shadow Validation Decoupling

Suppressed-occurrence render-only execution was not added. Running the full data
fetch, lifecycle, narrative, caption, and renderer inside a suppression branch
would add external latency and a second side-effect path to scheduler arbitration.
It would also complicate the meaning of occurrence completion. The independent
production-safe validation command provides the same technical verification
without Telegram or scheduler state mutation.

## 8. Production-Safe Validation

Command:

```bash
python3 -m app.fiona_runtime validate-market-news-image
```

The command uses the production snapshot builder, event conversion, lifecycle
processing in memory, narrative generation, current ViewModel, Caption RC,
Pillow renderer, and PNG validator. It does not call Telegram, create an
occurrence, update `last_check_at`, or save the scheduler ledger. Output is one
JSON line and excludes the full caption.

## 9. Test Scope

- normal vs catch-up in both directions
- current-day vs previous-day
- normal semantic priority and catch-up freshness
- Daily validity and next-day expiry
- 00:05 and 00:48 midnight collisions
- Monday Weekly/Daily/Market News collision
- suppression terminality and no delayed retry
- one-send collision behavior
- seven-day continuous scheduler simulation
- Caption RC sections, safety, and hash-only logging
- PNG dimensions, size, validation, and cleanup
- zero Telegram calls and zero ledger mutation in validation

Final local regression on 2026-08-04: `189 tests`, all passed. Python compile
completed successfully. A real-data local runtime validation also passed with
Caption length `517`, PNG `1080x1350`, PNG size `306068 bytes`, cleanup success,
and zero Telegram or scheduler-ledger mutation. This is not represented as the
required Railway production-image validation.

## 10. Remaining Production Gates

- deploy the remediation commit while mode remains `shadow`
- run the validation command inside the deployed Railway image
- confirm PNG `1080x1350`, `<1.5 MB`, cleanup success, and zero API calls
- only then change the single variable to `image`
- inspect the first live occurrence for one document, no text duplicate

## 11. Rollback

1. `image -> shadow`
2. if rendering remains unstable, `shadow -> text`
3. if duplicate risk appears, isolate delivery with `WILSON_SEND=0` only when necessary
4. inspect ledger before any manual resend
