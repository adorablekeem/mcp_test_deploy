"""
Clean Positioning System for Google Slides Chart Positioning

This package provides a complete replacement for the existing complex positioning logic
with a clean, declarative, and maintainable system using GoogleApiSupport.

Key Features:
- Template-driven placeholder discovery
- Declarative positioning configuration  
- Feature flags for safe rollback
- Drop-in replacements for existing functions
- Comprehensive error handling and monitoring
- Full backward compatibility

Usage:
    # For new code - use the clean API directly
    from scalapay.scalapay_mcp_kam.positioning import CleanChartPositioner
    
    positioner = CleanChartPositioner(presentation_id)
    await positioner.initialize()
    result = await positioner.position_charts_batch(image_map, slide_metadata)
    
    # For existing code - drop-in replacement
    from scalapay.scalapay_mcp_kam.positioning import apply_chart_specific_positioning_correctly
    
    # This function has identical signature to the legacy version
    result = await apply_chart_specific_positioning_correctly(
        slides_service, presentation_id, image_map, slide_metadata
    )

Configuration:
    The system can be configured via environment variables or configuration files:
    
    # Environment variables
    POSITIONING_MODE=clean|legacy|hybrid|auto
    CLEAN_POSITIONING_ROLLOUT=25.0  # Percentage rollout
    ENABLE_TEMPLATE_DISCOVERY=true
    ENABLE_BATCH_OPERATIONS=true
    
    # Or via configuration file
    scalapay/scalapay_mcp_kam/positioning/config.json

Emergency Rollback:
    from scalapay.scalapay_mcp_kam.positioning import emergency_rollback
    emergency_rollback("Production issue detected")
"""

import logging

# Core components
from .clean_replacements import CleanChartPositioner

# Configuration management
from .declarative_config import get_chart_styling_config, get_config_manager, resolve_chart_layout

# Feature flag controls
from .feature_flags import (
    emergency_rollback,
    get_feature_manager,
    record_positioning_performance,
    should_use_clean_positioning,
)
from .google_api_wrapper import get_api_wrapper
from .template_discovery import ChartPlaceholderMapper, TemplatePlaceholderAnalyzer

# Drop-in replacement functions (main public API) - will be imported dynamically
# from .clean_replacements import (
#     apply_chart_specific_positioning_correctly,
#     fill_template_with_clean_positioning,
#     apply_chart_specific_positioning_correctly_with_fallback
# )



# Version info
__version__ = "1.0.0"
__author__ = "Scalapay MCP KAM Team"

logger = logging.getLogger(__name__)

# Package-level convenience functions


def get_positioning_status() -> dict:
    """Get current status of the positioning system."""
    feature_manager = get_feature_manager()

    return {
        "version": __version__,
        "current_mode": feature_manager.flags.positioning_mode.value,
        "rollout_percentage": feature_manager.flags.rollout_percentage,
        "features_enabled": {
            "template_discovery": feature_manager.flags.enable_template_discovery,
            "declarative_config": feature_manager.flags.enable_declarative_config,
            "batch_operations": feature_manager.flags.enable_batch_operations,
            "concurrent_uploads": feature_manager.flags.enable_concurrent_uploads,
            "fallback_on_error": feature_manager.flags.enable_fallback_on_error,
        },
        "performance_stats": feature_manager.get_performance_stats(),
        "googleapi_support_available": get_api_wrapper()._googleapi_available,
    }


def configure_positioning(
    mode: str = None, rollout_percentage: float = None, enable_features: dict = None, save_config: bool = True
):
    """
    Configure the positioning system dynamically.

    Args:
        mode: Positioning mode ('clean', 'legacy', 'hybrid', 'auto')
        rollout_percentage: Percentage of requests to use clean mode (0-100)
        enable_features: Dictionary of features to enable/disable
        save_config: Whether to save configuration to file

    Example:
        configure_positioning(
            mode='hybrid',
            rollout_percentage=50.0,
            enable_features={
                'template_discovery': True,
                'batch_operations': True,
                'concurrent_uploads': False
            }
        )
    """
    feature_manager = get_feature_manager()

    if mode is not None:
        from .feature_flags import PositioningMode

        feature_manager.update_flags(positioning_mode=PositioningMode(mode))

    if rollout_percentage is not None:
        feature_manager.update_flags(rollout_percentage=rollout_percentage)

    if enable_features:
        for feature, enabled in enable_features.items():
            if hasattr(feature_manager.flags, f"enable_{feature}"):
                feature_manager.update_flags(**{f"enable_{feature}": enabled})

    if save_config:
        feature_manager.save_config()

    logger.info(f"Positioning system configured: mode={mode}, rollout={rollout_percentage}%")


