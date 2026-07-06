# Fiona Delivery Arbitration Policy

版本：Phase 0B.1  
状态：Implemented locally, not committed  
负责人：Wilson / Codex  
更新时间：2026-07-06

## 1. Purpose

Delivery arbitration prevents notification fatigue when multiple scheduled or catch-up brief occurrences are discovered in the same scheduler cycle.

This policy does not delete scheduled tasks and does not change fixed task times.

## 2. Actions

```text
SEND
SUPPRESS
DEFER
```

V2.0 does not implement message merging.

## 3. Priority

| Brief | Priority |
|---|---:|
| Weekly | 500 |
| Daily | 400 |
| Evening | 300 |
| Morning | 300 |
| Market News | 200 |

Priority is combined with freshness, catch-up age, and semantic overlap. It is not a simple delete-by-priority rule.

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
2. Daily suppresses stale Evening catch-up when both collide.
3. Weekly catch-up prevents Monday triple push with Daily and Market News.
4. Market News may be deferred when a higher-value Weekly is due nearby.
5. Morning is not replaced by previous-night stale briefs.

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

Deferred occurrences are recorded as:

```text
deferred_collision
```

with:

```text
defer_until
```

## 7. Known Limits

This is not distributed arbitration. If Railway runs multiple replicas, duplicate sends remain possible.

