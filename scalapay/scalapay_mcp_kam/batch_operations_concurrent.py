"""
Concurrent batch operations for Google Slides text and image replacement.
Implements slide-level parallelism for performance optimization while maintaining API efficiency.
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor
import time

from scalapay.scalapay_mcp_kam.utils.concurrency_utils import (
    ConcurrencyManager, gather_with_concurrency_limit, 
    log_concurrent_operation, create_correlation_id
)
from scalapay.scalapay_mcp_kam.utils.concurrency_config import get_concurrency_config

logger = logging.getLogger(__name__)

@log_concurrent_operation("concurrent_batch_text_replace")
async def concurrent_batch_text_replace(
    slides_service,
    presentation_id: str,
    text_map: Dict[str, str],
    *,
    max_concurrent_slides: int = 2,  # Reduced from 3 to 2
    batch_size: int = 3,  # Reduced from 5 to 3
    correlation_id: str = None
) -> Dict[str, Any]:
    """
    Replace text tokens across slides with concurrent slide-level processing.
    
    Instead of one big batch update, this processes slides concurrently in smaller batches
    for better performance and error isolation.
    
    Args:
        slides_service: Google Slides API service object
        presentation_id: ID of the presentation to update
        text_map: Dictionary mapping {token: replacement_text}
        max_concurrent_slides: Maximum slides to process concurrently
        batch_size: Number of text replacements per API call
        correlation_id: Unique ID for tracking this operation
    
    Returns:
        Dictionary with operation results and metrics
    """
    corr_id = correlation_id or create_correlation_id()
    
    if not text_map:
        logger.info(f"[{corr_id}] No text replacements to process")
        return {"replacements_processed": 0, "slides_processed": 0, "api_calls": 0}
    
    start_time = time.time()
    
    try:
        # Get all slides in the presentation
        logger.debug(f"[{corr_id}] Fetching presentation structure...")
        presentation = await asyncio.get_event_loop().run_in_executor(
            None, 
            lambda: slides_service.presentations().get(presentationId=presentation_id).execute()
        )
        
        slides = presentation.get("slides", [])
        logger.info(f"[{corr_id}] Processing {len(text_map)} text replacements across {len(slides)} slides")
        
        # Create concurrent slide processing tasks with staggered delays
        slide_tasks = []
        for i, slide in enumerate(slides):
            slide_id = slide["objectId"]
            
            async def process_slide_text_with_delay(slide_id=slide_id, slide_index=i):
                # Add staggered delays to prevent API overload
                delay = slide_index * 0.5  # 500ms between each slide start
                if delay > 0:
                    await asyncio.sleep(delay)
                return await process_single_slide_text_concurrent(
                    slides_service, presentation_id, slide_id, text_map, 
                    batch_size=batch_size,
                    correlation_id=f"{corr_id}_slide_{slide_index}"
                )
            
            slide_tasks.append(process_slide_text_with_delay)
        
        # Execute slide processing with concurrency limit
        logger.debug(f"[{corr_id}] Starting concurrent processing of {len(slide_tasks)} slides")
        slide_results = await gather_with_concurrency_limit(
            slide_tasks, max_concurrent=max_concurrent_slides, return_exceptions=True
        )
        
        # Aggregate results
        total_replacements = 0
        total_api_calls = 0
        successful_slides = 0
        errors = []
        
        for i, result in enumerate(slide_results):
            if isinstance(result, Exception):
                errors.append(f"Slide {i}: {str(result)}")
                continue
            
            if result.get("success", False):
                total_replacements += result.get("replacements_made", 0)
                total_api_calls += result.get("api_calls", 0)
                successful_slides += 1
            else:
                errors.append(f"Slide {i}: {result.get('error', 'Unknown error')}")
        
        processing_time = time.time() - start_time
        success_rate = successful_slides / len(slides) if slides else 1.0
        
        logger.info(f"[{corr_id}] Concurrent text replacement complete: {successful_slides}/{len(slides)} slides "
                   f"({success_rate:.1%} success rate), {total_replacements} replacements, "
                   f"{total_api_calls} API calls in {processing_time:.2f}s")
        
        if errors:
            logger.warning(f"[{corr_id}] Errors encountered: {errors[:3]}{'...' if len(errors) > 3 else ''}")
        
        return {
            "success": True,
            "replacements_processed": total_replacements,
            "slides_processed": successful_slides,
            "slides_total": len(slides),
            "api_calls": total_api_calls,
            "processing_time": processing_time,
            "success_rate": success_rate,
            "errors": errors,
            "correlation_id": corr_id
        }
        
    except Exception as e:
        processing_time = time.time() - start_time
        error_msg = f"Concurrent text replacement failed: {e}"
        logger.error(f"[{corr_id}] {error_msg} after {processing_time:.2f}s")
        return {
            "success": False,
            "error": error_msg,
            "processing_time": processing_time,
            "correlation_id": corr_id
        }

async def process_single_slide_text_concurrent(
    slides_service,
    presentation_id: str,
    slide_id: str,
    text_map: Dict[str, str],
    batch_size: int = 3,
    correlation_id: str = None,
    max_retries: int = 2
) -> Dict[str, Any]:
    """Process text replacements for a single slide with batching and retry logic."""
    corr_id = correlation_id or create_correlation_id()
    
    # Retry logic with exponential backoff
    for retry_attempt in range(max_retries + 1):
        try:
            if retry_attempt > 0:
                # Exponential backoff: 1s, 2s, 4s
                delay = 2 ** (retry_attempt - 1)
                logger.info(f"[{corr_id}] Retrying slide text processing, attempt {retry_attempt + 1} after {delay}s delay")
                await asyncio.sleep(delay)
            
            # Build requests for this specific slide
            requests = []
            for token, replacement_text in text_map.items():
                requests.append({
                    "replaceAllText": {
                        "containsText": {"text": token, "matchCase": False},
                        "replaceText": replacement_text,
                        "pageObjectIds": [slide_id]  # Limit to this specific slide
                    }
                })
            
            if not requests:
                return {"success": True, "replacements_made": 0, "api_calls": 0}
            
            # Process requests in smaller batches to respect API limits
            api_calls = 0
            total_replacements = 0
            
            # Split requests into even smaller batches for reliability
            for i in range(0, len(requests), batch_size):
                batch_requests = requests[i:i + batch_size]
                
                # Add small delay between batches within same slide
                if i > 0:
                    await asyncio.sleep(0.2)  # 200ms between batches
                
                # Execute batch update with timeout
                await asyncio.wait_for(
                    asyncio.get_event_loop().run_in_executor(
                        None,
                        lambda: slides_service.presentations().batchUpdate(
                            presentationId=presentation_id,
                            body={"requests": batch_requests}
                        ).execute()
                    ),
                    timeout=30.0  # 30 second timeout
                )
                
                api_calls += 1
                total_replacements += len(batch_requests)
                logger.debug(f"[{corr_id}] Processed batch {i//batch_size + 1} with {len(batch_requests)} replacements")
            
            return {
                "success": True,
                "replacements_made": total_replacements,
                "api_calls": api_calls,
                "correlation_id": corr_id,
                "retry_attempts": retry_attempt
            }
            
        except Exception as e:
            error_msg = str(e)
            
            # Don't retry on certain permanent errors
            if any(permanent_error in error_msg.lower() for permanent_error in [
                "invalid request", "permission denied", "not found", "quota exceeded"
            ]):
                logger.error(f"[{corr_id}] Permanent error, not retrying: {error_msg}")
                break
            
            if retry_attempt < max_retries:
                logger.warning(f"[{corr_id}] Attempt {retry_attempt + 1} failed: {error_msg}")
            else:
                logger.error(f"[{corr_id}] All {max_retries + 1} attempts failed: {error_msg}")
    
    return {
        "success": False,
        "error": error_msg,
        "correlation_id": corr_id,
        "retry_attempts": max_retries
    }

@log_concurrent_operation("concurrent_batch_image_replace")
async def concurrent_batch_replace_shapes_with_images_and_resize(
    slides_service,
    presentation_id: str,
    image_map: Dict[str, str],
    *,
    resize: Optional[Dict[str, Any]] = None,
    replace_method: str = "CENTER_INSIDE",
    max_concurrent_slides: int = 3,
    batch_size: int = 3,
    correlation_id: str = None
) -> Dict[str, Any]:
    """
    Replace shapes with images and apply transformations using concurrent slide-level processing.
    
    Processes slides concurrently for better performance while maintaining the two-phase
    approach (image replacement, then transformations).
    
    Args:
        slides_service: Google Slides API service object
        presentation_id: ID of the presentation to update
        image_map: Dictionary mapping {token: image_url}
        resize: Optional resize/transform parameters
        replace_method: Image replacement method ("CENTER_INSIDE" or "CENTER_CROP")
        max_concurrent_slides: Maximum slides to process concurrently
        batch_size: Number of operations per API call
        correlation_id: Unique ID for tracking this operation
    
    Returns:
        Dictionary with operation results and metrics
    """
    corr_id = correlation_id or create_correlation_id()
    
    if not image_map:
        logger.info(f"[{corr_id}] No image replacements to process")
        return {"replacements_processed": 0, "slides_processed": 0, "api_calls": 0}
    
    start_time = time.time()
    
    try:
        # Get all slides and find elements that need replacement
        logger.debug(f"[{corr_id}] Fetching presentation structure and element IDs...")
        
        presentation = await asyncio.get_event_loop().run_in_executor(
            None, 
            lambda: slides_service.presentations().get(presentationId=presentation_id).execute()
        )
        
        slides = presentation.get("slides", [])
        tokens = list(image_map.keys())
        
        # Find elements that match our tokens across all slides
        token_to_ids = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: find_element_ids_for_tokens_sync(slides_service, presentation_id, tokens)
        )
        
        logger.info(f"[{corr_id}] Processing {len(image_map)} image replacements across {len(slides)} slides")
        
        # Phase 1: Concurrent image replacement
        image_replacement_results = await process_image_replacements_concurrent(
            slides_service, presentation_id, slides, image_map, token_to_ids,
            replace_method=replace_method,
            max_concurrent_slides=max_concurrent_slides,
            batch_size=batch_size,
            correlation_id=f"{corr_id}_images"
        )
        
        # Phase 2: Concurrent transformations (if resize is specified)
        transformation_results = {"success": True, "transformations_applied": 0, "api_calls": 0}
        if resize and image_replacement_results.get("success", False):
            transformation_results = await process_transformations_concurrent(
                slides_service, presentation_id, slides, token_to_ids, resize,
                max_concurrent_slides=max_concurrent_slides,
                batch_size=batch_size,
                correlation_id=f"{corr_id}_transforms"
            )
        
        processing_time = time.time() - start_time
        
        # Aggregate results
        total_api_calls = image_replacement_results.get("api_calls", 0) + transformation_results.get("api_calls", 0)
        success = image_replacement_results.get("success", False) and transformation_results.get("success", False)
        
        logger.info(f"[{corr_id}] Concurrent image replacement complete: "
                   f"{image_replacement_results.get('replacements_processed', 0)} images replaced, "
                   f"{transformation_results.get('transformations_applied', 0)} transformations applied, "
                   f"{total_api_calls} API calls in {processing_time:.2f}s")
        
        return {
            "success": success,
            "replacements_processed": image_replacement_results.get("replacements_processed", 0),
            "transformations_applied": transformation_results.get("transformations_applied", 0),
            "slides_processed": image_replacement_results.get("slides_processed", 0),
            "slides_total": len(slides),
            "api_calls": total_api_calls,
            "processing_time": processing_time,
            "image_results": image_replacement_results,
            "transformation_results": transformation_results,
            "correlation_id": corr_id
        }
        
    except Exception as e:
        processing_time = time.time() - start_time
        error_msg = f"Concurrent image replacement failed: {e}"
        logger.error(f"[{corr_id}] {error_msg} after {processing_time:.2f}s")
        return {
            "success": False,
            "error": error_msg,
            "processing_time": processing_time,
            "correlation_id": corr_id
        }

async def process_image_replacements_concurrent(
    slides_service,
    presentation_id: str,
    slides: List[Dict[str, Any]],
    image_map: Dict[str, str],
    token_to_ids: Dict[str, List[str]],
    *,
    replace_method: str = "CENTER_INSIDE",
    max_concurrent_slides: int = 3,
    batch_size: int = 3,
    correlation_id: str = None
) -> Dict[str, Any]:
    """Process image replacements across slides concurrently."""
    corr_id = correlation_id or create_correlation_id()
    
    try:
        # Create slide-specific replacement tasks
        slide_tasks = []
        for i, slide in enumerate(slides):
            slide_id = slide["objectId"]
            
            async def process_slide_images(slide_id=slide_id, slide_index=i):
                return await process_single_slide_images_concurrent(
                    slides_service, presentation_id, slide_id, image_map, token_to_ids,
                    replace_method=replace_method,
                    batch_size=batch_size,
                    correlation_id=f"{corr_id}_slide_{slide_index}"
                )
            
            slide_tasks.append(process_slide_images)
        
        # Execute with concurrency limit
        slide_results = await gather_with_concurrency_limit(
            slide_tasks, max_concurrent=max_concurrent_slides, return_exceptions=True
        )
        
        # Aggregate results
        total_replacements = 0
        total_api_calls = 0
        successful_slides = 0
        errors = []
        
        for i, result in enumerate(slide_results):
            if isinstance(result, Exception):
                errors.append(f"Slide {i}: {str(result)}")
                continue
            
            if result.get("success", False):
                total_replacements += result.get("replacements_made", 0)
                total_api_calls += result.get("api_calls", 0)
                successful_slides += 1
            else:
                errors.append(f"Slide {i}: {result.get('error', 'Unknown error')}")
        
        success_rate = successful_slides / len(slides) if slides else 1.0
        
        logger.info(f"[{corr_id}] Image replacement complete: {successful_slides}/{len(slides)} slides "
                   f"({success_rate:.1%} success rate), {total_replacements} replacements")
        
        return {
            "success": success_rate > 0.5,  # Require >50% success rate
            "replacements_processed": total_replacements,
            "slides_processed": successful_slides,
            "api_calls": total_api_calls,
            "success_rate": success_rate,
            "errors": errors,
            "correlation_id": corr_id
        }
        
    except Exception as e:
        logger.error(f"[{corr_id}] Image replacement processing failed: {e}")
        return {"success": False, "error": str(e), "correlation_id": corr_id}

async def process_single_slide_images_concurrent(
    slides_service,
    presentation_id: str,
    slide_id: str,
    image_map: Dict[str, str],
    token_to_ids: Dict[str, List[str]],
    *,
    replace_method: str = "CENTER_INSIDE",
    batch_size: int = 3,
    correlation_id: str = None
) -> Dict[str, Any]:
    """Process image replacements for a single slide."""
    corr_id = correlation_id or create_correlation_id()
    
    try:
        # Build replacement requests for elements on this slide
        requests = []
        for token, url in image_map.items():
            # Only process if this token has elements on this slide
            element_ids = token_to_ids.get(token, [])
            slide_element_ids = [eid for eid in element_ids if eid.startswith(slide_id)]
            
            if slide_element_ids:
                requests.append({
                    "replaceAllShapesWithImage": {
                        "containsText": {"text": token, "matchCase": False},
                        "imageUrl": url,
                        "replaceMethod": replace_method,
                        "pageObjectIds": [slide_id]  # Limit to this slide
                    }
                })
        
        if not requests:
            return {"success": True, "replacements_made": 0, "api_calls": 0}
        
        # Process in batches
        api_calls = 0
        total_replacements = 0
        
        for i in range(0, len(requests), batch_size):
            batch_requests = requests[i:i + batch_size]
            
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: slides_service.presentations().batchUpdate(
                    presentationId=presentation_id,
                    body={"requests": batch_requests}
                ).execute()
            )
            
            api_calls += 1
            total_replacements += len(batch_requests)
        
        return {
            "success": True,
            "replacements_made": total_replacements,
            "api_calls": api_calls,
            "correlation_id": corr_id
        }
        
    except Exception as e:
        logger.error(f"[{corr_id}] Failed to process slide images: {e}")
        return {"success": False, "error": str(e), "correlation_id": corr_id}

async def process_transformations_concurrent(
    slides_service,
    presentation_id: str,
    slides: List[Dict[str, Any]],
    token_to_ids: Dict[str, List[str]],
    resize: Dict[str, Any],
    *,
    max_concurrent_slides: int = 3,
    batch_size: int = 5,
    correlation_id: str = None
) -> Dict[str, Any]:
    """Apply transformations across slides concurrently."""
    corr_id = correlation_id or create_correlation_id()
    
    try:
        # Parse resize parameters
        mode = (resize.get("mode") or "RELATIVE").upper()
        unit = resize.get("unit", "EMU")
        
        # Build transform matrix
        transform_params = {}
        for param in ["scaleX", "scaleY", "translateX", "translateY", "shearX", "shearY"]:
            value = resize.get(param)
            if value is not None:
                transform_params[param] = value
        
        if not transform_params:
            logger.info(f"[{corr_id}] No transformation parameters specified")
            return {"success": True, "transformations_applied": 0, "api_calls": 0}
        
        # Create slide-specific transformation tasks
        slide_tasks = []
        for i, slide in enumerate(slides):
            slide_id = slide["objectId"]
            
            async def process_slide_transforms(slide_id=slide_id, slide_index=i):
                return await process_single_slide_transforms_concurrent(
                    slides_service, presentation_id, slide_id, token_to_ids,
                    mode=mode, unit=unit, transform_params=transform_params,
                    batch_size=batch_size,
                    correlation_id=f"{corr_id}_slide_{slide_index}"
                )
            
            slide_tasks.append(process_slide_transforms)
        
        # Execute with concurrency limit
        slide_results = await gather_with_concurrency_limit(
            slide_tasks, max_concurrent=max_concurrent_slides, return_exceptions=True
        )
        
        # Aggregate results
        total_transformations = 0
        total_api_calls = 0
        successful_slides = 0
        errors = []
        
        for i, result in enumerate(slide_results):
            if isinstance(result, Exception):
                errors.append(f"Slide {i}: {str(result)}")
                continue
            
            if result.get("success", False):
                total_transformations += result.get("transformations_applied", 0)
                total_api_calls += result.get("api_calls", 0)
                successful_slides += 1
            else:
                errors.append(f"Slide {i}: {result.get('error', 'Unknown error')}")
        
        success_rate = successful_slides / len(slides) if slides else 1.0
        
        logger.info(f"[{corr_id}] Transformations complete: {successful_slides}/{len(slides)} slides "
                   f"({success_rate:.1%} success rate), {total_transformations} transformations")
        
        return {
            "success": success_rate > 0.5,  # Require >50% success rate
            "transformations_applied": total_transformations,
            "slides_processed": successful_slides,
            "api_calls": total_api_calls,
            "success_rate": success_rate,
            "errors": errors,
            "correlation_id": corr_id
        }
        
    except Exception as e:
        logger.error(f"[{corr_id}] Transformation processing failed: {e}")
        return {"success": False, "error": str(e), "correlation_id": corr_id}

async def process_single_slide_transforms_concurrent(
    slides_service,
    presentation_id: str,
    slide_id: str,
    token_to_ids: Dict[str, List[str]],
    *,
    mode: str,
    unit: str,
    transform_params: Dict[str, float],
    batch_size: int = 5,
    correlation_id: str = None
) -> Dict[str, Any]:
    """Apply transformations to elements on a single slide."""
    corr_id = correlation_id or create_correlation_id()
    
    try:
        # Find all elements on this slide that need transformation
        slide_element_ids = []
        for token, element_ids in token_to_ids.items():
            slide_element_ids.extend([eid for eid in element_ids if eid.startswith(slide_id)])
        
        if not slide_element_ids:
            return {"success": True, "transformations_applied": 0, "api_calls": 0}
        
        # Build transformation requests
        requests = []
        for element_id in slide_element_ids:
            transform_request = {
                "updatePageElementTransform": {
                    "objectId": element_id,
                    "transform": build_transform_matrix(transform_params, mode, unit),
                    "applyMode": mode
                }
            }
            requests.append(transform_request)
        
        # Process in batches
        api_calls = 0
        total_transformations = 0
        
        for i in range(0, len(requests), batch_size):
            batch_requests = requests[i:i + batch_size]
            
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: slides_service.presentations().batchUpdate(
                    presentationId=presentation_id,
                    body={"requests": batch_requests}
                ).execute()
            )
            
            api_calls += 1
            total_transformations += len(batch_requests)
        
        return {
            "success": True,
            "transformations_applied": total_transformations,
            "api_calls": api_calls,
            "correlation_id": corr_id
        }
        
    except Exception as e:
        logger.error(f"[{corr_id}] Failed to process slide transformations: {e}")
        return {"success": False, "error": str(e), "correlation_id": corr_id}

def find_element_ids_for_tokens_sync(slides_service, presentation_id: str, tokens: List[str]) -> Dict[str, List[str]]:
    """Synchronous version of element ID finding for use in thread executor."""
    pres = slides_service.presentations().get(presentationId=presentation_id).execute()
    token_ids = {t: [] for t in tokens}
    
    for slide in pres.get("slides", []):
        slide_id = slide["objectId"] 
        for pe in slide.get("pageElements", []):
            shape = pe.get("shape")
            if not shape:
                continue
            
            text_content = []
            text_elem = shape.get("text")
            if text_elem:
                for text_run in text_elem.get("textElements", []):
                    if "textRun" in text_run:
                        text_content.append(text_run["textRun"].get("content", ""))
            
            full_text = "".join(text_content).lower()
            
            for token in tokens:
                if token.lower() in full_text:
                    element_id = f"{slide_id}:{pe['objectId']}"
                    token_ids[token].append(element_id)
    
    return token_ids

def build_transform_matrix(transform_params: Dict[str, float], mode: str, unit: str) -> Dict[str, Any]:
    """Build Google Slides transform matrix from parameters."""
    transform = {
        "unit": unit
    }
    
    # Add transform parameters that are specified
    for param, value in transform_params.items():
        transform[param] = value
    
    return transform

# Backward compatibility wrappers with fallback
async def concurrent_batch_text_replace_with_fallback(
    slides_service,
    presentation_id: str,
    text_map: Dict[str, str],
    enable_concurrent: bool = True
) -> Dict[str, Any]:
    """Text replacement with automatic fallback to sequential processing."""
    config = get_concurrency_config()
    
    if enable_concurrent and hasattr(config, 'enable_concurrent_batch_operations') and config.enable_concurrent_batch_operations:
        try:
            return await concurrent_batch_text_replace(
                slides_service, presentation_id, text_map,
                max_concurrent_slides=getattr(config, 'max_concurrent_slides', 3)
            )
        except Exception as e:
            logger.warning(f"Concurrent text replacement failed, falling back to sequential: {e}")
            # Fallback to original implementation
            from scalapay.scalapay_mcp_kam.tests.test_fill_template_sections import batch_text_replace
            batch_text_replace(slides_service, presentation_id, text_map)
            return {"success": True, "fallback_used": True, "replacements_processed": len(text_map)}
    else:
        # Use sequential processing
        from scalapay.scalapay_mcp_kam.tests.test_fill_template_sections import batch_text_replace
        batch_text_replace(slides_service, presentation_id, text_map)
        return {"success": True, "sequential_used": True, "replacements_processed": len(text_map)}

async def concurrent_batch_replace_shapes_with_images_and_resize_with_fallback(
    slides_service,
    presentation_id: str,
    image_map: Dict[str, str],
    *,
    resize: Optional[Dict[str, Any]] = None,
    replace_method: str = "CENTER_INSIDE",
    enable_concurrent: bool = True
) -> Dict[str, Any]:
    """Image replacement with automatic fallback to sequential processing."""
    config = get_concurrency_config()
    
    if enable_concurrent and hasattr(config, 'enable_concurrent_batch_operations') and config.enable_concurrent_batch_operations:
        try:
            return await concurrent_batch_replace_shapes_with_images_and_resize(
                slides_service, presentation_id, image_map,
                resize=resize, replace_method=replace_method,
                max_concurrent_slides=getattr(config, 'max_concurrent_slides', 3)
            )
        except Exception as e:
            logger.warning(f"Concurrent image replacement failed, falling back to sequential: {e}")
            # Fallback to original implementation
            from scalapay.scalapay_mcp_kam.tests.test_fill_template_sections import batch_replace_shapes_with_images_and_resize
            batch_replace_shapes_with_images_and_resize(
                slides_service, presentation_id, image_map,
                resize=resize, replace_method=replace_method
            )
            return {"success": True, "fallback_used": True, "replacements_processed": len(image_map)}
    else:
        # Use sequential processing
        from scalapay.scalapay_mcp_kam.tests.test_fill_template_sections import batch_replace_shapes_with_images_and_resize
        batch_replace_shapes_with_images_and_resize(
            slides_service, presentation_id, image_map,
            resize=resize, replace_method=replace_method
        )
        return {"success": True, "sequential_used": True, "replacements_processed": len(image_map)}