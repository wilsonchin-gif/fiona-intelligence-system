# ADR 007: Global Editorial Coverage Architecture

- Status: Accepted
- Date: 2026-09-03
- Decision owners: Wilson / Fiona Product / Fiona Engineering
- Scope: Fiona V3.1 Gate 2

## Context

Gate 0 found source-list drift, effective European coverage near zero, ROW
coverage at zero, and a large Global/Unknown share. Applying a mathematical
6:3:1 split to that pool would create false global coverage.

## Decision

1. `config/sources.json` is the single source registry for legacy and new feeds.
2. Allocation uses event region, not publisher region.
3. 60/30/10 is a dynamic target, not a hard quota.
4. A deterministic quality floor prevents weak regional filler.
5. Material events override regional balance and record the reason.
6. Source count and independent-source count remain separate.
7. Deterministic clustering precedes ranking.
8. Legacy remains user-visible while Global 6:3:1 runs in Shadow.
9. Production activation requires 14 days and at least 100 qualified clusters,
   unless Product explicitly approves a different evidence threshold.

## Why

This preserves editorial quality, prevents syndication from inflating
confidence, makes provenance auditable, and lets Fiona measure global coverage
without risking Gate 1 production behavior.

## Alternatives Considered

- Hard per-edition quotas: rejected because they promote weak or stale stories.
- Publisher-headquarters allocation: rejected because it misclassifies global
  publishers covering regional events.
- Embeddings/vector database: deferred; deterministic bounded clustering is
  sufficient for Gate 2 and easier to audit.
- Immediate production switch: rejected because current source health and
  long-run distribution have not completed Shadow observation.

## Consequences

- Source metadata and adapters become production-critical configuration.
- Source outages are explicit health events rather than silent “no news.”
- The first release remains `PASS WITH CONDITIONS` until observation closes.
- Railway file-based observation state remains ephemeral; logs are required.

## Rollback

Keep `FIONA_COVERAGE_PROFILE=legacy`. The Shadow evaluator is failure-isolated
and can be reverted as one bounded Gate 2 commit without changing Scheduler or
Telegram transport.
