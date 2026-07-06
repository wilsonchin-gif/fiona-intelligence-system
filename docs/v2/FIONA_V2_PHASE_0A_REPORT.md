# Fiona V2 Phase 0A Report

版本：Phase 0A  
状态：Completed / Awaiting Wilson Review  
负责人：Wilson / Codex  
更新时间：2026-07-04

## 1. Goal

Phase 0A 目标：

1. 验证 Production Scheduler 是否存在任务漏执行风险。
2. 设计 V2 核心数据 Contract。
3. 不改变当前用户可见行为。
4. 不开始 V2 业务功能开发。

## 2. Repository Gate

Repository:

```text
/Users/mac/Desktop/Wilson AI Lab/Fiona Intelligence Platform/03_Development/fiona-intelligence-system
```

Git root:

```text
/Users/mac/Desktop/Wilson AI Lab/Fiona Intelligence Platform/03_Development/fiona-intelligence-system
```

Origin:

```text
https://github.com/wilsonchin-gif/fiona-intelligence-system.git
```

Current HEAD:

```text
2295e01b8918efca5f1b9250ae3d40e96c85d2dd
```

Status before Phase 0A:

- `main` ahead `origin/main` by 1 commit.
- Existing untracked docs were present.
- This phase did not overwrite existing untracked docs.

## 3. Decisions

### Decision 1: V2 contracts live in a new module

File:

```text
app/fiona_contracts.py
```

Reason:

- Keeps Production V1 `app/fiona_types.py` untouched.
- Avoids changing current runtime imports.
- Allows V2 contracts to mature independently.

### Decision 2: Scores may be null

If score data is insufficient:

```text
value = null
status = insufficient_data
```

Reason:

- Fiona must not generate fake precision.

### Decision 3: Railway JSON memory is EPHEMERAL

Current Railway file memory is classified as:

```text
EPHEMERAL
```

Reason:

- Container filesystem cannot be treated as durable storage across redeploys.

### Decision 4: Scheduler fix is deferred

Phase 0A only audits scheduler risk.

No scheduler code was changed.

## 4. Contracts Created

Created:

- Event Object V2 Contract
- Governance Contract
- Score Contract
- Routing Contract
- Alert Contract
- Memory Persistence Contract
- Tag Contract

## 5. Assumptions

- Fiona Production V1 must remain stable.
- Telegram output must not change in this phase.
- Alert remains disabled unless explicitly enabled outside this phase.
- V2 should be additive and backward-compatible.
- PostgreSQL is not required until Knowledge Graph/Search becomes production scope.

## 6. Unresolved Questions

1. Should Phase 0B change `WILSON_INTERVAL_MINUTES` operationally, or should code implement next-run scheduling first?
2. Should schedule ledger use JSON in V1/V2 transition, or wait for DB?
3. Which source registry should define source independence for financial media syndication?
4. What is Fiona's canonical tag language policy for Chinese-first output with English hashtags?
5. Should Image Intelligence be part of V2.0 or V2.1?

## 7. Backward Compatibility

Preserved:

- Existing `FionaEvent` unchanged.
- Existing runtime unchanged.
- Existing brief templates unchanged.
- Existing Telegram sender unchanged.
- Existing Alert switch unchanged.
- Existing Railway config unchanged.

## 8. Risks

### Scheduler risk

Confirmed.

With 240-minute polling and 15-minute due window, non-midnight tasks can be missed.

### Contract adoption risk

Low now, because V2 contracts are not imported by production runtime.

### Data risk

High for future V2 scoring and alerting unless ETF net flow, liquidation, OI/funding, official filings and source verification are added later.

## 9. Tests Added

File:

```text
tests/test_fiona_phase0a_contracts.py
```

Coverage:

- Event V2 optional fields.
- Backward compatibility from V1 event.
- Confirmed Fact Rule A.
- Confirmed Fact Rule B.
- Insufficient sources.
- Duplicate source independence.
- Score null when insufficient data.
- Multi-route.
- Material Change classification.
- PersistenceClass.
- Tag canonicalization.
- Telegram hashtag normalization.
- Scheduler 240-minute delivery risk simulation.

## 10. Validation

Commands run:

```text
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest tests.test_fiona_phase0a_contracts
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover -s tests
```

Result:

```text
Ran 48 tests
OK
```

## 11. Next Phase Recommendation

Recommended Phase 0B:

1. Decide scheduler repair path.
2. Prefer short polling as immediate operational mitigation.
3. Design schedule ledger before modifying production scheduler.
4. Keep V2 contracts unused by runtime until Wilson approves.

Do not begin Knowledge Graph, Academy, Narrative Challenge, real Market Anomaly Alert, or DB work yet.

