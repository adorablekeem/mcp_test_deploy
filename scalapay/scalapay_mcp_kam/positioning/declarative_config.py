"""
Declarative positioning and sizing configuration system.
Provides clean, template-driven approach to chart positioning without hardcoded values.
"""

import json
import logging
import os
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, NamedTuple, Optional, Tuple

logger = logging.getLogger(__name__)


class SizePreset(Enum):
    """Predefined size presets for different chart types."""

    DEFAULT = "default"
    WIDE_CHART = "wide_chart"  # For time series, bar charts
    TALL_CHART = "tall_chart"  # For stacked charts
    SQUARE_CHART = "square_chart"  # For pie charts
    LINE_CHART = "line_chart"  # For trend lines
    PIE_CHART = "pie_chart"  # For circular charts
    STACKED_CHART = "stacked_chart"  # For layered data
    COMPACT_CHART = "compact_chart"  # For smaller spaces


class PositionPreset(Enum):
    """Predefined position presets for different placements."""

    CENTER = "center"
    TOP_LEFT = "top_left"
    TOP_RIGHT = "top_right"
    TOP_CENTER = "top_center"
    BOTTOM_LEFT = "bottom_left"
    BOTTOM_RIGHT = "bottom_right"
    BOTTOM_CENTER = "bottom_center"
    LEFT_CENTER = "left_center"
    RIGHT_CENTER = "right_center"
    FULL_WIDTH = "full_width"


class ChartDimensions(NamedTuple):
    """Chart dimensions with units and constraints."""

    width: float
    height: float
    unit: str = "EMU"  # Google Slides native unit
    aspect_ratio: Optional[float] = None
    maintain_aspect_ratio: bool = True


class PositionOffset(NamedTuple):
    """Position offset from placeholder center."""

    x: float
    y: float
    unit: str = "EMU"


@dataclass
class ChartStylingConfig:
    """Chart-specific styling configuration."""

    # Core dimensions and positioning
    size_preset: SizePreset = SizePreset.DEFAULT
    position_preset: PositionPreset = PositionPreset.CENTER
    custom_dimensions: Optional[ChartDimensions] = None
    custom_position: Optional[PositionOffset] = None

    # Replacement behavior
    replace_method: str = "CENTER_INSIDE"  # CENTER_INSIDE, CENTER_CROP, FIT_FILL
    maintain_aspect_ratio: bool = True

    # Constraints
    min_width: Optional[float] = None
    max_width: Optional[float] = None
    min_height: Optional[float] = None
    max_height: Optional[float] = None

    # Template-specific overrides
    template_overrides: Dict[str, Any] = None

    def __post_init__(self):
        if self.template_overrides is None:
            self.template_overrides = {}


