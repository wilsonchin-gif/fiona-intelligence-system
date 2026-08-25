from __future__ import annotations

from dataclasses import asdict, dataclass, fields
from types import MappingProxyType
from typing import Mapping


@dataclass(frozen=True)
class Region:
    left: int
    top: int
    right: int
    bottom: int

    @property
    def width(self) -> int:
        return self.right - self.left

    @property
    def height(self) -> int:
        return self.bottom - self.top

    def as_tuple(self) -> tuple[int, int, int, int]:
        return self.left, self.top, self.right, self.bottom


@dataclass(frozen=True)
class CanvasTokens:
    width: int = 1080
    height: int = 1350
    color_mode: str = "RGB"
    output_format: str = "PNG"
    max_file_size_bytes: int = 1_500_000
    safe_top: int = 24
    safe_bottom: int = 24
    minimum_text_size: int = 13


@dataclass(frozen=True)
class ColorTokens:
    background: str = "#07111A"
    surface: str = "#0E1B25"
    elevated: str = "#142532"
    border: str = "#263D4C"
    primary_text: str = "#F7F4EC"
    secondary_text: str = "#B7C2C9"
    muted_text: str = "#7D909D"
    brand: str = "#E0B84F"
    positive: str = "#55B391"
    negative: str = "#D1747B"
    neutral: str = "#C2A56A"
    unknown: str = "#718592"
    risk: str = "#D59362"
    high_confidence: str = "#55B391"
    strong_confidence: str = "#65A6C7"
    limited_confidence: str = "#718592"
    us: str = "#5B8FD9"
    china: str = "#C9787E"
    crypto: str = "#E0B84F"
    rwa: str = "#4D9A7F"


@dataclass(frozen=True)
class TypographyTokens:
    family_regular: str = "NotoSansSC-Regular.otf"
    family_bold: str = "NotoSansSC-Bold.otf"
    product_title: int = 42
    brand_wordmark: int = 20
    brand_descriptor: int = 16
    timestamp: int = 18
    badge: int = 18
    badge_meta: int = 14
    regime_label: int = 16
    regime_value: int = 31
    hero_label: int = 20
    hero_body: int = 27
    hero_meta: int = 17
    section_title: int = 21
    section_meta: int = 16
    market_label: int = 18
    market_score: int = 32
    market_metric: int = 18
    metric_suffix: int = 16
    change_index: int = 18
    change_headline: int = 21
    body: int = 17
    key_label: int = 17
    key_value: int = 27
    narrative: int = 18
    tag: int = 16
    footer: int = 15
    footer_brand: int = 19
    footer_meta: int = 13


@dataclass(frozen=True)
class SpacingTokens:
    xxs: int = 4
    xs: int = 8
    sm: int = 12
    md: int = 16
    lg: int = 24
    xl: int = 32
    xxl: int = 48
    outer_margin: int = 48
    section_gap: int = 16
    card_padding: int = 16


@dataclass(frozen=True)
class RadiusTokens:
    badge: int = 6
    card: int = 8
    tag: int = 6
    accent: int = 3


@dataclass(frozen=True)
class BorderTokens:
    width: int = 1
    divider_width: int = 1
    hero_outline: str = "#38566A"


@dataclass(frozen=True)
class ShadowTokens:
    enabled: bool = False
    color: str = "#000000"
    opacity: float = 0.0
    blur: int = 0
    offset_x: int = 0
    offset_y: int = 0


@dataclass(frozen=True)
class IconSizeTokens:
    small: int = 16
    medium: int = 20
    large: int = 24


@dataclass(frozen=True)
class GridTokens:
    columns: int = 12
    gutter: int = 16
    market_columns: int = 2
    key_market_columns: int = 5
    watch_columns: int = 3


@dataclass(frozen=True)
class SurfaceTokens:
    page: str = "background"
    evidence: str = "surface"
    judgment: str = "elevated"
    context: str = "surface"


@dataclass(frozen=True)
class FooterStyleTokens:
    signature: str = "FIONA INTELLIGENCE"
    descriptor: str = "AI MARKET INTELLIGENCE"
    signature_opacity_role: str = "secondary"
    divider: bool = True


