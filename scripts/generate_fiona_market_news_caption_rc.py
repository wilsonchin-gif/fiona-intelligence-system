from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.fiona_briefing import sanitize_output
from app.fiona_market_news_image import (
    CAPTION_MAX_CHARS,
    HeatMapView,
    MarketNewsViewModel,
    build_market_news_view_model,
    compact_text,
    compose_market_news_caption,
    count_cjk_characters,
    ensure_sentence,
    summarize_market_state,
)
from app.fiona_narrative import NarrativeEngine
from scripts.generate_fiona_market_news_prototypes import (
    NOW,
    full_snapshot,
    long_text_snapshot,
    missing_snapshot,
    prototype_events,
)


OUTPUT_DIR = ROOT / "reports" / "prototypes" / "fiona_market_news_caption_rc"


def build_model(snapshot=None) -> MarketNewsViewModel:
    events = prototype_events()
    narratives = NarrativeEngine().build(events, now=NOW)
    return build_market_news_view_model(
        snapshot or full_snapshot(),
        events,
        narratives,
        generated_at=NOW,
    )


def with_regime(model: MarketNewsViewModel, kind: str) -> MarketNewsViewModel:
    settings = {
        "risk_on": {
            "cards": ((72, "Bullish"), (68, "Bullish"), (64, "Bullish"), (66, "Bullish")),
            "view": (
                "跨市场风险偏好正在改善，权益、加密与RWA的方向一致性高于上一轮。"
                "当前信号的关键仍是资金流能否延续，而不是单一资产的短线涨幅。"
            ),
        },
        "risk_off": {
            "cards": ((30, "Bearish"), (34, "Bearish"), (36, "Bearish"), (32, "Bearish")),
            "view": (
                "风险资产同步承压，价格与流动性信号暂未出现稳定修复。"
                "当前判断需要继续由美元、美债与ETF资金方向验证，避免把局部反弹误读为状态切换。"
            ),
        },
        "transition": {
            "cards": ((72, "Bullish"), (48, "Neutral"), (35, "Bearish"), (64, "Bullish")),
            "view": (
                "市场信号明显分化，风险偏好尚未形成一致方向。"
                "权益、加密与RWA之间的资金确认是判断状态能否完成切换的核心变量。"
            ),
        },
    }
    setting = settings[kind]
    heat_map = tuple(
        HeatMapView(
            key=original.key,
            label=original.label,
            score=score,
            direction=direction,
            key_metric=original.key_metric,
        )
        for original, (score, direction) in zip(model.heat_map, setting["cards"])
    )
    return replace(model, heat_map=heat_map, fiona_view=setting["view"])


def old_caption(model: MarketNewsViewModel) -> str:
    state = summarize_market_state(model.heat_map)
    changed = model.what_changed[0].event if model.what_changed else "暂无新增高价值变化"
    view = ensure_sentence(compact_text(model.fiona_view, 118))
    hashtags = " ".join(model.telegram_hashtags)
    return sanitize_output(
        (
            "Fiona Market News\n\n"
            f"过去4小时市场概览：{state}\n\n"
            f"关键变化：{compact_text(changed, 72)}。\n\n"
            f"【Fiona’s View】{view}\n\n"
            f"{hashtags}"
        ).strip()
    )


def scenario_models() -> dict[str, MarketNewsViewModel]:
    full = build_model(full_snapshot())
    missing = build_model(missing_snapshot())
    return {
        "caption_full.md": full,
        "caption_missing.md": missing,
        "caption_long.md": build_model(long_text_snapshot()),
        "caption_risk_on.md": with_regime(full, "risk_on"),
        "caption_risk_off.md": with_regime(full, "risk_off"),
        "caption_transition.md": with_regime(full, "transition"),
        "caption_unknown.md": missing,
        "caption_no_narrative.md": replace(full, current_narrative=()),
    }


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    models = scenario_models()
    for filename, model in models.items():
        caption = compose_market_news_caption(model)
        if len(caption) > CAPTION_MAX_CHARS:
            raise RuntimeError(f"{filename} exceeds the caption safety limit")
        content = (
            f"# {filename.removesuffix('.md')}\n\n"
            f"{caption}\n\n"
            "---\n"
            f"Total characters: {len(caption)}  \n"
            f"CJK characters: {count_cjk_characters(caption)}\n"
        )
        (OUTPUT_DIR / filename).write_text(content, encoding="utf-8")

    before = old_caption(models["caption_full.md"])
    after = compose_market_news_caption(models["caption_full.md"])
    comparison = f"""# Fiona Market News Caption RC Comparison

## Before

{before}

## After

{after}

## Removed Repetition

- Removed the four-market score recap and complete Key Markets value dump.
- Kept only one or two material changes; detailed evidence remains in the image.
- Moved event watch clauses into one deduplicated Watch Next section.
- Limited Telegram hashtags to eight and removed synonymous aliases.

## Product Improvement

- Market Regime and deterministic Evidence are visible immediately.
- Fiona's View is the decision layer instead of an attachment to market data.
- Watch Next now contains concrete, verifiable variables.
- Unknown or Limited evidence produces explicitly cautious language.
- Complete-sentence compression preserves structure below the Telegram safety limit.
"""
    (OUTPUT_DIR / "caption_comparison.md").write_text(comparison.strip() + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