class DeclarativePositioningConfig:
    """Main configuration system for declarative positioning."""

    # Size presets in EMU units (1 inch = 914400 EMU)
    SIZE_PRESETS = {
        SizePreset.DEFAULT: ChartDimensions(5486400, 4115200),  # 6" x 4.5"
        SizePreset.WIDE_CHART: ChartDimensions(7315200, 3657600),  # 8" x 4"
        SizePreset.TALL_CHART: ChartDimensions(5486400, 5486400),  # 6" x 6"
        SizePreset.SQUARE_CHART: ChartDimensions(4572000, 4572000),  # 5" x 5"
        SizePreset.LINE_CHART: ChartDimensions(7315200, 3200400),  # 8" x 3.5"
        SizePreset.PIE_CHART: ChartDimensions(4115200, 4115200),  # 4.5" x 4.5"
        SizePreset.STACKED_CHART: ChartDimensions(6400800, 4572000),  # 7" x 5"
        SizePreset.COMPACT_CHART: ChartDimensions(4115200, 3200400),  # 4.5" x 3.5"
    }

    # Position offsets from placeholder center
    POSITION_PRESETS = {
        PositionPreset.CENTER: PositionOffset(0, 0),
        PositionPreset.TOP_LEFT: PositionOffset(-914400, -685800),  # -1" x, -0.75" y
        PositionPreset.TOP_RIGHT: PositionOffset(914400, -685800),  # +1" x, -0.75" y
        PositionPreset.TOP_CENTER: PositionOffset(0, -685800),  # 0" x, -0.75" y
        PositionPreset.BOTTOM_LEFT: PositionOffset(-914400, 685800),  # -1" x, +0.75" y
        PositionPreset.BOTTOM_RIGHT: PositionOffset(914400, 685800),  # +1" x, +0.75" y
        PositionPreset.BOTTOM_CENTER: PositionOffset(0, 685800),  # 0" x, +0.75" y
        PositionPreset.LEFT_CENTER: PositionOffset(-914400, 0),  # -1" x, 0" y
        PositionPreset.RIGHT_CENTER: PositionOffset(914400, 0),  # +1" x, 0" y
        PositionPreset.FULL_WIDTH: PositionOffset(0, 0),  # No offset, size handles width
    }

    # Default chart type configurations
    DEFAULT_CHART_CONFIGS = {
        # Monthly sales variations
        "monthly_sales": ChartStylingConfig(
            size_preset=SizePreset.WIDE_CHART, position_preset=PositionPreset.CENTER, replace_method="CENTER_INSIDE"
        ),
        "monthly_sales_yoy": ChartStylingConfig(
            size_preset=SizePreset.WIDE_CHART, position_preset=PositionPreset.CENTER, replace_method="CENTER_INSIDE"
        ),
        "monthly_sales_trend": ChartStylingConfig(
            size_preset=SizePreset.WIDE_CHART, position_preset=PositionPreset.CENTER, replace_method="CENTER_INSIDE"
        ),
        "monthly_sales_by_product": ChartStylingConfig(
            size_preset=SizePreset.STACKED_CHART, position_preset=PositionPreset.CENTER, replace_method="CENTER_INSIDE"
        ),
        # AOV variations
        "aov": ChartStylingConfig(
            size_preset=SizePreset.LINE_CHART, position_preset=PositionPreset.CENTER, replace_method="CENTER_INSIDE"
        ),
        "aov_by_product": ChartStylingConfig(
            size_preset=SizePreset.STACKED_CHART, position_preset=PositionPreset.CENTER, replace_method="CENTER_INSIDE"
        ),
        # Orders variations
        "monthly_orders": ChartStylingConfig(
            size_preset=SizePreset.WIDE_CHART, position_preset=PositionPreset.CENTER, replace_method="CENTER_INSIDE"
        ),
        "orders_by_user_type": ChartStylingConfig(
            size_preset=SizePreset.STACKED_CHART, position_preset=PositionPreset.CENTER, replace_method="CENTER_INSIDE"
        ),
        "orders_by_product_type": ChartStylingConfig(
            size_preset=SizePreset.STACKED_CHART, position_preset=PositionPreset.CENTER, replace_method="CENTER_INSIDE"
        ),
        # Demographics
        "user_demographics": ChartStylingConfig(
            size_preset=SizePreset.PIE_CHART, position_preset=PositionPreset.CENTER, replace_method="CENTER_INSIDE"
        ),
        "demographics": ChartStylingConfig(
            size_preset=SizePreset.PIE_CHART, position_preset=PositionPreset.CENTER, replace_method="CENTER_INSIDE"
        ),
        # Generic fallbacks
        "sales_chart": ChartStylingConfig(size_preset=SizePreset.WIDE_CHART, position_preset=PositionPreset.CENTER),
        "orders_chart": ChartStylingConfig(size_preset=SizePreset.DEFAULT, position_preset=PositionPreset.CENTER),
        "demographic_chart": ChartStylingConfig(
            size_preset=SizePreset.PIE_CHART, position_preset=PositionPreset.CENTER
        ),
        "generic_chart": ChartStylingConfig(size_preset=SizePreset.DEFAULT, position_preset=PositionPreset.CENTER),
    }

    @classmethod
    def get_chart_config(cls, chart_type: str, template_id: Optional[str] = None) -> ChartStylingConfig:
        """
        Get styling configuration for a chart type.

        Args:
            chart_type: Detected chart type (e.g., "monthly_sales", "aov")
            template_id: Optional template ID for template-specific overrides

        Returns:
            ChartStylingConfig with appropriate settings
        """

        # Normalize chart type
        normalized_type = chart_type.lower().replace(" ", "_").replace("-", "_")

        # Try exact match first
        if normalized_type in cls.DEFAULT_CHART_CONFIGS:
            config = cls.DEFAULT_CHART_CONFIGS[normalized_type]
        else:
            # Try pattern matching for variations
            config = cls._find_similar_config(normalized_type)

        # Apply template-specific overrides if available
        if template_id and template_id in config.template_overrides:
            overrides = config.template_overrides[template_id]
            config = cls._apply_overrides(config, overrides)

        return config

    @classmethod
    def _find_similar_config(cls, chart_type: str) -> ChartStylingConfig:
        """Find configuration for similar chart type."""

        # Define similarity patterns
        similarity_patterns = [
            (["monthly", "sales"], "monthly_sales"),
            (["aov", "average"], "aov"),
            (["orders", "user"], "orders_by_user_type"),
            (["orders", "product"], "orders_by_product_type"),
            (["demographic", "users"], "user_demographics"),
            (["sales"], "sales_chart"),
            (["orders"], "orders_chart"),
            (["demographic"], "demographic_chart"),
        ]

        for keywords, config_key in similarity_patterns:
            if all(keyword in chart_type for keyword in keywords):
                return cls.DEFAULT_CHART_CONFIGS[config_key]

        # Ultimate fallback
        return cls.DEFAULT_CHART_CONFIGS["generic_chart"]

    @classmethod
    def _apply_overrides(cls, base_config: ChartStylingConfig, overrides: Dict[str, Any]) -> ChartStylingConfig:
        """Apply template-specific overrides to base configuration."""

        # Create copy of base config
        config_dict = asdict(base_config)

        # Apply overrides
        for key, value in overrides.items():
            if key in config_dict:
                if key in ["size_preset", "position_preset"]:
                    # Handle enum values
                    if isinstance(value, str):
                        if key == "size_preset":
                            config_dict[key] = SizePreset(value)
                        elif key == "position_preset":
                            config_dict[key] = PositionPreset(value)
                    else:
                        config_dict[key] = value
                else:
                    config_dict[key] = value

        return ChartStylingConfig(**config_dict)

    @classmethod
    def resolve_dimensions_and_position(
        cls,
        config: ChartStylingConfig,
        placeholder_width: Optional[float] = None,
        placeholder_height: Optional[float] = None,
        placeholder_x: Optional[float] = None,
        placeholder_y: Optional[float] = None,
    ) -> Tuple[ChartDimensions, PositionOffset]:
        """
        Resolve final dimensions and position based on configuration and placeholder info.

        Args:
            config: Chart styling configuration
            placeholder_width: Current placeholder width (if known)
            placeholder_height: Current placeholder height (if known)
            placeholder_x: Current placeholder X position (if known)
            placeholder_y: Current placeholder Y position (if known)

        Returns:
            Tuple of (final_dimensions, final_position)
        """

        # Resolve dimensions
        if config.custom_dimensions:
            dimensions = config.custom_dimensions
        else:
            dimensions = cls.SIZE_PRESETS[config.size_preset]

        # Apply constraints
        final_width = dimensions.width
        final_height = dimensions.height

        if config.min_width and final_width < config.min_width:
            final_width = config.min_width
            if config.maintain_aspect_ratio and dimensions.aspect_ratio:
                final_height = final_width / dimensions.aspect_ratio

        if config.max_width and final_width > config.max_width:
            final_width = config.max_width
            if config.maintain_aspect_ratio and dimensions.aspect_ratio:
                final_height = final_width / dimensions.aspect_ratio

        if config.min_height and final_height < config.min_height:
            final_height = config.min_height
            if config.maintain_aspect_ratio and dimensions.aspect_ratio:
                final_width = final_height * dimensions.aspect_ratio

        if config.max_height and final_height > config.max_height:
            final_height = config.max_height
            if config.maintain_aspect_ratio and dimensions.aspect_ratio:
                final_width = final_height * dimensions.aspect_ratio

        final_dimensions = ChartDimensions(
            width=final_width,
            height=final_height,
            unit=dimensions.unit,
            aspect_ratio=dimensions.aspect_ratio,
            maintain_aspect_ratio=dimensions.maintain_aspect_ratio,
        )

        # Resolve position
        if config.custom_position:
            position_offset = config.custom_position
        else:
            position_offset = cls.POSITION_PRESETS[config.position_preset]

        # Calculate final position relative to placeholder
        final_x = (placeholder_x or 0) + position_offset.x
        final_y = (placeholder_y or 0) + position_offset.y

        final_position = PositionOffset(x=final_x, y=final_y, unit=position_offset.unit)

        return final_dimensions, final_position


