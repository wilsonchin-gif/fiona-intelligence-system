# Fiona V2 Contracts

版本：V2.0 Phase 0A  
状态：Contract Design  
负责人：Wilson / Codex  
更新时间：2026-07-04

## 1. Scope

本文件定义 Fiona V2 的核心数据 Contract。

本阶段不改变 Production V1 输出，不改变 Telegram 行为，不改变 scheduler 行为，不开启 Alert。

实现位置：

- `app/fiona_contracts.py`

选择新建 `app/fiona_contracts.py` 的原因：

- `app/fiona_types.py` 是 Production V1 当前运行对象所在地。
- 直接扩展 V1 类型可能增加生产行为风险。
- V2 Contract 需要 Governance、Routing、Alert、Tag、Score 等跨域结构，独立模块更清晰。
- 现有 imports 不受影响。

## 2. Event Object V2 Contract

Canonical object:

```text
FionaEventV2Contract
```

字段：

| Field | Type | Null / Default Semantics |
|---|---|---|
| `schema_version` | `str` | 默认 `2.0` |
| `event_id` | `str` | 必填 |
| `title` | `str` | 必填 |
| `event_type` | `str` | 必填；兼容 V1 `category.value` |
| `detected_at` | `datetime` | 必填；必须 timezone-aware，naive 会补 UTC |
| `occurred_at` | `datetime | None` | 可空；未知真实发生时间时为 null |
| `verification_status` | `VerificationStatus` | 默认 `Unverified` |
| `sources` | `list[EvidenceRecord]` | 默认空 |
| `source_count` | `int` | 默认 0；sources 非空时自动取 `len(sources)` |
| `entities` | `list[str]` | 默认空；实体尚未抽取时为空 |
| `assets` | `list[str]` | 默认空；兼容 V1 `affected_assets` |
| `markets` | `list[str]` | 默认空；未映射时为空 |
| `tags` | `list[FionaTag]` | 默认空 |
| `importance_score` | `ScoreRecord` | 默认 unavailable/null |
| `confidence_score` | `ScoreRecord` | 默认 unavailable/null |
| `urgency_score` | `ScoreRecord` | 默认 unavailable/null |
| `impact_score` | `ScoreRecord` | 默认 unavailable/null |
| `novelty_score` | `ScoreRecord` | 默认 unavailable/null |
| `persistence_score` | `ScoreRecord` | 默认 unavailable/null |
| `cross_market_score` | `ScoreRecord` | 默认 unavailable/null |
| `narrative_score` | `ScoreRecord` | 默认 unavailable/null |
| `risk_score` | `ScoreRecord` | 默认 unavailable/null |
| `lifecycle_status` | `str | None` | 可空；兼容 V1 lifecycle |
| `routes` | `list[RouteDecision]` | 默认空；支持 multi-route |
| `parent_event_id` | `str | None` | 可空；用于未来 clustering |

Backward compatibility:

- `FionaEventV2Contract.from_v1_event(event)` 可从现有 `FionaEvent` 生成 V2 Contract。
- 不要求 Production V1 立即迁移。
- V1 分数字段映射为 `ScoreStatus.HEURISTIC`。

## 3. Governance Contract

Enums:

```text
VerificationStatus:
Confirmed / Probable / Developing / Unverified / Conflicting / False / Stale / Manipulated

SourceType:
Primary / Official / Authoritative / MajorMedia / Specialist / MarketData / Social / Anonymous / Unknown

EpistemicType:
Fact / Inference / Hypothesis / Scenario / Opinion
```

Evidence object:

```text
EvidenceRecord
├── source_id
├── source_name
├── source_type
├── source_identity
├── independence_group
├── url
├── claim
├── epistemic_type
└── observed_at
```

Verification output:

```text
VerificationDecision
├── status
├── rule
├── reason
├── source_count
├── independent_source_count
└── evidence_source_ids
```

Confirmed Fact Rule:

```text
Rule A:
>= 3 independent sources

OR

Rule B:
1 Primary Source
+
1 independent Authoritative / Official supporting source
```

Important rule:

- Duplicate syndication does not count as independent sources.
- LLM cannot independently mark a claim as Confirmed.
- Source independence is represented by `independence_group`.

## 4. Score Contract

V2 score dimensions:

- Importance
- Confidence
- Urgency
- Impact
- Novelty
- Persistence
- Cross-Market
- Narrative
- Risk

Object:

```text
ScoreRecord
├── value: int | None
├── status: ScoreStatus
├── evidence: list[str]
├── data_support: str
├── calculation_method: str
└── updated_at: datetime
```

ScoreStatus:

```text
supported
heuristic
insufficient_data
unavailable
```

Rule:

- If `status` is `insufficient_data` or `unavailable`, `value` is forced to `null`.
- Fiona must not fill fake numbers just to make a template complete.

## 5. Routing Contract

Routes:

- Ignore
- Store Only
- Watch
- Market News
- Morning
- Evening
- Daily
- Weekly
- Alert

Object:

```text
RouteDecision
├── route
├── reason
├── confidence
└── decided_at
```

Future routes reserved but not implemented:

- Academy
- Today's Asset
- Deep Research
- Timeline Update

## 6. Alert Contract

AlertType:

- Information
- MarketAnomaly

AlertStatus:

- Developing
- Confirmed
- Updated
- Resolved
- Retracted

CauseStatus:

- Known
- Probable
- Unknown
- Conflicting

Material Change dimensions:

- verification change
- risk level change
- impact expansion
- cause confirmation
- cause invalidation
- cross-market contagion
- price regime change
- flow reversal
- official response
- lifecycle change

Current implementation:

- Contract only.
- No production Alert behavior change.
- No real push.

## 7. Memory Persistence Contract

PersistenceClass:

- `EPHEMERAL`
- `LOCAL_DURABLE`
- `EXTERNAL_DURABLE`

Memory types:

- Event History
- Alert History
- Route History
- Verification History
- Lifecycle History

Current Railway JSON memory classification:

```text
EPHEMERAL
```

Reason:

- Railway container filesystem JSON should not be described as durable memory.
- Redeploy/rebuild can lose local files.

## 8. Tag Contract

TagType:

- Market
- Narrative
- Asset
- Institution
- Person
- Concept
- Risk
- Event
- Policy
- Geography

Object:

```text
FionaTag
├── canonical_id
├── display_name
├── tag_type
├── aliases
└── telegram_hashtag
```

Rules:

- Internal tag and Telegram hashtag are not the same object.
- `canonical_id` may preserve Chinese.
- `telegram_hashtag` is normalized to ASCII-safe `#...`.
- Spaces and punctuation are collapsed to `_`.
- Numeric-leading hashtags are prefixed with `Fiona_`.

## 9. Backward Compatibility

No existing Production V1 module imports `app.fiona_contracts.py`.

Therefore:

- Production V1 output unchanged.
- Telegram behavior unchanged.
- Alert remains controlled by current env.
- Scheduler unchanged.

