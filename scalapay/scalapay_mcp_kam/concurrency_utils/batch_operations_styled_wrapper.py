"""
Styled batch operations wrapper that integrates with the existing template processing system.
Provides a drop-in replacement for the standard batch operations with chart-specific styling.
"""

import asyncio
import logging
import os
import time
from typing import Any, Dict, List, Optional

from .batch_operations_concurrent_wrapper import (
    concurrent_batch_replace_shapes_with_images_and_resize_with_fallback,
    concurrent_batch_text_replace_with_fallback,
)
from .batch_operations_with_styling import (
    build_slide_metadata_from_results,
    styled_batch_image_replace,
    styled_batch_operations_with_fallback,
    styled_batch_text_replace,
)

logger = logging.getLogger(__name__)


async def enhanced_batch_text_replace_with_styling(
    slides_service,
    presentation_id: str,
    text_map: Dict[str, str],
    *,
    results: Optional[Dict[str, Any]] = None,
    enable_styling: bool = True,
    enable_concurrent: bool = None,
    correlation_id: str = None,
    **kwargs,
) -> Dict[str, Any]:
    """
    Enhanced text replacement with optional chart-specific styling.

    This function automatically chooses between:
    1. Styled batch operations (when styling data is available)
    2. Standard concurrent operations (fallback)
    3. Emergency sequential operations (last resort)

    Args:
        slides_service: Google Slides API service
        presentation_id: ID of the presentation to update
        text_map: Dictionary mapping {token: replacement_text}
        results: Alfred results for styling context (optional)
        enable_styling: Whether to apply chart-specific styling
        enable_concurrent: Whether to enable concurrent processing
        correlation_id: Tracking ID for this operation
        **kwargs: Additional arguments passed to batch operations

    Returns:
        Dictionary with operation results and styling information
    """
    corr_id = correlation_id or f"enhanced_text_{int(time.time())}"

    # Check environment overrides
    if os.getenv("SCALAPAY_DISABLE_CHART_STYLING", "").lower() in ("true", "1", "yes"):
        enable_styling = False

    # Debug: Log the inputs to understand what's happening
    logger.info(f"[{corr_id}] Enhanced text replacement called with:")
    logger.info(f"   enable_styling={enable_styling}")
    logger.info(f"   results provided={results is not None}")
    logger.info(f"   text_map size={len(text_map) if text_map else 0}")

    if results:
        logger.info(f"   results keys: {list(results.keys())}")
        for key, entry in results.items():
            if isinstance(entry, dict):
                entry_keys = list(entry.keys())
                logger.info(f"   '{key}' has keys: {entry_keys}")

    # Use styled operations if styling is enabled and we have context data
    if (
        enable_styling
        and results
        and any(
            isinstance(entry, dict) and any(key in entry for key in ["slides_struct", "alfred_raw", "paragraph"])
            for entry in results.values()
        )
    ):
        logger.info(f"[{corr_id}] Using styled batch text replacement")

        try:
            # Build slide metadata for styling
            slide_metadata = build_slide_metadata_from_results(results)
            logger.info(
                f"[{corr_id}] Built slide metadata for {len(slide_metadata)} entries: {list(slide_metadata.keys())}"
            )

            result = await styled_batch_text_replace(
                slides_service, presentation_id, text_map, slide_metadata=slide_metadata, correlation_id=corr_id
            )

            result["processing_mode"] = "styled_batch"
            logger.info(f"[{corr_id}] Styled text replacement completed: {result.get('success', False)}")
            return result

        except Exception as e:
            logger.error(f"[{corr_id}] Styled text replacement failed, falling back to standard: {e}")
            import traceback

            logger.error(f"[{corr_id}] Traceback: {traceback.format_exc()}")
            # Fall through to standard operations

    # Fall back to standard concurrent operations
    logger.info(f"[{corr_id}] Using standard batch text replacement")
    logger.info(f"[{corr_id}] Fallback reason: enable_styling={enable_styling}, results={results is not None}")

    result = await concurrent_batch_text_replace_with_fallback(
        slides_service,
        presentation_id,
        text_map,
        enable_concurrent=enable_concurrent,
        correlation_id=f"{corr_id}_standard",
        **kwargs,
    )

    logger.info(f"[{corr_id}] Standard text replacement result: {result.get('success', False)}")
    result["processing_mode"] = result.get("processing_mode", "standard") + "_no_styling"
    return result