class TemplateConfigManager:
    """Manages template-specific configuration files."""

    def __init__(self, config_dir: str = "scalapay/scalapay_mcp_kam/positioning/templates"):
        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.loaded_configs: Dict[str, Dict[str, Any]] = {}

    def load_template_config(self, template_id: str) -> Dict[str, Any]:
        """Load configuration for a specific template."""

        if template_id in self.loaded_configs:
            return self.loaded_configs[template_id]

        config_file = self.config_dir / f"{template_id}.json"

        if config_file.exists():
            try:
                with open(config_file, "r") as f:
                    config = json.load(f)
                    self.loaded_configs[template_id] = config
                    logger.debug(f"Loaded template config for {template_id}")
                    return config
            except Exception as e:
                logger.warning(f"Failed to load template config {config_file}: {e}")

        # Return empty config if not found
        return {}

    def save_template_config(self, template_id: str, config: Dict[str, Any]):
        """Save configuration for a template."""

        config_file = self.config_dir / f"{template_id}.json"

        try:
            with open(config_file, "w") as f:
                json.dump(config, f, indent=2, sort_keys=True)

            self.loaded_configs[template_id] = config
            logger.info(f"Saved template config for {template_id}")

        except Exception as e:
            logger.error(f"Failed to save template config {config_file}: {e}")

    def create_default_template_config(self, template_id: str) -> Dict[str, Any]:
        """Create a default configuration file for a template."""

        default_config = {
            "template_name": f"Template {template_id}",
            "version": "1.0",
            "chart_overrides": {
                "monthly_sales": {
                    "size_preset": "wide_chart",
                    "position_preset": "center",
                    "replace_method": "CENTER_INSIDE",
                },
                "aov": {"size_preset": "line_chart", "position_preset": "center", "replace_method": "CENTER_INSIDE"},
                "user_demographics": {
                    "size_preset": "pie_chart",
                    "position_preset": "center",
                    "replace_method": "CENTER_INSIDE",
                },
            },
            "global_settings": {
                "default_replace_method": "CENTER_INSIDE",
                "enable_aspect_ratio_lock": True,
                "units": "EMU",
            },
        }

        self.save_template_config(template_id, default_config)
        return default_config


