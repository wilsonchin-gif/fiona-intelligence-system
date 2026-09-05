# Fiona Version Changelog

版本：V3.1-alpha.2
状态：Implemented / Shadow Candidate; Global selection not activated
负责人：Wilson  
更新时间：2026-09-05

## Gate 2.1 - Shadow Editorial Observability

日期：2026-09-05；Commit：`Add Fiona Shadow editorial observability`（SHA 见 Git）。

- 新增入选事件的限量审计投影和 compact JSON 日志，保留实际 occurrence ID、排名、标题、来源与独立性、已有评分及覆盖理由。
- 扩展既有 Shadow 历史和安全验证输出；不新增存储系统，不调整排序、选源、Telegram、Scheduler、Ledger 或开关。
- 修复汇总日志无法支持逐条编辑审阅的问题；不回填历史标题，不重置 2026-09-04 观察起点。
- HKMA 保持 WATCH；独立确认数问题仅观测。Gate 2 保持 PASS WITH CONDITIONS，Gate 3 LOCKED。
- 固定排序和指标基线等价；22 项专项、381 项全量测试及编译通过。首轮生产明细待自然任务验收。

## V3.1-alpha.2 - Global Coverage Engine

日期：2026-09-03

Commit：本条目随 `Implement Fiona V3.1 global coverage engine` 提交；SHA 由 Git 记录。

影响范围：Source Registry / Provenance / Shadow Ranking / Coverage Metrics / Tests / Documentation

- 新增单一来源注册表、8 个 Shadow-only 官方来源适配器、事件地区与来源地区分离、独立来源计数。
- 新增确定性聚类、URL/转载去重、时效与质量门槛、重大事件覆盖和动态 6:3:1 排序。
- 修复硬编码来源列表与配置漂移；保留原 7 个 legacy 来源的顺序、权重和输出责任。
- 新增仅观测的 24h/7d 指标与无 Telegram、ledger、occurrence 副作用的验证入口。
- 原始标题、语言、链接和发布时间保留；无时间戳不伪造为当前时间；缺少文章链接不伪造为共享源链接。
- 不修改 Scheduler、Telegram transport、Alert、cadence、Delta、Railway Variables。
- `FIONA_COVERAGE_PROFILE=legacy` 保持选题权威；不声明 Global Coverage 已激活。
- 来源缺口和本地 ECB TLS 验证问题保留为显式风险；不绕过访问限制。
- 下一步：生产 Shadow 14 天、至少 100 个不同的合格事件簇；Gate 3 继续锁定。

## V3.1-alpha.1 - Gate 1 Production Closeout

日期：2026-09-03

Commits：`d0ea66931bdedf0cacbf3df451379ddbd327ea67`、`87d046884375fe0fc64fe8e35e009f04dad77c46`

影响范围：Documentation / Product Acceptance / Version Records

### 验收完成

- Native Telegram Photo、1440 x 1800 iOS Renderer 与 Market News `en-US` 通过生产验收。
- Morning、Evening 与自然 Alert 的 `en-US` 真实生产消息通过；Daily 与 Weekly 通过 production-safe 验证。
- Wilson 完成真实 iPhone 九项验收：内嵌图片、无附件名、完整可见、正文与 Fiona's View 可读、无裁切、英文自然、Caption 简短且无重复。
- 生产 CJK leakage、Scheduler、ledger 与 runtime 健康检查通过。

### 当前边界

- 生产媒体为 `photo`，输出语言为 `en-US`。
- Coverage 与 cadence 保持 `legacy`，4H Delta 保持 `off`。
- Gate 1 正式关闭；Gate 2 尚未开始；V3.1 GA 未声明。

## V3.1-alpha.1.1 - American English Surface Completion

日期：2026-09-02

Commit：`87d046884375fe0fc64fe8e35e009f04dad77c46`

影响范围：Output Locale Boundary / Morning / Evening / Daily / Weekly / Alert / Tests / Documentation

### 新增内容

- 将统一 `en-US` 输出边界扩展到 Morning、Evening、Daily、Weekly、Alert、缺失数据与安全 fallback。
- 新增共享英文术语、Alert 严重度映射、确定性事件英文投影和全用户面 CJK leakage guard。
- 新增无 Telegram、ledger、scheduler 和正式 occurrence 副作用的全表面验证命令。

