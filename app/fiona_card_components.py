from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Iterable, Protocol

from PIL import ImageDraw, ImageFont

from app.design_tokens import FIONA_TOKENS, FionaDesignTokens, Region
from app.fiona_locale import FionaLocaleStrings, OutputLocale, ZH_CN_STRINGS, format_display_timestamp
from app.fiona_market_news_image import (
    ChangedEventView,
    HeatMapView,
    KeyMarketView,
    NarrativeView,
)


ROOT = Path(__file__).resolve().parent.parent


def font_asset_paths(
    root: str | Path,
    tokens: FionaDesignTokens = FIONA_TOKENS,
) -> tuple[Path, Path]:
    font_dir = Path(root) / "assets" / "fonts"
    return (
        font_dir / tokens.typography.family_regular,
        font_dir / tokens.typography.family_bold,
    )


FONT_REGULAR, FONT_BOLD = font_asset_paths(ROOT)
FONT_DIR = FONT_REGULAR.parent


@dataclass(frozen=True)
class ComponentRenderResult:
    name: str
    region: tuple[int, int, int, int]
    rendered_items: int


@dataclass(frozen=True)
class RenderContext:
    draw: ImageDraw.ImageDraw
    tokens: FionaDesignTokens = FIONA_TOKENS
    strings: FionaLocaleStrings = ZH_CN_STRINGS
    locale: OutputLocale = OutputLocale.ZH_CN


class CardComponent(Protocol):
    name: str
    region_name: str

    def render(self, context: RenderContext) -> ComponentRenderResult: ...


@dataclass(frozen=True)
class HeaderInput:
    generated_at: object


@dataclass(frozen=True)
class MarketRegimeInput:
    label: str
    reason: str
    tone: str


@dataclass(frozen=True)
class EvidenceInput:
    label: str
    source_count: int
    completeness: int
    tone: str


@dataclass(frozen=True)
class HeroJudgmentInput:
    judgment: str
    primary_driver: str
    next_confirmation: str


@dataclass(frozen=True)
class HistoricalContextInput:
    topic: str
    reference: str