async def enhanced_batch_image_replace_with_styling(
    slides_service,
    presentation_id: str,
    image_map: Dict[str, str],
    *,
    results: Optional[Dict[str, Any]] = None,
    resize: Optional[Dict] = None,
    replace_method: str = "CENTER_INSIDE",
    enable_styling: bool = True,
    enable_concurrent: bool = None,
    correlation_id: str = None,
    **kwargs,
) -> Dict[str, Any]:
    """
    Enhanced image replacement with optional chart-specific styling.

    Args:
        slides_service: Google Slides API service
        presentation_id: ID of the presentation to update
        image_map: Dictionary mapping {token: image_url}
        results: Alfred results for styling context (optional)
        resize: Default resize configuration (used as fallback)
        replace_method: Image replacement method
        enable_styling: Whether to apply chart-specific styling
        enable_concurrent: Whether to enable concurrent processing
        correlation_id: Tracking ID for this operation
        **kwargs: Additional arguments passed to batch operations

    Returns:
        Dictionary with operation results and styling information
    """
    corr_id = correlation_id or f"enhanced_image_{int(time.time())}"

    # Check environment overrides
    if os.getenv("SCALAPAY_DISABLE_CHART_STYLING", "").lower() in ("true", "1", "yes"):
        enable_styling = False

    # Debug: Log the inputs to understand what's happening
    logger.info(f"[{corr_id}] Enhanced image replacement called with:")
    logger.info(f"   enable_styling={enable_styling}")
    logger.info(f"   results provided={results is not None}")
    logger.info(f"   image_map size={len(image_map) if image_map else 0}")

    if results:
        logger.info(f"   results keys: {list(results.keys())}")

    # Use styled operations if styling is enabled and we have context data
    if (
        enable_styling
        and results
        and any(
            isinstance(entry, dict) and any(key in entry for key in ["slides_struct", "alfred_raw", "paragraph"])
            for entry in results.values()
        )
    ):
        logger.info(f"[{corr_id}] Using styled batch image replacement")

        try:
            # Build slide metadata for styling
            slide_metadata = build_slide_metadata_from_results(results)
            logger.info(
                f"[{corr_id}] Built slide metadata for {len(slide_metadata)} entries: {list(slide_metadata.keys())}"
            )

            result = await styled_batch_image_replace(
                slides_service, presentation_id, image_map, slide_metadata=slide_metadata, correlation_id=corr_id
            )

            result["processing_mode"] = "styled_batch"
            logger.info(f"[{corr_id}] Styled image replacement completed: {result.get('success', False)}")
            return result

        except Exception as e:
            logger.error(f"[{corr_id}] Styled image replacement failed, falling back to standard: {e}")
            import traceback

            logger.error(f"[{corr_id}] Traceback: {traceback.format_exc()}")
            # Fall through to standard operations

    # Fall back to standard concurrent operations
    logger.info(f"[{corr_id}] Using standard batch image replacement")
    result = await concurrent_batch_replace_shapes_with_images_and_resize_with_fallback(
        slides_service,
        presentation_id,
        image_map,
        resize=resize,
        replace_method=replace_method,
        enable_concurrent=enable_concurrent,
        correlation_id=f"{corr_id}_standard",
        **kwargs,
    )

    result["processing_mode"] = result.get("processing_mode", "standard") + "_no_styling"
    return result


# Configuration function to enable/disable styling features
def configure_chart_styling(
    enable_styling: bool = True,
    enable_concurrent_with_styling: bool = True,
    styling_fallback_mode: str = "standard",  # "standard", "emergency", "disabled"
) -> Dict[str, Any]:
    """
    Configure chart styling behavior globally.

    Args:
        enable_styling: Whether to enable chart-specific styling
        enable_concurrent_with_styling: Whether to allow concurrency with styling
        styling_fallback_mode: What to do when styling fails

    Returns:
        Dictionary with current configuration
    """
    config = {
        "enable_styling": enable_styling,
        "enable_concurrent_with_styling": enable_concurrent_with_styling,
        "styling_fallback_mode": styling_fallback_mode,
        "environment_overrides": {
            "SCALAPAY_DISABLE_CHART_STYLING": os.getenv("SCALAPAY_DISABLE_CHART_STYLING", "false"),
            "SCALAPAY_EMERGENCY_MODE": os.getenv("SCALAPAY_EMERGENCY_MODE", "false"),
            "SCALAPAY_FORCE_SEQUENTIAL_BATCH": os.getenv("SCALAPAY_FORCE_SEQUENTIAL_BATCH", "false"),
        },
    }

    logger.info(f"Chart styling configuration: {config}")
    return config


# Convenience function for complete styled batch operations
async def complete_styled_batch_operations(
    slides_service,
    presentation_id: str,
    text_map: Dict[str, str],
    image_map: Dict[str, str],
    results: Dict[str, Any],
    *,
    enable_styling: bool = True,
    correlation_id: str = None,
) -> Dict[str, Any]:
    """
    Perform complete styled batch operations (text + images) in one call.

    Args:
        slides_service: Google Slides API service
        presentation_id: ID of the presentation to update
        text_map: Dictionary mapping {token: replacement_text}
        image_map: Dictionary mapping {token: image_url}
        results: Alfred results for styling context
        enable_styling: Whether to apply chart-specific styling
        correlation_id: Tracking ID for this operation

    Returns:
        Dictionary with combined operation results
    """
    corr_id = correlation_id or f"complete_styled_{int(time.time())}"

    if enable_styling and results:
        logger.info(f"[{corr_id}] Performing complete styled batch operations")
        return await styled_batch_operations_with_fallback(
            slides_service, presentation_id, text_map, image_map, results, corr_id
        )
    else:
        logger.info(f"[{corr_id}] Performing standard batch operations (styling disabled)")

        # Run standard operations sequentially
        text_result = await enhanced_batch_text_replace_with_styling(
            slides_service,
            presentation_id,
            text_map,
            results=results,
            enable_styling=False,
            correlation_id=f"{corr_id}_text",
        )

        image_result = await enhanced_batch_image_replace_with_styling(
            slides_service,
            presentation_id,
            image_map,
            results=results,
            enable_styling=False,
            correlation_id=f"{corr_id}_image",
        )

        return {
            "success": text_result.get("success", False) and image_result.get("success", False),
            "text_replacement": text_result,
            "image_replacement": image_result,
            "total_styles_applied": 0,
            "processing_mode": "standard_complete",
            "correlation_id": corr_id,
        }


# Backward compatibility aliases
styled_batch_text_replace_with_fallback = enhanced_batch_text_replace_with_styling
styled_batch_image_replace_with_fallback = enhanced_batch_image_replace_with_styling
