"""
Enhanced batch operations with chart-specific styling support.
Applies different positioning, sizing, and formatting based on chart type and content.
"""

import asyncio
import logging
import re
from typing import Dict, List, Any, Optional, Tuple
import time
import json

from .chart_config.chart_styling_config import (
    get_image_style_for_slide, get_text_style_for_slide, 
    select_style_config, detect_chart_type_from_data_type, ChartType
)
from .utils.google_connection_manager import connection_manager, presentation_locks
from .batch_operations_emergency_fallback import (
    safe_sequential_batch_text_replace, safe_sequential_batch_image_replace
)

logger = logging.getLogger(__name__)


async def styled_batch_text_replace(
    slides_service,
    presentation_id: str,
    text_map: Dict[str, str],
    slide_metadata: Optional[Dict[str, Dict[str, Any]]] = None,
    correlation_id: str = None
) -> Dict[str, Any]:
    """
    Replace text with chart-specific styling applied.
    
    Args:
        slides_service: Google Slides API service
        presentation_id: ID of the presentation to update
        text_map: Dictionary mapping {token: replacement_text}
        slide_metadata: Dictionary with slide information {slide_id: {data_type, paragraph, chart_type}}
        correlation_id: Tracking ID for this operation
    
    Returns:
        Dictionary with operation results and styling information
    """
    corr_id = correlation_id or f"styled_text_{int(time.time())}"
    
    if not text_map:
        logger.info(f"[{corr_id}] No text replacements to process")
        return {"replacements_processed": 0, "slides_processed": 0, "api_calls": 0, "styles_applied": 0}
    
    start_time = time.time()
    slide_metadata = slide_metadata or {}
    
    try:
        # Get presentation structure
        service = await connection_manager.get_service()
        presentation = await asyncio.get_event_loop().run_in_executor(
            None, 
            lambda: service.presentations().get(presentationId=presentation_id).execute()
        )
        
        slides = presentation.get("slides", [])
        logger.info(f"[{corr_id}] Processing styled text replacement across {len(slides)} slides")
        
        # Use presentation lock to prevent conflicts
        async with await presentation_locks.acquire_lock(presentation_id):
            # Build styled requests using token-based matching instead of slide-based
            requests = []
            styles_applied = 0
            
            # Use slug mapper for accurate token matching
            from .utils.slug_validation import SlugMapper
            slug_mapper = SlugMapper("1hDkICKx4D3jHdxky_3_1iJcPFVQFxTkvlH7mVSFCx_o")
            
            # Process each text token with its specific styling
            for token, replacement_text in text_map.items():
                logger.info(f"[{corr_id}] Processing text token: {token}")
                
                # Find the best matching metadata using slug-based matching
                best_match_metadata = None
                matched_data_type = None
                
                # Extract token name for matching (e.g., {{aov_title}} -> aov)
                token_match = re.match(r'\{\{([^_}]+)(?:_(?:title|paragraph|chart))?\}\}', token)
                if token_match:
                    token_slug = token_match.group(1)
                    
                    # Find matching data type from slide metadata
                    for data_type, metadata in slide_metadata.items():
                        # Generate expected slug for this data type
                        expected_slug = slug_mapper.get_slug(data_type)
                        
                        # Check for exact match or close match
                        if (token_slug == expected_slug or 
                            token_slug.replace('-', '_') == expected_slug.replace('-', '_') or
                            expected_slug.replace('-', '_') == token_slug.replace('-', '_')):
                            best_match_metadata = metadata
                            matched_data_type = data_type
                            logger.info(f"[{corr_id}] Matched token '{token}' -> data_type '{data_type}' (slug: {expected_slug})")
                            break
                
                # Determine if this is a title or content token
                element_type = "title" if any(title_indicator in token.lower() 
                                            for title_indicator in ["title", "header", "heading"]) else "content"
                
                # Get text styling configuration if we found a match
                if best_match_metadata and matched_data_type:
                    data_type = best_match_metadata.get("data_type", "")
                    paragraph = best_match_metadata.get("paragraph", "")
                    chart_type = best_match_metadata.get("chart_type")
                    
                    if isinstance(chart_type, str):
                        chart_type = ChartType(chart_type)
                    elif chart_type is None and data_type:
                        chart_type = detect_chart_type_from_data_type(data_type)
                    
                    text_style = get_text_style_for_slide(data_type, paragraph, element_type)
                    styles_applied += 1
                    
                    # Create styled text replacement request (GLOBAL, not per-slide)
                    styled_request = {
                        "replaceAllText": {
                            "containsText": {"text": token, "matchCase": False},
                            "replaceText": replacement_text
                            # NOTE: No pageObjectIds - apply globally across all slides
                        }
                    }
                    
                    # Add text formatting if available (this is complex and may need further development)
                    # For now, just do the basic replacement
                    requests.append(styled_request)
                    
                    logger.info(f"[{corr_id}] Prepared styled text replacement for '{token}' -> '{replacement_text}' (matched with {data_type})")
                else:
                    # Basic replacement without styling for unmatched tokens
                    basic_request = {
                        "replaceAllText": {
                            "containsText": {"text": token, "matchCase": False},
                            "replaceText": replacement_text
                            # Global replacement
                        }
                    }
                    requests.append(basic_request)
                    logger.info(f"[{corr_id}] Prepared basic text replacement for '{token}' -> '{replacement_text}' (no metadata match)")
            
            # Execute batch update
            if requests:
                # Process in smaller batches to respect API limits
                api_calls = 0
                for i in range(0, len(requests), 5):  # 5 requests per batch
                    batch_requests = requests[i:i + 5]
                    
                    await asyncio.wait_for(
                        asyncio.get_event_loop().run_in_executor(
                            None,
                            lambda: service.presentations().batchUpdate(
                                presentationId=presentation_id,
                                body={"requests": batch_requests}
                            ).execute()
                        ),
                        timeout=15.0
                    )
                    
                    api_calls += 1
                    
                    # Small delay between batches
                    if i + 5 < len(requests):
                        await asyncio.sleep(0.3)
        
        processing_time = time.time() - start_time
        
        logger.info(f"[{corr_id}] Styled text replacement complete: {len(text_map)} replacements, "
                   f"{styles_applied} styles applied in {processing_time:.2f}s")
        
        return {
            "success": True,
            "replacements_processed": len(text_map),
            "slides_processed": len(slides),
            "api_calls": api_calls,
            "styles_applied": styles_applied,
            "processing_time": processing_time,
            "processing_mode": "styled_batch",
            "correlation_id": corr_id
        }
        
    except Exception as e:
        processing_time = time.time() - start_time
        error_msg = f"Styled text replacement failed: {e}"
        logger.error(f"[{corr_id}] {error_msg} after {processing_time:.2f}s")
        
        # Fallback to emergency sequential processing
        logger.warning(f"[{corr_id}] Falling back to emergency sequential text replacement")
        return await safe_sequential_batch_text_replace(
            slides_service, presentation_id, text_map, f"{corr_id}_fallback"
        )


