# Fiona V3 Visual Experience Release Plan

- Version: V3.0.0
- Status: Production Release
- Owner: Fiona Product / Engineering / Release
- Updated: 2026-08-05

## 1. Objective

将 Production V2.4 的工程输出升级为专业金融情报卡，同时保持现有数据模型、调度、运行时、Telegram Delivery 和 Railway 配置不变。

## 2. Release Boundary

Include: `app/design_tokens.py`、`app/fiona_card_components.py`、`app/fiona_card_renderer.py`、相关 renderer tests、Design System 文档、Release Notes、Version Matrix、CHANGELOG、Architecture Snapshot 与 ADR 006。

Exclude: `reports/`、PNG 原型、原型生成脚本、缓存、临时文件、历史草稿、无关未跟踪文件、Scheduler、Runtime、Telegram、Railway 与环境变量。

## 3. Gates

1. Product Gate: Full / Missing / Stress 人工视觉验收。
2. Engineering Gate: compile + full unit tests。
3. Release Boundary Gate: 仅 Renderer、tests、scripts、docs 有 tracked diff。
4. Production Validator Gate: 验证 1080×1350、<1.5 MB、中文字体、cleanup、Telegram calls = 0 与 ledger mutations = 0。
5. Deployment Gate: Railway 自动部署，保持现有 `image` mode 和所有环境变量。
6. Runtime Gate: 至少观察三个 scheduler cycles，并验收下一次 Market News image delivery。

## 4. Rollback

若 renderer 在生产失败，执行 `git revert <V3.0.0 release commit>` 并允许 Railway 自动部署。不得修改 Scheduler。现有 delivery fallback 行为继续保留。

## 5. Current Decision

V3.0.0 批准为 Production Release。发布只包含 presentation layer，生产 mode 保持 `image`，不修改 Scheduler、Runtime、Telegram Delivery、Railway Variables、ledger 或 arbitration。