# Global configuration manager instance
_config_manager = None


def get_config_manager() -> TemplateConfigManager:
    """Get global configuration manager instance."""
    global _config_manager
    if _config_manager is None:
        _config_manager = TemplateConfigManager()
    return _config_manager


# Convenience functions
def get_chart_styling_config(chart_type: str, template_id: Optional[str] = None) -> ChartStylingConfig:
    """Convenience function to get chart styling configuration."""
    return DeclarativePositioningConfig.get_chart_config(chart_type, template_id)


def resolve_chart_layout(
    chart_type: str, template_id: Optional[str] = None, placeholder_info: Optional[Dict[str, Any]] = None
) -> Tuple[ChartDimensions, PositionOffset]:
    """
    Convenience function to resolve complete chart layout.

    Args:
        chart_type: Type of chart to layout
        template_id: Optional template ID for overrides
        placeholder_info: Optional placeholder size/position info

    Returns:
        Tuple of (dimensions, position)
    """
    config = get_chart_styling_config(chart_type, template_id)

    placeholder_width = None
    placeholder_height = None
    placeholder_x = None
    placeholder_y = None

    if placeholder_info:
        placeholder_width = placeholder_info.get("current_width")
        placeholder_height = placeholder_info.get("current_height")
        placeholder_x = placeholder_info.get("current_x")
        placeholder_y = placeholder_info.get("current_y")

    return DeclarativePositioningConfig.resolve_dimensions_and_position(
        config, placeholder_width, placeholder_height, placeholder_x, placeholder_y
    )
