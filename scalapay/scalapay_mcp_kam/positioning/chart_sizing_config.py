"""
Chart sizing configuration system.
Provides configuration loading and management for custom chart sizing.
"""

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from .size_utils import STANDARD_CHART_SIZES, inches_to_emu, validate_size_config

logger = logging.getLogger(__name__)

# Default chart sizing configurations
DEFAULT_CHART_SIZING_CONFIG = {
    # Sales and revenue charts - typically wider for time series
    "monthly_sales": {
        "width_inches": 7.5,
        "height_inches": 4.5,
        "maintain_aspect_ratio": False,
        "anchor_point": "center",
    },
    "monthly_sales_by_product_type": {
        "width_inches": 8.0,
        "height_inches": 5.0,
        "maintain_aspect_ratio": False,
        "anchor_point": "center",
    },
    "monthly_sales_year_over_year": {
        "width_inches": 8.0,
        "height_inches": 4.5,
        "maintain_aspect_ratio": False,
        "anchor_point": "center",
    },
    # Order volume charts
    "monthly_orders": {
        "width_inches": 7.0,
        "height_inches": 4.0,
        "maintain_aspect_ratio": False,
        "anchor_point": "center",
    },
    "monthly_orders_by_user_type": {
        "width_inches": 7.5,
        "height_inches": 4.5,
        "maintain_aspect_ratio": False,
        "anchor_point": "center",
    },
    "orders_by_product_type": {
        "standard_size": "medium_chart",
        "maintain_aspect_ratio": True,
        "anchor_point": "center",
    },
    # AOV (Average Order Value) charts
    "aov": {"width_inches": 6.5, "height_inches": 4.0, "maintain_aspect_ratio": False, "anchor_point": "center"},
    "aov_by_product_type": {
        "width_inches": 7.0,
        "height_inches": 4.5,
        "maintain_aspect_ratio": False,
        "anchor_point": "center",
    },
    # Demographic charts - often better as squares or pie charts
    "user_demographics": {"standard_size": "square_chart", "maintain_aspect_ratio": True, "anchor_point": "center"},
    "scalapay_users_demographic": {
        "width_inches": 5.0,
        "height_inches": 5.0,
        "maintain_aspect_ratio": True,
        "anchor_point": "center",
    },
    # Growth and trend charts
    "growth_metrics": {
        "width_inches": 8.0,
        "height_inches": 4.0,
        "maintain_aspect_ratio": False,
        "anchor_point": "center",
    },
    # Default fallback configuration
    "default": {"scale_factor": 1.0, "maintain_aspect_ratio": True, "anchor_point": "center"},
    # Small charts for dashboards
    "thumbnail": {"standard_size": "small_thumbnail", "maintain_aspect_ratio": True, "anchor_point": "center"},
    # Large featured charts
    "featured": {"standard_size": "large_dashboard", "maintain_aspect_ratio": False, "anchor_point": "center"},
}


