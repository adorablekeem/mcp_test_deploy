"""
Size and transform utilities for Google Slides chart positioning.
Provides EMU conversion and size calculation functions.
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple, Union

logger = logging.getLogger(__name__)

# EMU Conversion Constants
INCHES_TO_EMU = 914400  # 1 inch = 914,400 EMU
PIXELS_TO_EMU = 12700  # 1 pixel = 12,700 EMU (assuming 72 DPI)
POINTS_TO_EMU = 12700  # 1 point = 12,700 EMU


@dataclass
class ChartSize:
    """Represents chart dimensions in EMU units."""

    width_emu: int
    height_emu: int

    def to_googleapi_size(self) -> Dict[str, Any]:
        """Convert to GoogleApiSupport Size format."""
        return {
            "width": {"magnitude": self.width_emu, "unit": "EMU"},
            "height": {"magnitude": self.height_emu, "unit": "EMU"},
        }

    def aspect_ratio(self) -> float:
        """Calculate aspect ratio (width/height)."""
        return self.width_emu / self.height_emu if self.height_emu > 0 else 1.0

    def scale(self, factor: float) -> "ChartSize":
        """Scale dimensions by a factor."""
        return ChartSize(width_emu=int(self.width_emu * factor), height_emu=int(self.height_emu * factor))


@dataclass
class ChartTransform:
    """Represents chart position and transformation in EMU units."""

    translate_x: int = 0
    translate_y: int = 0
    scale_x: float = 1.0
    scale_y: float = 1.0
    shear_x: float = 0.0
    shear_y: float = 0.0

    def to_googleapi_transform(self) -> Dict[str, Any]:
        """Convert to GoogleApiSupport Transform format."""
        return {
            "scaleX": self.scale_x,
            "scaleY": self.scale_y,
            "shearX": self.shear_x,
            "shearY": self.shear_y,
            "translateX": self.translate_x,
            "translateY": self.translate_y,
            "unit": "EMU",
        }


# Unit Conversion Functions


def inches_to_emu(inches: float) -> int:
    """Convert inches to EMU units."""
    return int(inches * INCHES_TO_EMU)


def pixels_to_emu(pixels: int, dpi: int = 72) -> int:
    """Convert pixels to EMU units."""
    return int(pixels * INCHES_TO_EMU / dpi)


def points_to_emu(points: float) -> int:
    """Convert points to EMU units."""
    return int(points * POINTS_TO_EMU)


def emu_to_inches(emu: int) -> float:
    """Convert EMU units to inches."""
    return emu / INCHES_TO_EMU


def emu_to_pixels(emu: int, dpi: int = 72) -> int:
    """Convert EMU units to pixels."""
    return int(emu * dpi / INCHES_TO_EMU)


# Standard Chart Sizes

STANDARD_CHART_SIZES = {
    "large_dashboard": ChartSize(inches_to_emu(8), inches_to_emu(5)),
    "medium_chart": ChartSize(inches_to_emu(6), inches_to_emu(4)),
    "small_thumbnail": ChartSize(inches_to_emu(3), inches_to_emu(2)),
    "square_chart": ChartSize(inches_to_emu(4), inches_to_emu(4)),
    "wide_chart": ChartSize(inches_to_emu(7), inches_to_emu(3)),
    "tall_chart": ChartSize(inches_to_emu(3), inches_to_emu(6)),
}

# Size Calculation Functions


def calculate_size_from_config(
    original_size: Dict[str, Any], sizing_config: Dict[str, Any], correlation_id: str = None
) -> ChartSize:
    """
    Calculate final chart size based on configuration.

    Args:
        original_size: Original placeholder size from Google Slides API
        sizing_config: Chart sizing configuration
        correlation_id: For logging

    Returns:
        ChartSize object with calculated dimensions
    """

    correlation_id = correlation_id or "size_calc"

    try:
        # Extract original dimensions
        orig_width = original_size.get("width", {}).get("magnitude", 0)
        orig_height = original_size.get("height", {}).get("magnitude", 0)

        # Method 1: Absolute size specified
        if "width_emu" in sizing_config and "height_emu" in sizing_config:
            target_width = int(sizing_config["width_emu"])
            target_height = int(sizing_config["height_emu"])

            # Maintain aspect ratio if requested
            if sizing_config.get("maintain_aspect_ratio", False) and orig_width > 0 and orig_height > 0:
                orig_ratio = orig_width / orig_height
                target_ratio = target_width / target_height

                if target_ratio > orig_ratio:
                    # Target is wider, constrain by height
                    target_width = int(target_height * orig_ratio)
                else:
                    # Target is taller, constrain by width
                    target_height = int(target_width / orig_ratio)

            logger.info(f"[{correlation_id}] Calculated absolute size: {target_width} x {target_height} EMU")
            return ChartSize(target_width, target_height)

        # Method 2: Scale factor specified
        elif "scale_factor" in sizing_config:
            scale = float(sizing_config["scale_factor"])
            target_width = int(orig_width * scale)
            target_height = int(orig_height * scale)

            logger.info(
                f"[{correlation_id}] Calculated scaled size: {target_width} x {target_height} EMU (scale: {scale})"
            )
            return ChartSize(target_width, target_height)

        # Method 3: Standard size name
        elif "standard_size" in sizing_config:
            size_name = sizing_config["standard_size"]
            if size_name in STANDARD_CHART_SIZES:
                standard_size = STANDARD_CHART_SIZES[size_name]
                logger.info(
                    f"[{correlation_id}] Using standard size '{size_name}': {standard_size.width_emu} x {standard_size.height_emu} EMU"
                )
                return standard_size
            else:
                logger.warning(f"[{correlation_id}] Unknown standard size '{size_name}', using original")

        # Method 4: Inches specified
        elif "width_inches" in sizing_config and "height_inches" in sizing_config:
            target_width = inches_to_emu(float(sizing_config["width_inches"]))
            target_height = inches_to_emu(float(sizing_config["height_inches"]))

            logger.info(f"[{correlation_id}] Calculated size from inches: {target_width} x {target_height} EMU")
            return ChartSize(target_width, target_height)

        # Default: Use original size
        logger.info(f"[{correlation_id}] Using original size: {orig_width} x {orig_height} EMU")
        return ChartSize(int(orig_width), int(orig_height))

    except Exception as e:
        logger.error(f"[{correlation_id}] Size calculation failed: {e}")
        # Fallback to original size
        orig_width = original_size.get("width", {}).get("magnitude", inches_to_emu(4))
        orig_height = original_size.get("height", {}).get("magnitude", inches_to_emu(3))
        return ChartSize(int(orig_width), int(orig_height))


def calculate_transform_for_size_change(
    original_transform: Dict[str, Any], original_size: ChartSize, new_size: ChartSize, anchor_point: str = "center"
) -> ChartTransform:
    """
    Calculate new transform to maintain positioning when size changes.

    Args:
        original_transform: Original transform from Google Slides API
        original_size: Original chart size
        new_size: New chart size
        anchor_point: How to anchor the resize ('center', 'top_left', etc.)

    Returns:
        ChartTransform with adjusted positioning
    """

    # Extract original transform values
    orig_translate_x = original_transform.get("translateX", 0)
    orig_translate_y = original_transform.get("translateY", 0)
    orig_scale_x = original_transform.get("scaleX", 1.0)
    orig_scale_y = original_transform.get("scaleY", 1.0)

    # Calculate size differences
    width_diff = new_size.width_emu - original_size.width_emu
    height_diff = new_size.height_emu - original_size.height_emu

    # Adjust translation based on anchor point
    new_translate_x = orig_translate_x
    new_translate_y = orig_translate_y

    if anchor_point == "center":
        # Keep center point the same
        new_translate_x = orig_translate_x - (width_diff // 2)
        new_translate_y = orig_translate_y - (height_diff // 2)
    elif anchor_point == "top_left":
        # Keep top-left corner the same
        pass  # No translation adjustment needed
    elif anchor_point == "top_right":
        new_translate_x = orig_translate_x - width_diff
    elif anchor_point == "bottom_left":
        new_translate_y = orig_translate_y - height_diff
    elif anchor_point == "bottom_right":
        new_translate_x = orig_translate_x - width_diff
        new_translate_y = orig_translate_y - height_diff

    return ChartTransform(
        translate_x=int(new_translate_x),
        translate_y=int(new_translate_y),
        scale_x=orig_scale_x,
        scale_y=orig_scale_y,
        shear_x=original_transform.get("shearX", 0.0),
        shear_y=original_transform.get("shearY", 0.0),
    )


def validate_size_config(config: Dict[str, Any]) -> bool:
    """
    Validate chart sizing configuration.

    Args:
        config: Sizing configuration dictionary

    Returns:
        True if valid, raises ValueError if invalid
    """

    if not isinstance(config, dict):
        raise ValueError("Sizing config must be a dictionary")

    # Check absolute size
    if "width_emu" in config or "height_emu" in config:
        if not ("width_emu" in config and "height_emu" in config):
            raise ValueError("Both width_emu and height_emu must be specified together")

        if not isinstance(config["width_emu"], (int, float)) or config["width_emu"] <= 0:
            raise ValueError("width_emu must be a positive number")

        if not isinstance(config["height_emu"], (int, float)) or config["height_emu"] <= 0:
            raise ValueError("height_emu must be a positive number")

    # Check scale factor
    if "scale_factor" in config:
        if not isinstance(config["scale_factor"], (int, float)) or config["scale_factor"] <= 0:
            raise ValueError("scale_factor must be a positive number")

    # Check inches
    if "width_inches" in config or "height_inches" in config:
        if not ("width_inches" in config and "height_inches" in config):
            raise ValueError("Both width_inches and height_inches must be specified together")

        if not isinstance(config["width_inches"], (int, float)) or config["width_inches"] <= 0:
            raise ValueError("width_inches must be a positive number")

        if not isinstance(config["height_inches"], (int, float)) or config["height_inches"] <= 0:
            raise ValueError("height_inches must be a positive number")

    # Check standard size
    if "standard_size" in config:
        if config["standard_size"] not in STANDARD_CHART_SIZES:
            available = list(STANDARD_CHART_SIZES.keys())
            raise ValueError(f"Unknown standard_size. Available: {available}")

    return True


class ChartSizingError(Exception):
    """Custom exception for chart sizing operations."""

    pass