### 修复内容

- 修复 runtime 仅在 Market News 分支读取 `FIONA_OUTPUT_LOCALE`，导致其他生产消息继续输出中文或双语的问题。
- 修复 en-US 模式下 snapshot 构建失败时缺少安全英文 fallback 的问题。

### 优化内容

- 时间统一为 `SEP 02 · 20:00 UTC+8` 样式，免责声明统一为简短 en-US 版本。
- 中文源事实与 provenance 保持原样，用户面改用保守的分类规则生成英文，不引入外部翻译服务。

### 删除内容

- 未删除生产代码、中文 legacy 模式、来源、任务、Alert 阈值、ledger 或 Telegram 能力。

### 影响范围

- `FIONA_OUTPUT_LOCALE=en-US` 下的剩余生产用户面已随部署切换为英文并完成 Gate 1 验收。
- Scheduler、cadence、coverage、delta、Railway Variables 与 Telegram transport 语义不变。
- Gate 2 未开始。

## V3.1-alpha.1 - Native Telegram Photo + American English

日期：2026-08-25

Commit：`d0ea66931bdedf0cacbf3df451379ddbd327ea67`

影响范围：Market News Transport / iOS Renderer / Locale Boundary / Tests / Documentation

### 新增内容

- 新增 `FIONA_TELEGRAM_MEDIA_MODE=document|photo`，默认 `document`。
- 新增 `FIONA_OUTPUT_LOCALE=zh-CN|en-US`，默认 `zh-CN`。
- 新增 production-grade `sendPhoto`、1440 x 1800 原生 Pillow profile、短 Caption、CJK leakage guard 与来源 provenance sidecar。
- 新增 photo definite/unknown delivery 分类、一次 text fallback、结构化 observability 与 production-safe validator。

### 修复内容

- 补齐原有 photo helper 缺少 Caption、错误分类、未知交付保护和 message ID 验证的问题。
- 保护 photo timeout、5xx、network 与 malformed response，避免不确定状态触发重复发送。

### 优化内容

- Market News 的确定性用户文案、时间、缺失状态、Disclaimer 与 Caption 统一通过 locale boundary。
- iOS profile 提高像素清晰度与安全边距，不增加信息密度，不放大旧图。

### 删除内容

- 未删除生产代码、任务、来源、ledger 或 Telegram document 能力。

### 影响范围

- 默认生产行为不变：`document + zh-CN`。
- Scheduler、cadence、Railway Variables、source coverage、Morning、Evening、Daily、Weekly 与 Alert 均未改变。
- `photo + en-US` 需要独立 Product Review 后才能激活；Gate 2 未开始。

## V3.1.0 Phase 0 - Gate 0 Closeout

日期：2026-08-25

Commit：见 Git 历史 `Close Fiona V3.1 Gate 0 product and technical audit`

影响范围：Product Freeze / Technical Audit / Implementation Roadmap / Release Strategy / Documentation Index

### 新增内容

- 冻结 Fiona Global 4H Intelligence 产品边界、原生图片交付语义、`en-US` 输出边界、动态 6:3:1 全球覆盖、六时段节奏与 4H 状态要求。
- 新增 Gate 0 Closeout，记录 Product Review、技术结论、遗留风险和 Gate 1 准入条件。

### 修复内容

- 修正 README 的当前生产图片模式、实际本地仓库路径和 V3.1 状态。
- 修正 Version Matrix 与技术审计中已过期的待确认状态。

### 影响范围

- 仅文档变更。
- Production V1/V3.0.0 代码、Scheduler、Telegram、Railway 与环境变量均未改变。
- Gate 1 未开始。

## V3.0.0 GA - Fiona Design System 1.0

发布日期：2026-08-05

Commit：`a8678b0 Release Fiona Design System 1.0`

影响范围：Market News Renderer / Design Tokens / Component Library / Tests / Product Documentation

### 新增功能

- 新增集中式 immutable design tokens，统一颜色、字号、间距、圆角、边框、阴影、图标、网格、surface、品牌与置信状态。
- 新增可独立渲染和测试的 Intelligence Card 组件库。
- 新增 Design System 1.0 文档、Release Notes、Architecture Snapshot 更新与 ADR 006。