class ChartSizingConfigManager:
    """Manages chart sizing configurations with support for custom overrides."""

    def __init__(self, config_dir: Optional[str] = None):
        """
        Initialize config manager.

        Args:
            config_dir: Directory to look for custom config files
        """
        self.config_dir = config_dir
        self._loaded_configs: Dict[str, Dict] = {}
        self._default_config = DEFAULT_CHART_SIZING_CONFIG.copy()

    def get_chart_sizing_config(
        self, data_types: List[str], presentation_id: Optional[str] = None, correlation_id: Optional[str] = None
    ) -> Dict[str, Dict[str, Any]]:
        """
        Get sizing configuration for specified chart data types.

        Args:
            data_types: List of chart data type names
            presentation_id: Presentation ID for presentation-specific configs
            correlation_id: For logging

        Returns:
            Dictionary mapping data_type -> sizing_config
        """

        correlation_id = correlation_id or "config_load"

        try:
            # Load presentation-specific config if available
            if presentation_id:
                self._load_presentation_config(presentation_id, correlation_id)

            # Build configuration for each data type
            result = {}
            for data_type in data_types:
                config = self._get_config_for_data_type(data_type, presentation_id, correlation_id)

                # Validate configuration
                try:
                    validate_size_config(config)
                    result[data_type] = config
                    logger.debug(f"[{correlation_id}] Loaded config for '{data_type}': {config}")
                except ValueError as e:
                    logger.warning(f"[{correlation_id}] Invalid config for '{data_type}': {e}, using default")
                    result[data_type] = self._default_config["default"].copy()

            logger.info(f"[{correlation_id}] Loaded sizing configs for {len(result)} chart types")
            return result

        except Exception as e:
            logger.error(f"[{correlation_id}] Failed to load sizing configs: {e}")

            # Return default configs for all data types
            return {data_type: self._default_config["default"].copy() for data_type in data_types}

    def _get_config_for_data_type(
        self, data_type: str, presentation_id: Optional[str] = None, correlation_id: str = "config"
    ) -> Dict[str, Any]:
        """Get configuration for a specific data type with fallback hierarchy."""

        # Priority order:
        # 1. Presentation-specific override for data_type
        # 2. Global config for data_type
        # 3. Default config

        if presentation_id and presentation_id in self._loaded_configs:
            pres_config = self._loaded_configs[presentation_id]
            if data_type in pres_config:
                return pres_config[data_type].copy()

        # Check default config for exact match
        if data_type in self._default_config:
            return self._default_config[data_type].copy()

        # Check for partial matches (e.g., "monthly_sales_chart" -> "monthly_sales")
        base_data_type = data_type.replace("_chart", "").replace("_graph", "")
        if base_data_type in self._default_config:
            logger.debug(f"[{correlation_id}] Using base config '{base_data_type}' for '{data_type}'")
            return self._default_config[base_data_type].copy()

        # Use default fallback
        logger.debug(f"[{correlation_id}] No specific config for '{data_type}', using default")
        return self._default_config["default"].copy()

    def _load_presentation_config(self, presentation_id: str, correlation_id: str = "config") -> None:
        """Load presentation-specific configuration if available."""

        if presentation_id in self._loaded_configs:
            return  # Already loaded

        if not self.config_dir:
            return  # No config directory specified

        config_file = Path(self.config_dir) / f"{presentation_id}_sizing.json"

        try:
            if config_file.exists():
                with open(config_file, "r") as f:
                    config_data = json.load(f)

                self._loaded_configs[presentation_id] = config_data
                logger.info(f"[{correlation_id}] Loaded presentation-specific config from {config_file}")
            else:
                self._loaded_configs[presentation_id] = {}  # Mark as checked

        except Exception as e:
            logger.warning(f"[{correlation_id}] Failed to load presentation config from {config_file}: {e}")
            self._loaded_configs[presentation_id] = {}

    def save_presentation_config(
        self, presentation_id: str, config: Dict[str, Dict[str, Any]], correlation_id: Optional[str] = None
    ) -> bool:
        """
        Save presentation-specific configuration.

        Args:
            presentation_id: Presentation ID
            config: Configuration dictionary mapping data_type -> sizing_config
            correlation_id: For logging

        Returns:
            True if saved successfully
        """

        correlation_id = correlation_id or "config_save"

        if not self.config_dir:
            logger.warning(f"[{correlation_id}] No config directory specified, cannot save")
            return False

        try:
            # Validate all configurations
            for data_type, sizing_config in config.items():
                validate_size_config(sizing_config)

            # Ensure config directory exists
            config_dir_path = Path(self.config_dir)
            config_dir_path.mkdir(parents=True, exist_ok=True)

            # Save configuration
            config_file = config_dir_path / f"{presentation_id}_sizing.json"
            with open(config_file, "w") as f:
                json.dump(config, f, indent=2)

            # Update loaded configs cache
            self._loaded_configs[presentation_id] = config.copy()

            logger.info(f"[{correlation_id}] Saved presentation config to {config_file}")
            return True

        except Exception as e:
            logger.error(f"[{correlation_id}] Failed to save presentation config: {e}")
            return False

    def get_available_standard_sizes(self) -> Dict[str, Dict[str, Any]]:
        """Get available standard chart sizes."""
        return {
            name: {
                "width_inches": round(size.width_emu / inches_to_emu(1), 1),
                "height_inches": round(size.height_emu / inches_to_emu(1), 1),
                "width_emu": size.width_emu,
                "height_emu": size.height_emu,
                "aspect_ratio": round(size.aspect_ratio(), 2),
            }
            for name, size in STANDARD_CHART_SIZES.items()
        }

    def add_custom_config(self, data_type: str, sizing_config: Dict[str, Any], global_override: bool = False) -> None:
        """
        Add or update a custom sizing configuration.

        Args:
            data_type: Chart data type name
            sizing_config: Sizing configuration
            global_override: If True, updates the default config permanently
        """

        # Validate configuration
        validate_size_config(sizing_config)

        if global_override:
            self._default_config[data_type] = sizing_config.copy()
            logger.info(f"Added global sizing config for '{data_type}'")
        else:
            # This would typically be saved as a user preference or temporary override
            logger.info(f"Added temporary sizing config for '{data_type}'")


# Global config manager instance
_config_manager: Optional[ChartSizingConfigManager] = None


def get_config_manager(config_dir: Optional[str] = None) -> ChartSizingConfigManager:
    """Get or create the global config manager instance."""
    global _config_manager

    if _config_manager is None or (config_dir and _config_manager.config_dir != config_dir):
        _config_manager = ChartSizingConfigManager(config_dir)

    return _config_manager


def get_chart_sizing_config(
    data_types: List[str],
    presentation_id: Optional[str] = None,
    config_dir: Optional[str] = None,
    correlation_id: Optional[str] = None,
) -> Dict[str, Dict[str, Any]]:
    """
    Convenience function to get chart sizing configuration.

    Args:
        data_types: List of chart data type names
        presentation_id: Presentation ID for presentation-specific configs
        config_dir: Directory to look for custom config files
        correlation_id: For logging

    Returns:
        Dictionary mapping data_type -> sizing_config
    """

    manager = get_config_manager(config_dir)
    return manager.get_chart_sizing_config(data_types, presentation_id, correlation_id)