async def styled_batch_image_replace(
    slides_service,
    presentation_id: str,
    image_map: Dict[str, str],
    slide_metadata: Optional[Dict[str, Dict[str, Any]]] = None,
    correlation_id: str = None
) -> Dict[str, Any]:
    """
    Replace images with chart-specific styling and positioning.
    
    Args:
        slides_service: Google Slides API service
        presentation_id: ID of the presentation to update
        image_map: Dictionary mapping {token: image_url}
        slide_metadata: Dictionary with slide information {slide_id: {data_type, paragraph, chart_type}}
        correlation_id: Tracking ID for this operation
    
    Returns:
        Dictionary with operation results and styling information
    """
    corr_id = correlation_id or f"styled_image_{int(time.time())}"
    
    if not image_map:
        logger.info(f"[{corr_id}] No image replacements to process")
        return {"replacements_processed": 0, "slides_processed": 0, "api_calls": 0, "styles_applied": 0}
    
    start_time = time.time()
    slide_metadata = slide_metadata or {}
    
    try:
        # Get presentation structure
        service = await connection_manager.get_service()
        presentation = await asyncio.get_event_loop().run_in_executor(
            None, 
            lambda: service.presentations().get(presentationId=presentation_id).execute()
        )
        
        slides = presentation.get("slides", [])
        logger.info(f"[{corr_id}] Processing styled image replacement across {len(slides)} slides")
        
        # Use presentation lock to prevent conflicts
        async with await presentation_locks.acquire_lock(presentation_id):
            # Build styled image replacement requests
            requests = []
            styles_applied = 0
            
            # Use slug mapper for accurate token matching
            from .utils.slug_validation import SlugMapper
            slug_mapper = SlugMapper("1hDkICKx4D3jHdxky_3_1iJcPFVQFxTkvlH7mVSFCx_o")
            
            # Process each image token with its specific styling
            for token, image_url in image_map.items():
                logger.info(f"[{corr_id}] Processing image token: {token}")
                
                # Find the best matching metadata using slug-based matching
                best_match_metadata = None
                matched_data_type = None
                
                # Extract chart name from token (e.g., {{aov_chart}} -> aov)
                token_match = re.match(r'\{\{([^_}]+)(?:_chart)?\}\}', token)
                if token_match:
                    token_slug = token_match.group(1)
                    
                    # Find matching data type from slide metadata
                    for data_type, metadata in slide_metadata.items():
                        # Generate expected slug for this data type
                        expected_slug = slug_mapper.get_slug(data_type)
                        
                        # Check for exact match or close match
                        if (token_slug == expected_slug or 
                            token_slug.replace('-', '_') == expected_slug.replace('-', '_') or
                            expected_slug.replace('-', '_') == token_slug.replace('-', '_')):
                            best_match_metadata = metadata
                            matched_data_type = data_type
                            logger.info(f"[{corr_id}] Matched token '{token}' -> data_type '{data_type}' (slug: {expected_slug})")
                            break
                    
                    if not best_match_metadata:
                        logger.warning(f"[{corr_id}] No metadata match found for token: {token} (extracted slug: {token_slug})")
                
                # Get styling information based on the best match
                if best_match_metadata:
                    data_type = best_match_metadata.get("data_type", "")
                    paragraph = best_match_metadata.get("paragraph", "")
                    chart_type = best_match_metadata.get("chart_type")
                    
                    if isinstance(chart_type, str):
                        chart_type = ChartType(chart_type)
                    elif chart_type is None and data_type:
                        chart_type = detect_chart_type_from_data_type(data_type)
                    
                    # Get chart-specific styling configuration
                    image_style_config = get_image_style_for_slide(data_type, paragraph, chart_type)
                    resize_config = image_style_config.get("resize", {})
                    styles_applied += 1
                    
                    logger.info(f"[{corr_id}] Applying chart-specific style to {token} (matched with '{data_type}'): "
                               f"scale=({resize_config.get('scaleX', 120)}, {resize_config.get('scaleY', 120)}), "
                               f"pos=({resize_config.get('translateX', 130)}, {resize_config.get('translateY', 250)})")
                else:
                    # Default configurations when no match found
                    image_style_config = {"replace_method": "CENTER_INSIDE"}
                    resize_config = {
                        "mode": "ABSOLUTE",
                        "scaleX": 120,
                        "scaleY": 120,
                        "unit": "PT",
                        "translateX": 130,
                        "translateY": 250
                    }
                    logger.debug(f"[{corr_id}] No metadata match for {token}, using default styling")
                
                # Create styled image replacement request with immediate sizing
                styled_request = {
                    "replaceAllShapesWithImage": {
                        "containsText": {"text": token, "matchCase": False},
                        "imageUrl": image_url,
                        "replaceMethod": image_style_config.get("replace_method", "CENTER_INSIDE")
                        # Note: No pageObjectIds means apply globally across all slides
                    }
                }
                
                requests.append(styled_request)
                logger.info(f"[{corr_id}] Added image replacement request for {token} -> {image_url}")
                
                # Store the chart config for this token to be applied after import
                # This will be used by the positioning correction function
                if resize_config and best_match_metadata:
                    positioning_info = {
                        "token": token,
                        "data_type": matched_data_type,
                        "resize_config": resize_config,
                        "image_style_config": image_style_config,
                        "needs_positioning": True
                    }
                    
                    # Store this for the positioning phase that happens after image import
                    if not hasattr(styled_batch_image_replace, '_positioning_info'):
                        styled_batch_image_replace._positioning_info = []
                    styled_batch_image_replace._positioning_info.append(positioning_info)
            
            # Execute image replacement requests first
            api_calls = 0
            if requests:
                logger.info(f"[{corr_id}] Executing {len(requests)} image replacement requests")
                for i in range(0, len(requests), 3):  # 3 requests per batch for images
                    batch_requests = requests[i:i + 3]
                    
                    await asyncio.wait_for(
                        asyncio.get_event_loop().run_in_executor(
                            None,
                            lambda: service.presentations().batchUpdate(
                                presentationId=presentation_id,
                                body={"requests": batch_requests}
                            ).execute()
                        ),
                        timeout=20.0  # Longer timeout for image operations
                    )
                    api_calls += 1
                    
                    # Small delay between batches
                    await asyncio.sleep(1.0)
                
                # CRITICAL: Now apply chart sizing/positioning after images are imported
                if hasattr(styled_batch_image_replace, '_positioning_info') and styled_batch_image_replace._positioning_info:
                    positioning_info_list = styled_batch_image_replace._positioning_info
                    logger.info(f"[{corr_id}] Applying chart-specific sizing to {len(positioning_info_list)} imported images")
                    
                    # Clear the positioning info for next call
                    styled_batch_image_replace._positioning_info = []
                    
                    # Import the corrected positioning function
                    from .batch_operations_image_positioning_fix import apply_chart_specific_positioning_correctly
                    
                    # Apply corrected positioning using the stored chart configs
                    positioning_result = await apply_chart_specific_positioning_correctly(
                        slides_service=service,
                        presentation_id=presentation_id,
                        image_map=image_map,
                        slide_metadata=slide_metadata or {},
                        correlation_id=f"{corr_id}_positioning"
                    )
                    
                    if positioning_result.get("success"):
                        logger.info(f"[{corr_id}] Chart positioning applied successfully: "
                                  f"{positioning_result.get('styles_applied', 0)} images positioned")
                    else:
                        logger.error(f"[{corr_id}] Chart positioning failed: {positioning_result.get('error', 'Unknown error')}")
                        
                    api_calls += positioning_result.get("api_calls", 0)
                    
                    # Small delay between batches
                    if i + 3 < len(requests):
                        await asyncio.sleep(0.5)
        
        processing_time = time.time() - start_time
        
        logger.info(f"[{corr_id}] Styled image replacement complete: {len(image_map)} replacements, "
                   f"{styles_applied} styles applied in {processing_time:.2f}s")
        
        return {
            "success": True,
            "replacements_processed": len(image_map),
            "slides_processed": len(slides),
            "api_calls": api_calls,
            "styles_applied": styles_applied,
            "processing_time": processing_time,
            "processing_mode": "styled_batch",
            "correlation_id": corr_id
        }
        
    except Exception as e:
        processing_time = time.time() - start_time
        error_msg = f"Styled image replacement failed: {e}"
        logger.error(f"[{corr_id}] {error_msg} after {processing_time:.2f}s")
        
        # Fallback to emergency sequential processing
        logger.warning(f"[{corr_id}] Falling back to emergency sequential image replacement")
        default_resize = {
            "mode": "ABSOLUTE", "scaleX": 120, "scaleY": 120, 
            "unit": "PT", "translateX": 130, "translateY": 250
        }
        return await safe_sequential_batch_image_replace(
            slides_service, presentation_id, image_map, default_resize, f"{corr_id}_fallback"
        )