### 修复内容

- 移除 Renderer 中分散的视觉常量和重复字体配置。
- 保留缺失数据、中文换行和长文本语义裁剪的确定性行为。

### 优化内容

- Today's Judgement 固定为视觉中心，Market Regime 与 Evidence 调整为次级信号。
- 技术 Footer 替换为低对比 Fiona Brand Signature。
- Full、Missing、Stress 原型统一使用同一 Design System。

### 删除内容

- 未删除生产代码、数据字段或交付能力。

### 影响范围

- 不影响 Scheduler、Runtime、Telegram Delivery、Railway、环境变量、ledger 或 arbitration。
- V3.0.0 作为 Fiona 第一个完整产品版本进入 Production。

## V3.0.0-RC - Visual Experience

发布日期：2026-08-05

Commit：未创建

影响范围：Market News Renderer / Tests / Product Documentation

### 新增功能

- 建立 Fiona Visual System V3、Information Architecture V3、Telegram Card Spec V3 与 Brand Guideline V3。
- 新增 Full、Missing、Stress 三种本地产品级原型及视觉验收测试。
- 新增 Judgment-First ADR、V3 Architecture Snapshot 与 Release Plan。

### 修复内容

- 修复长中文判断换行时可能出现的行首孤立标点。
- 缺失数据继续保持固定布局，不以零值代替未知值。

### 优化内容

- Fiona's View 成为视觉中心，Heat Map 调整为证据层。
- 优化移动端字号、对比度、间距、数据密度、品牌识别和分享体验。

### 删除内容

- 未删除生产代码、数据字段或交付能力。

### 影响范围

- 不影响 Scheduler、Runtime、Telegram Delivery、Railway、环境变量及五个定时任务。
- 当前仅为本地 Release Candidate，未 Commit、Push 或 Deploy。

## V1.0.1 - Workspace V2 Migration

发布日期：2026-06-26  
Commit：待本次 Workspace Migration 提交后由 Git 历史确认  
影响范围：Local Workspace / Documentation / Development Path

### 新增功能

- 建立 `~/Documents/Wilson AI Lab/` 作为长期本地工作空间。
- 将 Fiona Git 仓库迁移到 `Fiona Intelligence Platform/03_Development/fiona-intelligence-system/`。
- 建立 Workspace 管理规范、项目模板、迁移计划和迁移报告。

### 修复内容

- 修复本地 Fiona helper 默认输出路径，避免继续写入旧 `~/WilsonMarketNewsRuntime`。
- 更新旧 phase 文档中的本地 runtime 路径。

### 优化内容

- 旧 runtime、历史 reports、logs、env、launchd 模板迁入 Wilson AI Lab 分类目录。
- Desktop 不再保留 Fiona 项目目录。

### 删除内容

- 未删除任何生产代码。
- 未删除任何历史资料。

### 影响范围

- Railway 云端生产不受影响。
- Telegram 配置不变。
- 本地开发路径已迁移。

## V1.0.0 - Production Foundation

发布日期：2026-06-26  
Commit：待本次 Documentation Sync 提交后由 Git 历史确认  
影响范围：Documentation / Product Management

### 新增功能

- 建立 Fiona Project Documentation System。
- 新增 Roadmap、PRD、Architecture、Deployment、Decision Log、UI Library、Release Notes 等文档目录。
- 新增 `.docx` 导出目录 `docs/export/`。

### 修复内容

- 无代码修复。本次仅建立文档体系。

### 优化内容

- 明确 Fiona 后续开发必须执行 Documentation Sync。
- 明确 Git 提交前必须同步 README、CHANGELOG、PRD、Architecture、Roadmap、Decision Log。

### 删除内容

- 无。

### 影响范围

- 不影响 Railway Runtime。
- 不影响 Telegram 推送。
- 不影响 Alert Engine。

## 历史基线

### V1.0.0 Production Runtime

发布日期：2026-06-25  
状态：已完成

主要内容：

- Railway 部署完成。
- Telegram 发送链路统一。
- Fiona 定时任务稳定运行。
- Alert Engine 代码保留，默认关闭。
- 配置兼容完成：`WILSON_SEND`、`TELEGRAM_GROUP_ID`、`WILSON_INTERVAL_MINUTES`。
