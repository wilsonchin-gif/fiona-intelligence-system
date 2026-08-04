# Fiona Delivery Arbitration Policy

版本：Phase 2 Image Launch Hardening
状态：Implemented locally, release validation pending
负责人：Wilson / Codex  
更新时间：2026-08-04

## 1. Purpose

Delivery arbitration prevents notification fatigue when multiple scheduled or catch-up brief occurrences are discovered in the same scheduler cycle.

This policy does not delete scheduled tasks and does not change fixed task times.

## 2. Actions

```text
SEND
SUPPRESS
```

`DEFER` remains readable for backward compatibility with existing ledger entries,
but new collision decisions do not emit it. A collision loser is terminally
suppressed so it cannot create a delayed second or third notification.

## 3. Priority

| Brief | Priority |
|---|---:|
| Weekly | 500 |
| Daily | 400 |
| Evening | 300 |
| Morning | 300 |
| Market News | 200 |

Static priority is only a final tie-breaker. Winner selection is layered:

1. normal occurrence (age <= 10 minutes) over catch-up
2. current local date over previous local date
3. lower occurrence age for catch-up candidates
4. static semantic priority

When all remaining candidates are normal, semantic priority resolves the tie.

## 4. Collision Window

```text
180 minutes
```

This covers:

- Evening vs Daily
- Weekly vs Daily
- Daily vs Market News
- Weekly vs Market News

It avoids suppressing unrelated tasks many hours apart.

## 5. Minimum Rules

1. Fresh scheduled occurrence beats older catch-up occurrence.
2. Current-day content beats previous-day content.
3. Daily suppresses stale Evening catch-up when both collide near 22:30.
4. Current-day Market News suppresses previous-day Daily or Weekly catch-up.
5. Catch-up candidates are ranked by freshness before static priority.
6. Collision losers are terminally suppressed; no delayed double/triple push.
7. Morning is not replaced by previous-night stale briefs.

## 6. Ledger Audit

Suppressed occurrences are recorded as:

```text
suppressed_collision
```

Fields:

```text
suppressed_by_occurrence_id
suppression_reason
arbitrated_at
```

Legacy deferred occurrences remain readable as:

```text
deferred_collision
```

with:

```text
defer_until
```

No new `deferred_collision` decision is emitted by the Phase 2 policy.

## 7. Daily Expiry

Daily catch-up has a maximum age of `120 minutes`. A previous-day Daily is also
expired after local `00:30`. Expired candidates are marked `skipped_expired`
before collision arbitration and therefore cannot suppress a valid Market News
occurrence.

## 8. Known Limits

This is not distributed arbitration. If Railway runs multiple replicas, duplicate sends remain possible.