def _hex_to_rgb(hex_color: str) -> Dict[str, float]:
    """Convert hex color to RGB values for Google Slides API."""
    hex_color = hex_color.lstrip('#')
    if len(hex_color) != 6:
        return {"red": 0.0, "green": 0.0, "blue": 0.0}
    
    try:
        r = int(hex_color[0:2], 16) / 255.0
        g = int(hex_color[2:4], 16) / 255.0
        b = int(hex_color[4:6], 16) / 255.0
        return {"red": r, "green": g, "blue": b}
    except ValueError:
        return {"red": 0.0, "green": 0.0, "blue": 0.0}


def build_slide_metadata_from_results(results: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """
    Build slide metadata from Alfred results for styling purposes.
    
    Args:
        results: Dictionary from Alfred with chart data and structure
    
    Returns:
        Dictionary mapping data types to metadata (to be used with token-based matching)
    """
    slide_metadata = {}
    
    for data_type, entry in results.items():
        if isinstance(entry, dict):
            # Extract relevant information
            paragraph = ""
            chart_type = None
            
            # Try to get paragraph from slides_struct
            if "slides_struct" in entry:
                slides_struct = entry["slides_struct"]
                if isinstance(slides_struct, dict):
                    paragraph = slides_struct.get("paragraph", "")
            
            # Try to get paragraph from alfred_raw
            elif "alfred_raw" in entry:
                alfred_raw = entry["alfred_raw"]
                if isinstance(alfred_raw, str):
                    try:
                        parsed_raw = json.loads(alfred_raw)
                        paragraph = parsed_raw.get("paragraph", "")
                    except (json.JSONDecodeError, AttributeError):
                        pass
            
            # Auto-detect chart type
            chart_type = detect_chart_type_from_data_type(data_type)
            
            # Create slide metadata entry mapped by data_type for token-based matching
            # This will be used to match chart tokens to their styling configuration
            slide_metadata[data_type] = {
                "data_type": data_type,
                "paragraph": paragraph,
                "chart_type": chart_type.value if chart_type else None,
                "entry": entry  # Keep reference for additional processing
            }
    
    return slide_metadata


# Main wrapper functions for external use
async def styled_batch_operations_with_fallback(
    slides_service,
    presentation_id: str,
    text_map: Dict[str, str],
    image_map: Dict[str, str],
    results: Dict[str, Any],
    correlation_id: str = None
) -> Dict[str, Any]:
    """
    Complete styled batch operations with automatic fallback.
    
    Args:
        slides_service: Google Slides API service
        presentation_id: ID of the presentation to update
        text_map: Dictionary mapping {token: replacement_text}
        image_map: Dictionary mapping {token: image_url}
        results: Results from Alfred for styling context
        correlation_id: Tracking ID for this operation
    
    Returns:
        Dictionary with combined operation results
    """
    corr_id = correlation_id or f"styled_batch_{int(time.time())}"
    
    # Build slide metadata for styling
    slide_metadata = build_slide_metadata_from_results(results)
    
    logger.info(f"[{corr_id}] Starting styled batch operations with {len(slide_metadata)} styled slides")
    
    # Execute text and image operations
    text_result = await styled_batch_text_replace(
        slides_service, presentation_id, text_map, slide_metadata, f"{corr_id}_text"
    )
    
    image_result = await styled_batch_image_replace(
        slides_service, presentation_id, image_map, slide_metadata, f"{corr_id}_image"
    )
    
    # Combine results
    combined_result = {
        "success": text_result.get("success", False) and image_result.get("success", False),
        "text_replacement": text_result,
        "image_replacement": image_result,
        "total_styles_applied": text_result.get("styles_applied", 0) + image_result.get("styles_applied", 0),
        "correlation_id": corr_id
    }
    
    logger.info(f"[{corr_id}] Styled batch operations complete: "
               f"{combined_result['total_styles_applied']} total styles applied")
    
    return combined_result