@dataclass(frozen=True)
class HeaderComponent:
    value: HeaderInput
    name: str = "Header"
    region_name: str = "header"

    def render(self, context: RenderContext) -> ComponentRenderResult:
        draw, tokens = context.draw, context.tokens
        colors, type_, space = tokens.colors, tokens.typography, tokens.spacing
        region = tokens.regions[self.region_name]
        left = space.outer_margin
        right = tokens.canvas.width - space.outer_margin

        draw.rectangle(
            (region.left, region.top, region.right, region.top + space.xs - space.xxs // 2),
            fill=colors.brand,
        )
        brand_y = max(region.top + space.lg, tokens.canvas.safe_top)
        draw.text((left, brand_y), context.strings.brand_wordmark, font=font(type_.brand_wordmark, bold=True), fill=colors.brand)
        brand_width = text_width(draw, context.strings.brand_wordmark, font(type_.brand_wordmark, bold=True))
        draw.text(
            (left + brand_width + space.lg, brand_y + space.xxs // 2),
            context.strings.brand_descriptor,
            font=font(type_.brand_descriptor, bold=True),
            fill=colors.muted_text,
        )

        title_y = region.top + space.xxl + space.xs
        draw.text(
            (left, title_y),
            context.strings.product_title,
            font=font(type_.product_title, bold=True),
            fill=colors.primary_text,
        )

        cadence = context.strings.interim_badge
        cadence_font = font(type_.brand_descriptor, bold=True)
        cadence_width = text_width(draw, cadence, cadence_font) + space.xl
        cadence_top = region.top + space.lg
        cadence_bottom = cadence_top + font_line_height(cadence_font) + space.sm
        rounded_box(
            context,
            (right - cadence_width, cadence_top, right, cadence_bottom),
            fill=colors.surface,
            outline=colors.border,
            radius=tokens.radius.badge,
        )
        draw.text(
            (right - cadence_width / 2, cadence_top + space.xs - space.xxs // 2),
            cadence,
            font=cadence_font,
            fill=colors.secondary_text,
            anchor="ma",
        )
        timestamp = format_display_timestamp(self.value.generated_at, context.locale)
        draw.text(
            (right, region.bottom - space.xl - space.xs),
            timestamp,
            font=font(type_.timestamp, bold=True),
            fill=colors.secondary_text,
            anchor="ra",
        )
        draw.line(
            (left, region.bottom - space.xs, right, region.bottom - space.xs),
            fill=colors.border,
            width=tokens.border.divider_width,
        )
        return component_result(self, tokens, 1)


@dataclass(frozen=True)
class MarketRegimeComponent:
    value: MarketRegimeInput
    name: str = "Market Regime"
    region_name: str = "market_regime"

    def render(self, context: RenderContext) -> ComponentRenderResult:
        draw, tokens = context.draw, context.tokens
        colors, type_, space = tokens.colors, tokens.typography, tokens.spacing
        region = tokens.regions[self.region_name]
        left = space.outer_margin
        draw.text(
            (left, region.top + space.sm),
            context.strings.market_regime,
            font=font(type_.regime_label, bold=True),
            fill=colors.muted_text,
        )
        draw.text(
            (left, region.top + space.xl),
            self.value.label.upper(),
            font=font(type_.regime_value, bold=True),
            fill=tone_color(tokens, self.value.tone),
        )
        draw_text_fit(
            context,
            (grid_x(tokens, 3), region.top + space.lg + space.xxs, grid_x(tokens, 8), region.bottom - space.xs),
            semantic_limit(self.value.reason, 42 if tokens.canvas.width > 1080 else 26),
            font(type_.market_metric, bold=True),
            colors.secondary_text,
            max_lines=1,
        )
        return component_result(self, tokens, 1)


@dataclass(frozen=True)
class EvidenceComponent:
    value: EvidenceInput
    name: str = "Evidence"
    region_name: str = "market_regime"

    def render(self, context: RenderContext) -> ComponentRenderResult:
        draw, tokens = context.draw, context.tokens
        colors, type_, space = tokens.colors, tokens.typography, tokens.spacing
        region = tokens.regions[self.region_name]
        right = tokens.canvas.width - space.outer_margin
        selected_font = font(type_.badge, bold=True)
        badge_width = text_width(draw, self.value.label.upper(), selected_font) + space.lg
        badge_left = right - badge_width
        badge_top = region.top + space.sm + space.xxs
        badge_bottom = badge_top + font_line_height(selected_font) + space.xs
        tone = tone_color(tokens, self.value.tone)
        draw.text(
            (badge_left - space.xxl - space.xl, region.top + space.md + space.xxs),
            context.strings.evidence,
            font=font(type_.regime_label, bold=True),
            fill=colors.muted_text,
        )
        rounded_box(
            context,
            (badge_left, badge_top, right, badge_bottom),
            fill=mix(colors.background, tone, 0.15),
            outline=tone,
            radius=tokens.radius.badge,
        )
        draw.text(
            (badge_left + space.sm, badge_top + space.xxs + 1),
            self.value.label.upper(),
            font=selected_font,
            fill=tone,
        )
        metadata = f"{self.value.source_count} {context.strings.sources} · {self.value.completeness}%"
        draw.text(
            (right, region.bottom - space.md),
            metadata,
            font=font(type_.badge_meta, bold=True),
            fill=colors.muted_text,
            anchor="ra",
        )
        return component_result(self, tokens, 1)


@dataclass(frozen=True)
class HeroJudgmentComponent:
    value: HeroJudgmentInput
    name: str = "Hero Judgment"
    region_name: str = "fiona_view"

    def render(self, context: RenderContext) -> ComponentRenderResult:
        draw, tokens = context.draw, context.tokens
        colors, type_, space = tokens.colors, tokens.typography, tokens.spacing
        region = tokens.regions[self.region_name]
        left, right = space.outer_margin, tokens.canvas.width - space.outer_margin
        top, bottom = region.top + space.xs, region.bottom - space.sm
        rounded_box(
            context,
            (left, top, right, bottom),
            fill=colors.elevated,
            outline=tokens.border.hero_outline,
            radius=tokens.radius.card,
        )
        draw.rectangle((left, top, left + space.xs, bottom), fill=colors.brand)
        content_left = left + space.lg
        draw.text(
            (content_left, top + space.sm),
            context.strings.fiona_view,
            font=font(type_.hero_label, bold=True),
            fill=colors.brand,
        )
        draw.text(
            (right - space.lg, top + space.sm + 1),
            context.strings.today_judgment,
            font=font(type_.brand_descriptor, bold=True),
            fill=colors.muted_text,
            anchor="ra",
        )
        draw_text_fit(
            context,
            (content_left, top + space.xxl, right - space.lg, bottom - space.xxl),
            semantic_limit(self.value.judgment, 110 if tokens.canvas.width > 1080 else 68),
            font(type_.hero_body, bold=True),
            colors.primary_text,
            max_lines=2,
            line_gap=1,
        )
        midpoint = left + (right - left) // 2
        meta_top = bottom - space.xl - space.xxs
        draw_text_fit(
            context,
            (content_left, meta_top, midpoint - space.md, bottom - space.xs),
            f"{context.strings.driver}  {semantic_limit(self.value.primary_driver, 42 if tokens.canvas.width > 1080 else 27)}",
            font(type_.hero_meta, bold=True),
            colors.secondary_text,
            max_lines=1,
        )
        draw_text_fit(
            context,
            (midpoint + space.md, meta_top, right - space.lg, bottom - space.xs),
            f"{context.strings.next_confirmation}  {semantic_limit(self.value.next_confirmation, 42 if tokens.canvas.width > 1080 else 27)}",
            font(type_.hero_meta, bold=True),
            colors.brand,
            max_lines=1,
        )
        return component_result(self, tokens, 1)


@dataclass(frozen=True)
class HeatMapComponent:
    values: tuple[HeatMapView, ...]
    name: str = "Heat Map"
    region_name: str = "heat_map"

    def render(self, context: RenderContext) -> ComponentRenderResult:
        tokens, space = context.tokens, context.tokens.spacing
        region = tokens.regions[self.region_name]
        draw_section_title(context, region.top + space.xs, context.strings.heat_map, context.strings.heat_map_meta)
        cards = list(self.values)[:4]
        while len(cards) < 4:
            cards.append(
                HeatMapView(
                    "",
                    context.strings.data_unavailable,
                    None,
                    context.strings.awaiting,
                    context.strings.data_unavailable,
                )
            )
        top = region.top + space.xl + space.xs
        bottom = region.bottom - space.sm
        row_gap = space.xs
        tile_height = (bottom - top - row_gap) // 2
        content_width = tokens.canvas.width - space.outer_margin * 2
        tile_width = (content_width - tokens.grid.gutter) // tokens.grid.market_columns
        positions = (
            (space.outer_margin, top),
            (space.outer_margin + tile_width + tokens.grid.gutter, top),
            (space.outer_margin, top + tile_height + row_gap),
            (space.outer_margin + tile_width + tokens.grid.gutter, top + tile_height + row_gap),
        )
        for card, (x, y) in zip(cards, positions):
            draw_heat_tile(context, card, x, y, tile_width, tile_height)
        return component_result(self, tokens, len(cards))


@dataclass(frozen=True)
class WhatChangedComponent:
    values: tuple[ChangedEventView, ...]
    verification: str
    verification_tone: str
    name: str = "What Changed"
    region_name: str = "what_changed"

    def render(self, context: RenderContext) -> ComponentRenderResult:
        draw, tokens = context.draw, context.tokens
        colors, type_, space = tokens.colors, tokens.typography, tokens.spacing
        region = tokens.regions[self.region_name]
        draw_section_title(
            context,
            region.top + space.xs,
            context.strings.what_changed,
            context.strings.what_changed_meta,
        )
        observations = list(self.values)[:2]
        if not observations:
            observations = [
                ChangedEventView(
                    event=context.strings.no_material_change,
                    why=context.strings.no_material_change_why,
                    watch=context.strings.waiting_confirmation,
                )
            ]
        cards_top = region.top + space.xl + space.xs
        cards_bottom = region.bottom - space.xs
        gap = space.xs
        row_height = (cards_bottom - cards_top - gap * (len(observations) - 1)) // len(observations)
        y = cards_top
        left, right = space.outer_margin, tokens.canvas.width - space.outer_margin
        for index, item in enumerate(observations, start=1):
            rounded_box(context, (left, y, right, y + row_height), fill=colors.surface, outline=colors.border)
            draw.text((left + space.md, y + space.sm), f"0{index}", font=font(type_.change_index, bold=True), fill=colors.brand)
            draw.text(
                (right - space.lg, y + space.sm),
                self.verification,
                font=font(type_.brand_descriptor, bold=True),
                fill=tone_color(tokens, self.verification_tone),
                anchor="ra",
            )
            headline_left = left + space.xxl + space.md
            draw_text_fit(
                context,
                (headline_left, y + space.xs, right - space.xxl * 4, y + space.xl + space.sm),
                semantic_limit(item.event, 52 if tokens.canvas.width > 1080 else 36),
                font(type_.change_headline, bold=True),
                colors.primary_text,
                max_lines=1,
            )
            midpoint = left + (right - left) // 2
            detail_top = y + row_height - space.xl - space.sm
            draw_text_fit(
                context,
                (headline_left, detail_top, midpoint + space.lg, y + row_height - space.xs),
                f"WHY  {semantic_limit(item.why, 50 if tokens.canvas.width > 1080 else 34)}",
                font(type_.body),
                colors.secondary_text,
                max_lines=1,
            )
            draw_text_fit(
                context,
                (midpoint + space.xxl, detail_top, right - space.lg, y + row_height - space.xs),
                f"WATCH  {semantic_limit(item.watch, 45 if tokens.canvas.width > 1080 else 30)}",
                font(type_.body, bold=True),
                colors.positive,
                max_lines=1,
            )
            y += row_height + gap
        return component_result(self, tokens, len(observations))


@dataclass(frozen=True)
class KeyMarketsComponent:
    values: tuple[KeyMarketView, ...]
    name: str = "Key Markets"
    region_name: str = "key_markets"

    def render(self, context: RenderContext) -> ComponentRenderResult:
        draw, tokens = context.draw, context.tokens
        colors, type_, space = tokens.colors, tokens.typography, tokens.spacing
        region = tokens.regions[self.region_name]
        draw_section_title(
            context,
            region.top + space.xs,
            context.strings.key_markets,
            context.strings.key_markets_meta,
        )
        markets = list(self.values)[: tokens.grid.key_market_columns]
        while len(markets) < tokens.grid.key_market_columns:
            markets.append(
                KeyMarketView(
                    "",
                    context.strings.awaiting,
                    "—",
                    context.strings.data_unavailable,
                )
            )
        left, right = space.outer_margin, tokens.canvas.width - space.outer_margin
        width = (right - left - tokens.grid.gutter * (tokens.grid.key_market_columns - 1)) // tokens.grid.key_market_columns
        top, bottom = region.top + space.xl + space.xs, region.bottom - space.sm
        for index, item in enumerate(markets):
            x = left + index * (width + tokens.grid.gutter)
            rounded_box(context, (x, top, x + width, bottom), fill=colors.surface, outline=colors.border)
            draw_text_fit(
                context,
                (x + space.sm, top + space.sm, x + width - space.sm, top + space.xl),
                item.label,
                font(type_.key_label, bold=True),
                colors.secondary_text,
                max_lines=1,
            )
            draw_text_fit(
                context,
                (x + space.sm, top + space.xxl, x + width - space.sm, bottom - space.xl),
                item.value,
                font(type_.key_value, bold=True),
                colors.primary_text,
                max_lines=1,
            )
            draw.text(
                (x + space.sm, bottom - space.lg),
                item.change,
                font=font(type_.key_label, bold=True),
                fill=change_color(tokens, item.change),
            )
        return component_result(self, tokens, len(markets))


@dataclass(frozen=True)
class NarrativeComponent:
    values: tuple[NarrativeView, ...]
    name: str = "Narrative"
    region_name: str = "narrative"

    def render(self, context: RenderContext) -> ComponentRenderResult:
        tokens, space = context.tokens, context.tokens.spacing
        colors, type_ = tokens.colors, tokens.typography
        region = tokens.regions[self.region_name]
        draw_section_title(
            context,
            region.top + space.xs,
            context.strings.narrative_context,
            context.strings.narrative_meta,
        )
        items = list(self.values)[:2]
        text = (
            context.strings.no_high_confidence_narrative
            if not items
            else "  |  ".join(
                format_narrative(
                    item,
                    context.strings,
                    max_name_chars=24 if tokens.canvas.width > 1080 else 16,
                )
                for item in items
            )
        )
        top = region.top + space.xl + space.xxs
        bottom = region.bottom - space.sm
        rounded_box(
            context,
            (space.outer_margin, top, tokens.canvas.width - space.outer_margin, bottom),
            fill=colors.surface,
            outline=colors.border,
            radius=tokens.radius.badge,
        )
        draw_text_fit(
            context,
            (space.outer_margin + space.md, top + space.xs, tokens.canvas.width - space.outer_margin - space.md, bottom - space.xxs),
            text,
            font(type_.narrative, bold=True),
            colors.secondary_text,
            max_lines=1,
        )
        return component_result(self, tokens, len(items))


@dataclass(frozen=True)
class WatchNextComponent:
    values: tuple[str, ...]
    name: str = "Watch Next"
    region_name: str = "watch_next"

    def render(self, context: RenderContext) -> ComponentRenderResult:
        draw, tokens = context.draw, context.tokens
        colors, type_, space = tokens.colors, tokens.typography, tokens.spacing
        region = tokens.regions[self.region_name]
        draw_section_title(
            context,
            region.top + space.xs,
            context.strings.watch_next,
            context.strings.watch_next_meta,
        )
        items = list(self.values)[: tokens.grid.watch_columns]
        while len(items) < tokens.grid.watch_columns:
            items.append(context.strings.waiting_confirmation)
        left, right = space.outer_margin, tokens.canvas.width - space.outer_margin
        width = (right - left - tokens.grid.gutter * (tokens.grid.watch_columns - 1)) // tokens.grid.watch_columns
        top, bottom = region.top + space.xl + space.xxs, region.bottom - space.sm
        for index, item in enumerate(items):
            x = left + index * (width + tokens.grid.gutter)
            rounded_box(context, (x, top, x + width, bottom), fill=colors.surface, outline=colors.border)
            draw.text((x + space.sm, top + space.xs), f"0{index + 1}", font=font(type_.brand_descriptor, bold=True), fill=colors.brand)
            draw_text_fit(
                context,
                (x + space.xxl, top + space.xs - 2, x + width - space.sm, bottom - space.xs),
                item,
                font(type_.body, bold=True),
                colors.primary_text,
                max_lines=1,
            )
        return component_result(self, tokens, len(items))


@dataclass(frozen=True)
class HistoricalContextComponent:
    value: HistoricalContextInput
    name: str = "Historical Context"
    region_name: str = "historical_context"

    def render(self, context: RenderContext) -> ComponentRenderResult:
        draw, tokens = context.draw, context.tokens
        colors, type_, space = tokens.colors, tokens.typography, tokens.spacing
        region = tokens.regions[self.region_name]
        draw_section_title(
            context,
            region.top + space.xs,
            context.strings.historical_context,
            context.strings.historical_context_meta,
        )
        top, bottom = region.top + space.xl + space.xxs, region.bottom - space.xs
        left, right = space.outer_margin, tokens.canvas.width - space.outer_margin
        rounded_box(
            context,
            (left, top, right, bottom),
            fill=mix(colors.surface, colors.brand, 0.05),
            outline=colors.border,
            radius=tokens.radius.badge,
        )
        draw.text((left + space.sm, top + 2), self.value.topic.upper(), font=font(type_.footer, bold=True), fill=colors.brand)
        draw_text_fit(
            context,
            (left + space.xxl * 3 + space.sm, top + 1, right - space.xxl * 4, bottom - 1),
            semantic_limit(self.value.reference, 40),
            font(type_.brand_descriptor, bold=True),
            colors.secondary_text,
            max_lines=1,
        )
        draw.text(
            (right - space.sm, top + 2),
            context.strings.historical_caveat,
            font=font(type_.badge_meta, bold=True),
            fill=colors.muted_text,
            anchor="ra",
        )
        return component_result(self, tokens, 1)


@dataclass(frozen=True)
class BrandSignatureComponent:
    hashtags: tuple[str, ...]
    name: str = "Brand Signature"
    region_name: str = "tags"

    def render(self, context: RenderContext) -> ComponentRenderResult:
        draw, tokens = context.draw, context.tokens
        colors, type_, space = tokens.colors, tokens.typography, tokens.spacing
        region = tokens.regions[self.region_name]
        x = space.outer_margin
        rendered = 0
        for tag in list(dict.fromkeys(self.hashtags))[:3]:
            label = semantic_limit(str(tag), 16)
            selected_font = font(type_.tag, bold=True)
            width = text_width(draw, label, selected_font) + space.lg
            if x + width > tokens.canvas.width - space.outer_margin:
                break
            rounded_box(
                context,
                (x, region.top + space.xxs, x + width, region.bottom - space.xs),
                fill=mix(colors.surface, colors.brand, 0.08),
                outline=colors.border,
                radius=tokens.radius.tag,
            )
            draw.text((x + space.sm, region.top + space.xs - 1), label, font=selected_font, fill=colors.secondary_text)
            x += width + space.sm
            rendered += 1
        draw.text(
            (tokens.canvas.width - space.outer_margin, region.top + space.xs),
            tokens.footer.signature,
            font=font(type_.badge_meta, bold=True),
            fill=colors.muted_text,
            anchor="ra",
        )
        return component_result(self, tokens, rendered)


@dataclass(frozen=True)
class FooterComponent:
    name: str = "Footer"
    region_name: str = "footer"

    def render(self, context: RenderContext) -> ComponentRenderResult:
        draw, tokens = context.draw, context.tokens
        colors, type_, space = tokens.colors, tokens.typography, tokens.spacing
        region = tokens.regions[self.region_name]
        left, right = space.outer_margin, tokens.canvas.width - space.outer_margin
        if tokens.footer.divider:
            draw.line((left, region.top + 3, right, region.top + 3), fill=colors.border, width=tokens.border.divider_width)
        draw_text_fit(
            context,
            (left, region.top + space.md, right - space.xxl * 5, region.bottom - space.lg),
            context.strings.informational_disclaimer,
            font(type_.footer),
            colors.muted_text,
            max_lines=1,
        )
        if tokens.canvas.width > 1080:
            draw.text(
                (right, region.top + space.md),
                tokens.footer.descriptor,
                font=font(type_.footer_brand, bold=True),
                fill=colors.secondary_text,
                anchor="ra",
            )
        else:
            draw.text(
                (right, region.top + space.md),
                tokens.footer.signature,
                font=font(type_.footer_brand, bold=True),
                fill=colors.secondary_text,
                anchor="ra",
            )
            draw.text(
                (right, region.bottom - space.lg),
                tokens.footer.descriptor,
                font=font(type_.footer_meta, bold=True),
                fill=colors.muted_text,
                anchor="ra",
            )
        return component_result(self, tokens, 1)


def draw_heat_tile(
    context: RenderContext,
    card: HeatMapView,
    x: int,
    y: int,
    width: int,
    height: int,
) -> None:
    draw, tokens = context.draw, context.tokens
    colors, type_, space = tokens.colors, tokens.typography, tokens.spacing
    direction = card.direction if card.score is not None else context.strings.awaiting
    semantic_color = direction_color(tokens, direction)
    intensity = 0.08 if card.score is None else 0.08 + min(0.08, abs(card.score - 50) / 625)
    rounded_box(
        context,
        (x, y, x + width, y + height),
        fill=mix(colors.surface, semantic_color, intensity),
        outline=colors.border,
    )
    accent = market_accent(tokens, card.key)
    draw.rounded_rectangle(
        (x, y, x + space.xs - space.xxs + 1, y + height),
        radius=tokens.radius.accent,
        fill=accent,
    )
    draw.text((x + space.lg - space.xxs, y + space.sm - 2), card.label, font=font(type_.market_label, bold=True), fill=colors.primary_text)
    score = str(card.score) if card.score is not None else "—"
    draw.text((x + space.lg - space.xxs, y + space.xl - 1), score, font=font(type_.market_score, bold=True), fill=colors.primary_text)
    if card.score is not None:
        draw.text((x + space.xxl + space.lg - 2, y + space.xxl - space.xxs), "/100", font=font(type_.metric_suffix), fill=colors.secondary_text)
    draw.text((x + width - space.md, y + space.sm - 1), direction, font=font(type_.market_label, bold=True), fill=semantic_color, anchor="ra")
    metric = context.strings.data_unavailable if card.score is None else semantic_limit(card.key_metric, 16)
    draw_text_fit(
        context,
        (x + space.xxl * 2 + space.lg, y + space.xl + space.xs - 1, x + width - space.md, y + height - space.xs),
        metric,
        font(type_.market_metric),
        colors.secondary_text,
        max_lines=1,
    )


def draw_section_title(context: RenderContext, y: int, title: str, meta: str) -> None:
    draw, tokens = context.draw, context.tokens
    colors, type_, space = tokens.colors, tokens.typography, tokens.spacing
    draw.text((space.outer_margin, y), title, font=font(type_.section_title, bold=True), fill=colors.primary_text)
    draw.text(
        (tokens.canvas.width - space.outer_margin, y + 3),
        meta,
        font=font(type_.section_meta, bold=True),
        fill=colors.muted_text,
        anchor="ra",
    )


def component_result(
    component: CardComponent,
    tokens: FionaDesignTokens,
    rendered_items: int,
) -> ComponentRenderResult:
    return ComponentRenderResult(
        name=component.name,
        region=tokens.regions[component.region_name].as_tuple(),
        rendered_items=rendered_items,
    )


def draw_text_fit(
    context: RenderContext,
    box: tuple[int, int, int, int],
    text: str,
    selected_font: ImageFont.FreeTypeFont,
    fill: str,
    *,
    max_lines: int,
    line_gap: int = 5,
) -> list[str]:
    draw = context.draw
    left, top, right, bottom = box
    lines = wrap_text_pixels(draw, str(text), selected_font, right - left, max_lines)
    line_height = font_line_height(selected_font) + line_gap
    max_height_lines = max(1, (bottom - top + line_gap) // line_height)
    lines = lines[:max_height_lines]
    for index, line in enumerate(lines):
        draw.text((left, top + index * line_height), line, font=selected_font, fill=fill)
    return lines


def wrap_text_pixels(
    draw: ImageDraw.ImageDraw,
    text: str,
    selected_font: ImageFont.FreeTypeFont,
    max_width: int,
    max_lines: int,
) -> list[str]:
    clean = re.sub(r"\s+", " ", str(text)).strip()
    if not clean:
        return [""]
    tokens = tokenize(clean)
    lines: list[str] = []
    current = ""
    consumed = 0
    for token in tokens:
        candidate = current + token
        if current and text_width(draw, candidate.rstrip(), selected_font) > max_width:
            lines.append(current.rstrip())
            current = token.lstrip()
            if len(lines) == max_lines:
                break
        else:
            current = candidate
        consumed += 1
    if len(lines) < max_lines and current:
        lines.append(current.rstrip())
    if consumed < len(tokens) and lines:
        lines[-1] = ellipsize(draw, lines[-1], selected_font, max_width)
    return avoid_orphan_punctuation(draw, lines[:max_lines], selected_font, max_width)


def avoid_orphan_punctuation(
    draw: ImageDraw.ImageDraw,
    lines: list[str],
    selected_font: ImageFont.FreeTypeFont,
    max_width: int,
) -> list[str]:
    closing_marks = "，。！？；：、,.!?;:)]}）】》」』"
    output = list(lines)
    for index in range(1, len(output)):
        while output[index] and output[index][0] in closing_marks:
            mark = output[index][0]
            remainder = output[index][1:].lstrip()
            if text_width(draw, output[index - 1] + mark, selected_font) <= max_width:
                output[index - 1] += mark
                output[index] = remainder
                continue
            previous = output[index - 1].rstrip()
            if not previous:
                output[index] = remainder
                continue
            moved = previous[-1]
            output[index - 1] = previous[:-1].rstrip()
            output[index] = ellipsize(draw, moved + mark + remainder, selected_font, max_width)
    return output


def tokenize(text: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9][A-Za-z0-9._/%+\-]*|\s+|.", text, flags=re.DOTALL)


def ellipsize(
    draw: ImageDraw.ImageDraw,
    text: str,
    selected_font: ImageFont.FreeTypeFont,
    max_width: int,
) -> str:
    value = text.rstrip("… ")
    while value and text_width(draw, value + "…", selected_font) > max_width:
        tokens = tokenize(value)
        if not tokens:
            break
        tokens.pop()
        value = "".join(tokens).rstrip()
    return (value + "…") if value else "…"


def semantic_limit(text: str, max_chars: int) -> str:
    clean = re.sub(r"\s+", " ", str(text)).strip()
    if len(clean) <= max_chars:
        return clean
    prefix = clean[:max_chars]
    boundary = max(prefix.rfind(mark) for mark in ("。", "！", "？", "；", "，", "、", ".", ";", ","))
    if boundary >= max_chars // 2:
        result = prefix[: boundary + 1].rstrip()
        if result[-1] in {"，", "；", "、", ",", ";"}:
            sentence_end = "。" if re.search(r"[\u3400-\u9fff]", clean) else "."
            result = result[:-1].rstrip() + sentence_end
        return result
    while prefix and prefix[-1].isascii() and prefix[-1].isalnum():
        prefix = prefix[:-1]
    return prefix.rstrip("，；、 ") + "…"


def validate_font_assets() -> None:
    missing = [str(path) for path in (FONT_REGULAR, FONT_BOLD) if not path.exists()]
    if missing:
        raise RuntimeError(f"Missing fixed Fiona font assets: {', '.join(missing)}")


@lru_cache(maxsize=64)
def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    path = FONT_BOLD if bold else FONT_REGULAR
    if not path.exists():
        raise RuntimeError(f"Missing fixed Fiona font asset: {path}")
    return ImageFont.truetype(str(path), size=size)


def font_line_height(selected_font: ImageFont.FreeTypeFont) -> int:
    ascent, descent = selected_font.getmetrics()
    return ascent + descent


def text_width(
    draw: ImageDraw.ImageDraw,
    text: str,
    selected_font: ImageFont.FreeTypeFont,
) -> int:
    left, _, right, _ = draw.textbbox((0, 0), text, font=selected_font)
    return right - left


def rounded_box(
    context: RenderContext,
    box: tuple[int, int, int, int],
    *,
    fill: str,
    outline: str,
    radius: int | None = None,
) -> None:
    context.draw.rounded_rectangle(
        box,
        radius=context.tokens.radius.card if radius is None else radius,
        fill=fill,
        outline=outline,
        width=context.tokens.border.width,
    )


def direction_color(tokens: FionaDesignTokens, direction: str) -> str:
    normalized = str(direction).lower()
    if normalized == "bullish":
        return tokens.colors.positive
    if normalized == "bearish":
        return tokens.colors.negative
    if normalized == "neutral":
        return tokens.colors.neutral
    return tokens.colors.unknown


def change_color(tokens: FionaDesignTokens, change: str) -> str:
    if str(change).startswith("+"):
        return tokens.colors.positive
    if str(change).startswith("-"):
        return tokens.colors.negative
    return tokens.colors.unknown


def tone_color(tokens: FionaDesignTokens, tone: str) -> str:
    return {
        "positive": tokens.colors.positive,
        "negative": tokens.colors.negative,
        "neutral": tokens.colors.neutral,
        "brand": tokens.colors.brand,
        "high_confidence": tokens.colors.high_confidence,
        "strong_confidence": tokens.colors.strong_confidence,
        "limited_confidence": tokens.colors.limited_confidence,
        "unknown": tokens.colors.unknown,
    }.get(str(tone).lower(), tokens.colors.unknown)


def market_accent(tokens: FionaDesignTokens, key: str) -> str:
    return {
        "us": tokens.colors.us,
        "china": tokens.colors.china,
        "crypto": tokens.colors.crypto,
        "rwa": tokens.colors.rwa,
    }.get(str(key).lower(), tokens.colors.unknown)


def format_narrative(
    item: NarrativeView,
    strings: FionaLocaleStrings = ZH_CN_STRINGS,
    *,
    max_name_chars: int = 16,
) -> str:
    confidence = f"{item.confidence}%" if item.confidence is not None else strings.confidence_unavailable
    return f"{semantic_limit(item.name, max_name_chars)} · {item.direction} · {confidence}"


def grid_x(tokens: FionaDesignTokens, column: int) -> int:
    content_width = tokens.canvas.width - tokens.spacing.outer_margin * 2
    column_width = (content_width - tokens.grid.gutter * (tokens.grid.columns - 1)) / tokens.grid.columns
    return round(tokens.spacing.outer_margin + column * (column_width + tokens.grid.gutter))


def validate_component_regions(tokens: FionaDesignTokens = FIONA_TOKENS) -> None:
    regions = sorted(tokens.regions.items(), key=lambda item: item[1].top)
    previous_bottom = 0
    for name, region in regions:
        if region.left != 0 or region.right != tokens.canvas.width:
            raise RuntimeError(f"{name} does not span the fixed canvas width.")
        if region.top < previous_bottom or region.bottom <= region.top:
            raise RuntimeError(f"{name} overlaps another component region.")
        if region.bottom > tokens.canvas.height:
            raise RuntimeError(f"{name} exceeds the fixed canvas height.")
        previous_bottom = region.bottom
    if previous_bottom != tokens.canvas.height:
        raise RuntimeError("Component regions do not fill the fixed canvas height.")


def mix(base: str, overlay: str, alpha: float) -> str:
    base_rgb = hex_rgb(base)
    overlay_rgb = hex_rgb(overlay)
    mixed = tuple(round(base_rgb[index] * (1 - alpha) + overlay_rgb[index] * alpha) for index in range(3))
    return "#" + "".join(f"{value:02X}" for value in mixed)


def hex_rgb(value: str) -> tuple[int, int, int]:
    clean = value.lstrip("#")
    return tuple(int(clean[index : index + 2], 16) for index in (0, 2, 4))
