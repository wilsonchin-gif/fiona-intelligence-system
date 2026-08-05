# Fiona Design Language

- Version: V3.0.0 / Design System 1.0
- Status: Production
- Owner: Wilson / Fiona Design Engineering
- Updated: 2026-08-05

## Brand Voice

Fiona 的视觉语言应表现为冷静、克制、可验证、判断明确。它像一位 Market Intelligence Officer，不像新闻媒体、交易终端截图或营销海报。

## Visual Tone

- 深色高对比信息底板，避免装饰性渐变和无意义图形。
- 状态颜色只表达语义：正向、负向、中性、未知、置信等级。
- 主判断使用最高对比度；辅助证据逐级降低视觉权重。
- Unknown 和 Limited 必须诚实可见，不用虚构数字填补。

## Layout Rules

1. Today's Judgement 必须位于第一阅读层。
2. Market Regime 和 Evidence 作为次级徽标，不能压过判断。
3. 数据模块按证据价值排序，而不是按数据量排序。
4. 同一信息只出现一次。
5. 每个区域具有稳定边界，内容变化不得推动整体结构漂移。

## Whitespace Rules

- 外边距、区块间距、卡片内边距全部使用 tokens。
- Hero 周围保留最大呼吸空间。
- 不以减少间距解决内容过载；优先裁剪低价值文本。
- Footer 保持低对比，不与正文竞争。

## Card Rhythm

- Header：身份与时间。
- Hero：判断、驱动、下一确认。
- Evidence：状态和可信度。
- Detail：变化、市场、叙事和语境。
- Signature：低调收束。

## Typography Philosophy

- 标题用于判断，不用于装饰。
- 数字采用稳定、易扫描的字号层级。
- 中英文共享语义尺度并使用 bundled Noto Sans CJK。
- 长文本只换行或截断，不动态缩小到不可读。

## Brand Signature Usage

固定使用：

```text
FIONA INTELLIGENCE
AI MARKET INTELLIGENCE
```

禁止添加网站、二维码、营销口号或高对比推广信息。

## Sharing Rules

- 图片脱离 Telegram Caption 后仍能独立说明时间、判断和品牌。
- Caption 只总结核心变化，不重复整张图。
- 分享截图中必须保留判断、证据等级和品牌签名。
