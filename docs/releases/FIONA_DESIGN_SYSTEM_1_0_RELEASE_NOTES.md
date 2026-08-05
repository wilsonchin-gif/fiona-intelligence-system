# Fiona Design System 1.0 Release Notes

- Version: V3.0.0 / Design System 1.0
- Date: 2026-08-05
- Status: Production Release
- Production baseline: V2.4 (`0738adb`)

## Highlights

- 建立集中式 Design Token System。
- 将 Market News Renderer 重构为可复用、可隔离测试的组件系统。
- 将 Today's Judgement 固定为视觉中心，Evidence 和 Market Regime 作为次级信号。
- 引入低对比 `FIONA INTELLIGENCE` 品牌签名。

## New Files

- `app/design_tokens.py`
- `app/fiona_card_components.py`
- `tests/test_fiona_design_system.py`
- Design System、Language、Component、Token、Renderer 与 Visual Review 文档。

## Compatibility

无 Scheduler、Runtime、Telegram Delivery、Railway、环境变量、ledger 或 arbitration 变更。

## Validation

- Full / Missing / Stress 原型。
- Token consistency、component isolation、layout、typography 与 deterministic snapshot tests。
- Production validation：1080×1350、PNG validation passed、Telegram calls = 0、ledger mutations = 0。

## Known Limitations

- 本版本只覆盖 Market News Card。
- 其他 Brief 尚未迁移到组件库。
- 生产继续使用既有 `image` mode；本次发布不修改变量。
