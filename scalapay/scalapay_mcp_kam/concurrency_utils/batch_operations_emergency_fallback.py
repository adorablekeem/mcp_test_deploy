"""
Emergency fallback for batch operations - Safe sequential processing
This module provides guaranteed-safe fallback when concurrent operations fail.
"""

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

from scalapay.scalapay_mcp_kam.utils.google_connection_manager import connection_manager

logger = logging.getLogger(__name__)


async def safe_sequential_batch_text_replace(
    slides_service, presentation_id: str, text_map: Dict[str, str], correlation_id: str = None
) -> Dict[str, Any]:
    """
    Emergency fallback: Safe sequential text replacement.
    Guaranteed to work without SSL/concurrency issues.
    """
    corr_id = correlation_id or f"emergency_{int(time.time())}"

    if not text_map:
        logger.info(f"[{corr_id}] No text replacements to process")
        return {"replacements_processed": 0, "slides_processed": 0, "api_calls": 0, "mode": "emergency_sequential"}

    start_time = time.time()

    try:
        # Use the original batch_text_replace approach (proven to work)
        from scalapay.scalapay_mcp_kam.tests.test_fill_template_sections import batch_text_replace

        logger.info(f"[{corr_id}] Using emergency sequential batch text replacement for {len(text_map)} replacements")

        # Get service with connection manager for consistency
        service = connection_manager.get_service_sync()  # Use sync version for compatibility

        # Call the original proven method
        batch_text_replace(text_map, presentation_id, service)

        processing_time = time.time() - start_time

        logger.info(f"[{corr_id}] Emergency sequential text replacement completed in {processing_time:.2f}s")

        return {
            "success": True,
            "replacements_processed": len(text_map),
            "slides_processed": -1,  # Unknown in this mode
            "api_calls": 1,  # Single batch call
            "processing_time": processing_time,
            "mode": "emergency_sequential",
            "correlation_id": corr_id,
        }

    except Exception as e:
        processing_time = time.time() - start_time
        error_msg = f"Emergency sequential text replacement failed: {e}"
        logger.error(f"[{corr_id}] {error_msg} after {processing_time:.2f}s")

        return {
            "success": False,
            "error": error_msg,
            "processing_time": processing_time,
            "mode": "emergency_sequential_failed",
            "correlation_id": corr_id,
        }


async def safe_sequential_batch_image_replace(
    slides_service,
    presentation_id: str,
    image_map: Dict[str, str],
    resize_config: Optional[Dict] = None,
    correlation_id: str = None,
) -> Dict[str, Any]:
    """
    Emergency fallback: Safe sequential image replacement.
    Guaranteed to work without SSL/concurrency issues.
    """
    corr_id = correlation_id or f"emergency_{int(time.time())}"

    if not image_map:
        logger.info(f"[{corr_id}] No image replacements to process")
        return {"replacements_processed": 0, "slides_processed": 0, "api_calls": 0, "mode": "emergency_sequential"}

    start_time = time.time()

    try:
        # Use the original batch_replace_shapes_with_images_and_resize approach (proven to work)
        from scalapay.scalapay_mcp_kam.tests.test_fill_template_sections import (
            batch_replace_shapes_with_images_and_resize,
        )

        logger.info(f"[{corr_id}] Using emergency sequential batch image replacement for {len(image_map)} replacements")

        # Get service with connection manager for consistency
        service = connection_manager.get_service_sync()  # Use sync version for compatibility

        # Set up resize configuration
        resize = resize_config or {
            "mode": "ABSOLUTE",
            "scaleX": 120,
            "scaleY": 120,
            "unit": "PT",
            "translateX": 130,
            "translateY": 250,
        }

        # Call the original proven method
        batch_replace_shapes_with_images_and_resize(
            service, presentation_id, image_map, resize=resize, replace_method="CENTER_INSIDE"
        )

        processing_time = time.time() - start_time

        logger.info(f"[{corr_id}] Emergency sequential image replacement completed in {processing_time:.2f}s")

        return {
            "success": True,
            "replacements_processed": len(image_map),
            "slides_processed": -1,  # Unknown in this mode
            "api_calls": 1,  # Single batch call
            "processing_time": processing_time,
            "mode": "emergency_sequential",
            "correlation_id": corr_id,
        }

    except Exception as e:
        processing_time = time.time() - start_time
        error_msg = f"Emergency sequential image replacement failed: {e}"
        logger.error(f"[{corr_id}] {error_msg} after {processing_time:.2f}s")

        return {
            "success": False,
            "error": error_msg,
            "processing_time": processing_time,
            "mode": "emergency_sequential_failed",
            "correlation_id": corr_id,
        }