REGIONS: Mapping[str, Region] = MappingProxyType(
    {
        "header": Region(0, 0, 1080, 126),
        "market_regime": Region(0, 126, 1080, 194),
        "fiona_view": Region(0, 194, 1080, 398),
        "heat_map": Region(0, 398, 1080, 606),
        "what_changed": Region(0, 606, 1080, 822),
        "key_markets": Region(0, 822, 1080, 984),
        "narrative": Region(0, 984, 1080, 1065),
        "watch_next": Region(0, 1065, 1080, 1165),
        "historical_context": Region(0, 1165, 1080, 1235),
        "tags": Region(0, 1235, 1080, 1275),
        "footer": Region(0, 1275, 1080, 1350),
    }
)


@dataclass(frozen=True)
class FionaDesignTokens:
    version: str
    canvas: CanvasTokens
    colors: ColorTokens
    typography: TypographyTokens
    spacing: SpacingTokens
    radius: RadiusTokens
    border: BorderTokens
    shadow: ShadowTokens
    icon_size: IconSizeTokens
    section_gap: int
    grid: GridTokens
    surfaces: SurfaceTokens
    footer: FooterStyleTokens
    regions: Mapping[str, Region]


FIONA_TOKENS = FionaDesignTokens(
    version="1.0.0",
    canvas=CanvasTokens(),
    colors=ColorTokens(),
    typography=TypographyTokens(),
    spacing=SpacingTokens(),
    radius=RadiusTokens(),
    border=BorderTokens(),
    shadow=ShadowTokens(),
    icon_size=IconSizeTokens(),
    section_gap=SpacingTokens().section_gap,
    grid=GridTokens(),
    surfaces=SurfaceTokens(),
    footer=FooterStyleTokens(),
    regions=REGIONS,
)


IOS_SCALE = 4 / 3


def scale_integer_tokens(instance: object, scale: float, **overrides: object) -> object:
    values: dict[str, object] = {}
    for item in fields(instance):
        value = getattr(instance, item.name)
        values[item.name] = round(value * scale) if isinstance(value, int) and not isinstance(value, bool) else value
    values.update(overrides)
    return type(instance)(**values)


IOS_REGIONS: Mapping[str, Region] = MappingProxyType(
    {
        name: Region(
            0,
            round(region.top * IOS_SCALE),
            1440,
            round(region.bottom * IOS_SCALE),
        )
        for name, region in REGIONS.items()
    }
)


FIONA_IOS_TOKENS = FionaDesignTokens(
    version="1.1.0-ios",
    canvas=CanvasTokens(
        width=1440,
        height=1800,
        color_mode="RGB",
        output_format="PNG",
        max_file_size_bytes=1_500_000,
        safe_top=48,
        safe_bottom=48,
        minimum_text_size=17,
    ),
    colors=ColorTokens(),
    typography=scale_integer_tokens(TypographyTokens(), IOS_SCALE),  # type: ignore[arg-type]
    spacing=scale_integer_tokens(SpacingTokens(), IOS_SCALE, outer_margin=72),  # type: ignore[arg-type]
    radius=scale_integer_tokens(RadiusTokens(), IOS_SCALE),  # type: ignore[arg-type]
    border=scale_integer_tokens(BorderTokens(), IOS_SCALE),  # type: ignore[arg-type]
    shadow=ShadowTokens(),
    icon_size=scale_integer_tokens(IconSizeTokens(), IOS_SCALE),  # type: ignore[arg-type]
    section_gap=round(SpacingTokens().section_gap * IOS_SCALE),
    grid=GridTokens(gutter=round(GridTokens().gutter * IOS_SCALE)),
    surfaces=SurfaceTokens(),
    footer=FooterStyleTokens(),
    regions=IOS_REGIONS,
)


def token_manifest(tokens: FionaDesignTokens = FIONA_TOKENS) -> dict[str, object]:
    return {
        "version": tokens.version,
        "canvas": asdict(tokens.canvas),
        "colors": asdict(tokens.colors),
        "typography": asdict(tokens.typography),
        "spacing": asdict(tokens.spacing),
        "radius": asdict(tokens.radius),
        "border": asdict(tokens.border),
        "shadow": asdict(tokens.shadow),
        "icon_size": asdict(tokens.icon_size),
        "section_gap": tokens.section_gap,
        "grid": asdict(tokens.grid),
        "surfaces": asdict(tokens.surfaces),
        "footer": asdict(tokens.footer),
        "regions": {name: region.as_tuple() for name, region in tokens.regions.items()},
    }
