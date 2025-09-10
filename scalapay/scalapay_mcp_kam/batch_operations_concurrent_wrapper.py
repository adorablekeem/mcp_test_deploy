"""
Safe wrapper for concurrent batch operations with automatic emergency fallback.
This module provides the primary interface that automatically handles fallbacks.
"""

import asyncio
import logging
import os
import time
from typing import Dict, List, Any, Optional

from .batch_operations_concurrent import (
    concurrent_batch_text_replace,
    EMERGENCY_DISABLE_CONCURRENCY,
    EMERGENCY_FALLBACK_ON_ERROR
)
from .batch_operations_emergency_fallback import (
    safe_sequential_batch_text_replace,
    safe_sequential_batch_image_replace
)

logger = logging.getLogger(__name__)


async def concurrent_batch_text_replace_with_fallback(
    slides_service,
    presentation_id: str,
    text_map: Dict[str, str],
    *,
    enable_concurrent: bool = None,
    correlation_id: str = None,
    **kwargs
) -> Dict[str, Any]:
    """
    Safe text replacement with automatic fallback to sequential processing.
    
    This function automatically handles:
    1. Emergency mode detection
    2. Concurrent processing with error recovery
    3. Automatic fallback on any failures
    4. Environment-based configuration
    
    Args:
        slides_service: Google Slides API service
        presentation_id: ID of the presentation to update
        text_map: Dictionary mapping {token: replacement_text}
        enable_concurrent: Override for concurrent processing (None = auto-detect)
        correlation_id: Tracking ID for this operation
        **kwargs: Additional arguments passed to concurrent function
    
    Returns:
        Dictionary with operation results and metadata
    """
    corr_id = correlation_id or f"wrapper_{int(time.time())}"
    
    # Check environment override
    if os.getenv("SCALAPAY_FORCE_SEQUENTIAL_BATCH", "").lower() in ("true", "1", "yes"):
        enable_concurrent = False
    
    # Auto-detect concurrent mode
    if enable_concurrent is None:
        enable_concurrent = not (EMERGENCY_DISABLE_CONCURRENCY or 
                               os.getenv("SCALAPAY_EMERGENCY_MODE", "").lower() in ("true", "1", "yes"))
    
    if not enable_concurrent:
        logger.info(f"[{corr_id}] Using sequential batch text replacement (concurrent disabled)")
        return await safe_sequential_batch_text_replace(
            slides_service, presentation_id, text_map, corr_id
        )
    
    # Try concurrent processing with automatic fallback
    try:
        logger.info(f"[{corr_id}] Attempting concurrent batch text replacement")
        result = await concurrent_batch_text_replace(
            slides_service, presentation_id, text_map,
            correlation_id=corr_id, **kwargs
        )
        
        # Check for partial failures that warrant fallback
        if not result.get("success", True) and EMERGENCY_FALLBACK_ON_ERROR:
            raise Exception(f"Concurrent operation reported failure: {result.get('error', 'Unknown error')}")
        
        result["processing_mode"] = "concurrent"
        return result
        
    except Exception as e:
        logger.warning(f"[{corr_id}] Concurrent processing failed, falling back to sequential: {e}")
        
        try:
            result = await safe_sequential_batch_text_replace(
                slides_service, presentation_id, text_map, f"{corr_id}_fallback"
            )
            result["processing_mode"] = "sequential_fallback"
            result["fallback_reason"] = str(e)
            return result
            
        except Exception as fallback_e:
            logger.error(f"[{corr_id}] Sequential fallback also failed: {fallback_e}")
            return {
                "success": False,
                "error": f"Both concurrent and sequential processing failed. Concurrent: {e}. Sequential: {fallback_e}",
                "processing_mode": "failed",
                "correlation_id": corr_id
            }


async def concurrent_batch_replace_shapes_with_images_and_resize_with_fallback(
    slides_service,
    presentation_id: str,
    image_map: Dict[str, str],
    *,
    enable_concurrent: bool = None,
    resize: Optional[Dict] = None,
    replace_method: str = "CENTER_INSIDE",
    correlation_id: str = None,
    **kwargs
) -> Dict[str, Any]:
    """
    Safe image replacement with automatic fallback to sequential processing.
    
    Similar to text replacement but for image shapes.
    """
    corr_id = correlation_id or f"wrapper_{int(time.time())}"
    
    # Check environment override
    if os.getenv("SCALAPAY_FORCE_SEQUENTIAL_BATCH", "").lower() in ("true", "1", "yes"):
        enable_concurrent = False
    
    # Auto-detect concurrent mode
    if enable_concurrent is None:
        enable_concurrent = not (EMERGENCY_DISABLE_CONCURRENCY or 
                               os.getenv("SCALAPAY_EMERGENCY_MODE", "").lower() in ("true", "1", "yes"))
    
    if not enable_concurrent:
        logger.info(f"[{corr_id}] Using sequential batch image replacement (concurrent disabled)")
        return await safe_sequential_batch_image_replace(
            slides_service, presentation_id, image_map, resize, corr_id
        )
    
    # For now, always use sequential for image replacement until concurrent version is stable
    logger.info(f"[{corr_id}] Using sequential batch image replacement (concurrent not yet implemented)")
    result = await safe_sequential_batch_image_replace(
        slides_service, presentation_id, image_map, resize, corr_id
    )
    result["processing_mode"] = "sequential_by_design"
    return result


# Backward compatibility exports
concurrent_batch_text_replace_safe = concurrent_batch_text_replace_with_fallback
concurrent_batch_image_replace_safe = concurrent_batch_replace_shapes_with_images_and_resize_with_fallback