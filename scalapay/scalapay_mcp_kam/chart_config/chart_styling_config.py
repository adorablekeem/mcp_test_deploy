"""
Chart-specific styling configuration for batch operations.
Defines positioning, sizing, and layout styles for different chart types and content.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional


class ChartType(Enum):
    """Enumeration of supported chart types."""

    BAR = "bar"
    STACKED_BAR = "stacked_bar"
    LINE = "line"
    PIE = "pie"
    AREA = "area"
    SCATTER = "scatter"
    COMBO = "combo"


class SlideLayout(Enum):
    """Enumeration of slide layout types."""

    TITLE_AND_CONTENT = "title_and_content"
    TITLE_ONLY = "title_only"
    CONTENT_ONLY = "content_only"
    TWO_COLUMN = "two_column"
    COMPARISON = "comparison"
    SECTION_HEADER = "section_header"


@dataclass
class TextStyling:
    """Text styling configuration."""

    font_size: int = 12
    font_family: str = "Arial"
    bold: bool = False
    italic: bool = False
    color: str = "#000000"
    alignment: str = "LEFT"  # LEFT, CENTER, RIGHT, JUSTIFY
    line_spacing: float = 1.0
    margin_top: int = 0
    margin_bottom: int = 0
    margin_left: int = 0
    margin_right: int = 0


@dataclass
class ImageStyling:
    """Image styling and positioning configuration."""

    # Size configuration (absolute dimensions)
    width: Optional[int] = None  # Absolute width in points
    height: Optional[int] = None  # Absolute height in points

    # Position configuration
    translate_x: int = 130
    translate_y: int = 250
    anchor_point: str = "TOP_LEFT"  # TOP_LEFT, CENTER, BOTTOM_RIGHT, etc.

    # Resize configuration
    resize_mode: str = "ABSOLUTE"  # ABSOLUTE, RELATIVE
    unit: str = "PT"  # PT (points), PX (pixels)
    replace_method: str = "CENTER_INSIDE"  # CENTER_INSIDE, CENTER_CROP, FIT_FILL

    # Layout constraints
    maintain_aspect_ratio: bool = True
    max_width: Optional[int] = None
    max_height: Optional[int] = None
    min_width: Optional[int] = None
    min_height: Optional[int] = None


@dataclass
class SlideStyleConfig:
    """Complete styling configuration for a slide."""

    slide_layout: SlideLayout = SlideLayout.TITLE_AND_CONTENT

    # Title styling
    title_style: TextStyling = None

    # Content text styling
    content_style: TextStyling = None

    # Image/chart styling
    image_style: ImageStyling = None

    # Slide-level properties
    background_color: Optional[str] = None
    slide_number_visible: bool = True

    def __post_init__(self):
        if self.title_style is None:
            self.title_style = TextStyling(font_size=24, bold=True, alignment="CENTER")
        if self.content_style is None:
            self.content_style = TextStyling(font_size=14, alignment="LEFT")
        if self.image_style is None:
            self.image_style = ImageStyling()


# Chart-specific styling configurations
CHART_STYLE_CONFIGS = {
    # Bar Charts - Typically need more horizontal space
    ChartType.BAR: {
        "monthly_sales": SlideStyleConfig(
            slide_layout=SlideLayout.TITLE_AND_CONTENT,
            title_style=TextStyling(font_size=28, bold=True, alignment="CENTER", color="#1f4e79"),
            content_style=TextStyling(font_size=14, alignment="LEFT", line_spacing=1.2),
            image_style=ImageStyling(
                width=700,
                height=700,  # Wide for bar charts with labels
                translate_x=80,
                translate_y=200,
                replace_method="CENTER_INSIDE",
                maintain_aspect_ratio=True,
                max_width=700,
                max_height=700,
            ),
        ),
        "yearly_comparison": SlideStyleConfig(
            slide_layout=SlideLayout.TITLE_AND_CONTENT,
            title_style=TextStyling(font_size=26, bold=True, alignment="CENTER", color="#2f5f8f"),
            content_style=TextStyling(font_size=13, alignment="LEFT", line_spacing=1.1),
            image_style=ImageStyling(
                width=580,
                height=320,
                translate_x=110,
                translate_y=220,
                replace_method="CENTER_INSIDE",
                maintain_aspect_ratio=True,
                max_width=620,
                max_height=360,
            ),
        ),
        "default": SlideStyleConfig(
            image_style=ImageStyling(
                width=580,
                height=320,
                translate_x=110,
                translate_y=220,
                replace_method="CENTER_INSIDE",
                maintain_aspect_ratio=True,
                max_width=620,
                max_height=360,
            )
        ),
    },
    # Stacked Bar Charts - Similar to bar but with legend space
    ChartType.STACKED_BAR: {
        "user_type_orders": SlideStyleConfig(
            slide_layout=SlideLayout.TITLE_AND_CONTENT,
            title_style=TextStyling(font_size=26, bold=True, alignment="CENTER", color="#8b4513"),
            content_style=TextStyling(font_size=14, alignment="LEFT", line_spacing=1.2),
            image_style=ImageStyling(
                width=580,
                height=380,  # Taller for stacked data, space for legend
                translate_x=90,
                translate_y=160,
                replace_method="CENTER_INSIDE",
                maintain_aspect_ratio=True,
                max_width=620,
                max_height=420,
            ),
        ),
        "product_type_analysis": SlideStyleConfig(
            slide_layout=SlideLayout.TITLE_AND_CONTENT,
            title_style=TextStyling(font_size=24, bold=True, alignment="CENTER", color="#6a4c93"),
            content_style=TextStyling(font_size=13, alignment="LEFT", line_spacing=1.1),
            image_style=ImageStyling(
                width=590,
                height=370,
                translate_x=85,
                translate_y=170,
                replace_method="CENTER_INSIDE",
                maintain_aspect_ratio=True,
                max_width=630,
                max_height=410,
            ),
        ),
        "default": SlideStyleConfig(
            image_style=ImageStyling(
                width=580,
                height=380,
                translate_x=90,
                translate_y=160,
                replace_method="CENTER_INSIDE",
                maintain_aspect_ratio=True,
                max_width=620,
                max_height=420,
            )
        ),
    },
    # Line Charts - Good for time series, need space for trend lines
    ChartType.LINE: {
        "aov_trends": SlideStyleConfig(
            slide_layout=SlideLayout.TITLE_AND_CONTENT,
            title_style=TextStyling(font_size=26, bold=True, alignment="CENTER", color="#d2691e"),
            content_style=TextStyling(font_size=14, alignment="LEFT", line_spacing=1.2),
            image_style=ImageStyling(
                width=650,
                height=300,  # Wide for time series trends
                translate_x=60,
                translate_y=230,
                replace_method="CENTER_INSIDE",
                maintain_aspect_ratio=True,
                max_width=700,
                max_height=350,
            ),
        ),
        "time_series": SlideStyleConfig(
            slide_layout=SlideLayout.TITLE_AND_CONTENT,
            title_style=TextStyling(font_size=25, bold=True, alignment="CENTER", color="#ff6347"),
            content_style=TextStyling(font_size=13, alignment="LEFT", line_spacing=1.1),
            image_style=ImageStyling(
                width=640,
                height=320,
                translate_x=70,
                translate_y=220,
                replace_method="CENTER_INSIDE",
                maintain_aspect_ratio=True,
                max_width=680,
                max_height=360,
            ),
        ),
        "default": SlideStyleConfig(
            image_style=ImageStyling(
                width=640,
                height=300,
                translate_x=80,
                translate_y=240,
                replace_method="CENTER_INSIDE",
                maintain_aspect_ratio=True,
                max_width=680,
                max_height=350,
            )
        ),
    },
    # Pie Charts - Usually square, need space for labels
    ChartType.PIE: {
        "demographics": SlideStyleConfig(
            slide_layout=SlideLayout.TITLE_AND_CONTENT,
            title_style=TextStyling(font_size=24, bold=True, alignment="CENTER", color="#4682b4"),
            content_style=TextStyling(font_size=14, alignment="LEFT", line_spacing=1.3),
            image_style=ImageStyling(
                width=400,
                height=400,  # Square for pie charts with labels
                translate_x=150,
                translate_y=180,
                replace_method="CENTER_INSIDE",
                maintain_aspect_ratio=True,
                max_width=450,
                max_height=450,
            ),
        ),
        "distribution": SlideStyleConfig(
            slide_layout=SlideLayout.TITLE_AND_CONTENT,
            title_style=TextStyling(font_size=23, bold=True, alignment="CENTER", color="#32cd32"),
            content_style=TextStyling(font_size=13, alignment="LEFT", line_spacing=1.2),
            image_style=ImageStyling(
                width=420,
                height=420,
                translate_x=140,
                translate_y=170,
                replace_method="CENTER_INSIDE",
                maintain_aspect_ratio=True,
                max_width=470,
                max_height=470,
            ),
        ),
        "default": SlideStyleConfig(
            image_style=ImageStyling(
                width=400,
                height=400,
                translate_x=150,
                translate_y=180,
                replace_method="CENTER_INSIDE",
                maintain_aspect_ratio=True,
                max_width=450,
                max_height=450,
            )
        ),
    },
}


# Content-based style selection patterns
CONTENT_STYLE_PATTERNS = [
    {"pattern": r"monthly sales.*year over year", "chart_type": ChartType.BAR, "style_key": "yearly_comparison"},
    {"pattern": r"monthly sales.*over time", "chart_type": ChartType.BAR, "style_key": "monthly_sales"},
    {"pattern": r"orders by user type", "chart_type": ChartType.STACKED_BAR, "style_key": "user_type_orders"},
    {"pattern": r".*by product type", "chart_type": ChartType.STACKED_BAR, "style_key": "product_type_analysis"},
    {
        "pattern": r"AOV.*over time|average order value.*over time",
        "chart_type": ChartType.LINE,
        "style_key": "aov_trends",
    },
    {
        "pattern": r".*demographic.*percentage|.*users.*demographic",
        "chart_type": ChartType.PIE,
        "style_key": "demographics",
    },
    {"pattern": r"distribution|percentage breakdown", "chart_type": ChartType.PIE, "style_key": "distribution"},
]


def detect_chart_type_from_data_type(data_type: str) -> ChartType:
    """
    Detect chart type from data type string.
    This matches the logic from agent_matplot.py
    """
    data_type_lower = data_type.lower()

    if "aov" in data_type_lower or "average order value" in data_type_lower:
        return ChartType.LINE
    elif "user type" in data_type_lower or "product type" in data_type_lower:
        return ChartType.STACKED_BAR
    elif "demographic" in data_type_lower or "percentage" in data_type_lower:
        return ChartType.PIE
    else:
        return ChartType.BAR


def select_style_config(
    data_type: str, paragraph: str = "", chart_type: Optional[ChartType] = None
) -> SlideStyleConfig:
    """
    Select the appropriate style configuration based on data type and content.

    Args:
        data_type: Type of data/chart being displayed
        paragraph: Content paragraph that might contain style hints
        chart_type: Explicit chart type (if known)

    Returns:
        SlideStyleConfig object with appropriate styling
    """
    import re

    # Auto-detect chart type if not provided
    if chart_type is None:
        chart_type = detect_chart_type_from_data_type(data_type)

    # Try to match specific content patterns
    search_text = f"{data_type} {paragraph}".lower()

    for pattern_config in CONTENT_STYLE_PATTERNS:
        if re.search(pattern_config["pattern"], search_text, re.IGNORECASE):
            expected_chart_type = pattern_config["chart_type"]
            style_key = pattern_config["style_key"]

            # Check if the detected chart type matches
            if chart_type == expected_chart_type:
                chart_configs = CHART_STYLE_CONFIGS.get(chart_type, {})
                if style_key in chart_configs:
                    return chart_configs[style_key]

    # Fall back to default for the chart type
    chart_configs = CHART_STYLE_CONFIGS.get(chart_type, {})
    if "default" in chart_configs:
        return chart_configs["default"]

    # Ultimate fallback - basic configuration
    return SlideStyleConfig()


def get_image_style_for_slide(
    data_type: str,
    paragraph: str = "",
    chart_type: Optional[ChartType] = None,
    chart_width_px: Optional[int] = None,
    chart_height_px: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Get image styling configuration formatted for Google Slides API.
    Calculates width and height in points based on pixel dimensions and aspect ratio.

    Args:
        data_type: Type of data/chart being displayed
        paragraph: Content paragraph that might contain style hints
        chart_type: Explicit chart type (if known)
        chart_width_px: Actual width of the generated chart image in pixels
        chart_height_px: Actual height of the generated chart image in pixels

    Returns:
        Dictionary with resize, translate, and other image parameters
    """
    style_config = select_style_config(data_type, paragraph, chart_type)
    image_style = style_config.image_style

    # Convert pixels to points (1 inch = 72 points, 1 inch = 96 pixels)
    # So, 1 pixel = 72/96 points = 0.75 points
    PX_TO_PT = 0.75

    target_width_pt = image_style.width
    target_height_pt = image_style.height

    if chart_width_px and chart_height_px:
        # Calculate aspect ratio of the original chart
        original_aspect_ratio = chart_width_px / chart_height_px

        if image_style.maintain_aspect_ratio:
            # If target width/height are not specified, use a default or calculate from max constraints
            if target_width_pt is None and target_height_pt is None:
                # Default to a reasonable size if no specific target is set
                target_width_pt = image_style.max_width or 400
                target_height_pt = image_style.max_height or (target_width_pt / original_aspect_ratio)
            elif target_width_pt is None:
                target_width_pt = target_height_pt * original_aspect_ratio
            elif target_height_pt is None:
                target_height_pt = target_width_pt / original_aspect_ratio

            # Apply max constraints while maintaining aspect ratio
            if image_style.max_width and target_width_pt > image_style.max_width:
                target_width_pt = image_style.max_width
                target_height_pt = target_width_pt / original_aspect_ratio
            if image_style.max_height and target_height_pt > image_style.max_height:
                target_height_pt = image_style.max_height
                target_width_pt = target_height_pt * original_aspect_ratio

        else:
            # If aspect ratio is not maintained, use target width/height or defaults
            if target_width_pt is None:
                target_width_pt = image_style.max_width or (chart_width_px * PX_TO_PT)
            if target_height_pt is None:
                target_height_pt = image_style.max_height or (chart_height_px * PX_TO_PT)

        # Ensure minimum dimensions are met
        if image_style.min_width and target_width_pt < image_style.min_width:
            target_width_pt = image_style.min_width
            if image_style.maintain_aspect_ratio:
                target_height_pt = target_width_pt / original_aspect_ratio
        if image_style.min_height and target_height_pt < image_style.min_height:
            target_height_pt = image_style.min_height
            if image_style.maintain_aspect_ratio:
                target_width_pt = target_height_pt * original_aspect_ratio

    else:
        # Fallback if pixel dimensions are not provided
        if target_width_pt is None:
            target_width_pt = image_style.max_width or 400  # Default width
        if target_height_pt is None:
            target_height_pt = image_style.max_height or 300  # Default height

    return {
        "resize": {
            "mode": image_style.resize_mode,
            "width": round(target_width_pt),
            "height": round(target_height_pt),
            "unit": image_style.unit,
            "translateX": image_style.translate_x,
            "translateY": image_style.translate_y,
        },
        "replace_method": image_style.replace_method,
        "maintain_aspect_ratio": image_style.maintain_aspect_ratio,
        "constraints": {
            "max_width": image_style.max_width,
            "max_height": image_style.max_height,
            "min_width": image_style.min_width,
            "min_height": image_style.min_height,
        },
    }


def get_text_style_for_slide(
    data_type: str, paragraph: str = "", element_type: str = "content"  # "title" or "content"
) -> Dict[str, Any]:
    """
    Get text styling configuration formatted for Google Slides API.

    Args:
        data_type: Type of data/chart being displayed
        paragraph: Content paragraph
        element_type: "title" or "content"

    Returns:
        Dictionary with text formatting parameters
    """
    style_config = select_style_config(data_type, paragraph)

    if element_type == "title":
        text_style = style_config.title_style
    else:
        text_style = style_config.content_style

    return {
        "font_size": text_style.font_size,
        "font_family": text_style.font_family,
        "bold": text_style.bold,
        "italic": text_style.italic,
        "color": text_style.color,
        "alignment": text_style.alignment,
        "line_spacing": text_style.line_spacing,
        "margins": {
            "top": text_style.margin_top,
            "bottom": text_style.margin_bottom,
            "left": text_style.margin_left,
            "right": text_style.margin_right,
        },
    }