def create_template_config(template_id: str) -> dict:
    """
    Create a default configuration file for a template.

    Args:
        template_id: Google Slides template ID

    Returns:
        Created configuration dictionary
    """
    config_manager = get_config_manager()
    return config_manager.create_default_template_config(template_id)


# Dynamic import functions to avoid circular imports
def get_clean_positioning_functions():
    """Get clean positioning functions dynamically."""
    try:
        from .clean_replacements import (
            apply_chart_specific_positioning_correctly,
            apply_chart_specific_positioning_correctly_with_fallback,
            fill_template_with_clean_positioning,
        )

        return {
            "apply_chart_specific_positioning_correctly": apply_chart_specific_positioning_correctly,
            "fill_template_with_clean_positioning": fill_template_with_clean_positioning,
            "apply_chart_specific_positioning_correctly_with_fallback": apply_chart_specific_positioning_correctly_with_fallback,
        }
    except ImportError as e:
        logger.warning(f"Could not import clean positioning functions: {e}")
        return None


# Add these functions to the module namespace dynamically
def _dynamic_import():
    """Import functions dynamically to avoid circular imports."""
    functions = get_clean_positioning_functions()
    if functions:
        globals().update(functions)


# Try to import functions, but don't fail if there are circular import issues
try:
    _dynamic_import()
except Exception as e:
    logger.info(f"Dynamic import skipped due to circular dependencies: {e}")


# Health check function for monitoring
def health_check() -> dict:
    """
    Perform a health check of the positioning system.

    Returns:
        Health status dictionary
    """
    try:
        status = get_positioning_status()
        feature_manager = get_feature_manager()
        api_wrapper = get_api_wrapper()

        # Check if performance is healthy
        stats = feature_manager.get_performance_stats()
        clean_error_rate = 0
        if stats.get("clean_mode_requests", 0) > 0:
            clean_error_rate = (stats.get("clean_mode_failures", 0) / stats.get("clean_mode_requests", 1)) * 100

        healthy = (
            clean_error_rate < feature_manager.flags.max_error_rate_percentage
            and stats.get("clean_avg_time", 0) < feature_manager.flags.max_execution_time_seconds
        )

        return {
            "status": "healthy" if healthy else "degraded",
            "version": __version__,
            "googleapi_available": api_wrapper._googleapi_available,
            "current_mode": feature_manager.flags.positioning_mode.value,
            "error_rate": clean_error_rate,
            "avg_execution_time": stats.get("clean_avg_time", 0),
            "total_requests": stats.get("clean_mode_requests", 0) + stats.get("legacy_mode_requests", 0),
            "issues": [],
        }

    except Exception as e:
        return {"status": "error", "version": __version__, "error": str(e), "issues": ["Health check failed"]}


# Initialize logging for the package
logger.info(f"Clean Positioning System v{__version__} initialized")

# Export all public APIs
__all__ = [
    # Core classes
    "CleanChartPositioner",
    "TemplatePlaceholderAnalyzer",
    "ChartPlaceholderMapper",
    # Main replacement functions (available via dynamic imports)
    # 'apply_chart_specific_positioning_correctly',
    # 'fill_template_with_clean_positioning',
    # 'apply_chart_specific_positioning_correctly_with_fallback',
    # Configuration functions
    "get_chart_styling_config",
    "resolve_chart_layout",
    "get_config_manager",
    # Feature flag functions
    "should_use_clean_positioning",
    "record_positioning_performance",
    "emergency_rollback",
    "get_feature_manager",
    # Convenience functions
    "get_positioning_status",
    "configure_positioning",
    "create_template_config",
    "health_check",
    # API wrappers
    "get_api_wrapper",
]
