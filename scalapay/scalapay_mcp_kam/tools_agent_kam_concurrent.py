"""
Concurrent version of template processing functions for optimized slide generation.
Implements concurrent image uploads, speaker notes processing, and validation operations.
"""

import asyncio
import logging
import time
from typing import Dict, List, Any, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor
import threading

# Import existing dependencies
from scalapay.scalapay_mcp_kam.tests.test_fill_template_sections import (
    make_all_shapes_normal_weight, upload_png, copy_file, move_file, 
    batch_text_replace, build_text_and_image_maps_enhanced, 
    batch_replace_shapes_with_images_and_resize, make_file_public, 
    add_speaker_notes_to_slides
)
from scalapay.scalapay_mcp_kam.utils.concurrency_utils import (
    ConcurrencyManager, gather_with_concurrency_limit, 
    log_concurrent_operation, create_correlation_id
)
from scalapay.scalapay_mcp_kam.utils.concurrency_config import get_concurrency_config

logger = logging.getLogger(__name__)

# Removed incorrect concurrent image upload functions - 
# Images are already uploaded in Phase 3, batch operations work with URLs

@log_concurrent_operation("concurrent_speaker_notes")
async def process_speaker_notes_concurrent(
    slides_service,
    presentation_id: str,
    sections: List[Dict[str, str]],
    batch_size: int = 3,
    max_concurrent: int = 2,
    correlation_id: str = None
) -> Dict[str, Any]:
    """Process speaker notes for multiple slides concurrently."""
    corr_id = correlation_id or create_correlation_id()
    
    try:
        logger.info(f"[{corr_id}] Starting concurrent speaker notes processing for {len(sections)} sections")
        
        # Create batches for processing
        batches = [sections[i:i + batch_size] for i in range(0, len(sections), batch_size)]
        
        async def process_batch(batch: List[Dict[str, str]]) -> Dict[str, Any]:
            """Process a batch of speaker notes."""
            batch_corr_id = f"{corr_id}_batch_{len(batch)}"
            try:
                result = await add_speaker_notes_to_slides(slides_service, presentation_id, batch)
                logger.debug(f"[{batch_corr_id}] Processed batch of {len(batch)} sections")
                return result
            except Exception as e:
                logger.error(f"[{batch_corr_id}] Batch processing failed: {e}")
                return {"error": str(e), "notes_added": 0}
        
        # Process batches concurrently
        batch_tasks = [process_batch(batch) for batch in batches]
        batch_results = await gather_with_concurrency_limit(
            batch_tasks, max_concurrent=max_concurrent, return_exceptions=True
        )
        
        # Aggregate results
        total_notes_added = 0
        errors = []
        
        for result in batch_results:
            if isinstance(result, Exception):
                errors.append(str(result))
            elif isinstance(result, dict):
                if "error" in result:
                    errors.append(result["error"])
                total_notes_added += result.get("notes_added", 0)
        
        logger.info(f"[{corr_id}] Speaker notes processing complete: {total_notes_added} notes added")
        
        return {
            "notes_added": total_notes_added,
            "errors": errors,
            "batches_processed": len(batches),
            "correlation_id": corr_id
        }
        
    except Exception as e:
        logger.error(f"[{corr_id}] Concurrent speaker notes processing failed: {e}")
        return {"error": str(e), "notes_added": 0, "correlation_id": corr_id}

@log_concurrent_operation("concurrent_validation")
async def run_validation_concurrent(
    results: Dict[str, Any],
    template_id: str,
    presentation_id: str,
    uploaded_files: List[str],
    correlation_id: str = None
) -> Dict[str, Any]:
    """Run validation and verification checks concurrently."""
    corr_id = correlation_id or create_correlation_id()
    
    try:
        from scalapay.scalapay_mcp_kam.utils.slug_validation import debug_slug_mapping, verify_chart_imports
        
        logger.debug(f"[{corr_id}] Starting concurrent validation")
        
        # Create concurrent validation tasks
        async def run_slug_validation():
            """Run slug mapping validation."""
            try:
                return debug_slug_mapping(results, template_id)
            except Exception as e:
                logger.error(f"Slug validation failed: {e}")
                return {"success_rate": 0.0, "error": str(e)}
        
        async def run_chart_verification():
            """Run chart import verification."""
            try:
                return verify_chart_imports(presentation_id, uploaded_files)
            except Exception as e:
                logger.error(f"Chart verification failed: {e}")
                return {"success_rate": 0.0, "error": str(e)}
        
        # Run validations concurrently
        validation_tasks = [run_slug_validation(), run_chart_verification()]
        validation_results = await asyncio.gather(*validation_tasks, return_exceptions=True)
        
        # Process results
        slug_validation = validation_results[0] if not isinstance(validation_results[0], Exception) else {"success_rate": 0.0, "error": str(validation_results[0])}
        chart_verification = validation_results[1] if not isinstance(validation_results[1], Exception) else {"success_rate": 0.0, "error": str(validation_results[1])}
        
        logger.info(f"[{corr_id}] Validation complete: slug={slug_validation.get('success_rate', 0):.1%}, charts={chart_verification.get('success_rate', 0):.1%}")
        
        return {
            "validation_report": slug_validation,
            "chart_verification": chart_verification,
            "correlation_id": corr_id
        }
        
    except Exception as e:
        logger.error(f"[{corr_id}] Concurrent validation failed: {e}")
        return {
            "validation_report": {"success_rate": 0.0, "error": str(e)},
            "chart_verification": {"success_rate": 0.0, "error": str(e)},
            "correlation_id": corr_id
        }

# Enhanced concurrent version of the main template processing function
async def fill_template_for_all_sections_new_enhanced_concurrent(
    drive, slides,
    results: Dict[str, Any],
    *,
    template_id: str,
    folder_id: Optional[str],
    llm_processor,
    verbose: bool = False,
    enable_speaker_notes: bool = True,
    concurrency_config: Optional[Any] = None
):
    """
    Enhanced template processing with concurrent image uploads, speaker notes, and validation.
    
    Concurrency improvements:
    1. Concurrent image uploads with thread pool execution
    2. Concurrent speaker notes processing in batches
    3. Concurrent validation and verification checks
    4. Comprehensive error handling and progress tracking
    """
    correlation_id = create_correlation_id()
    logger.info(f"[{correlation_id}] Starting enhanced concurrent template processing")
    
    # Load concurrency configuration
    config = concurrency_config or get_concurrency_config()
    concurrency_manager = ConcurrencyManager(
        max_concurrent_operations=config.max_concurrent_slides_processing,
        batch_size=config.slides_batch_size,
        retry_attempts=config.retry_attempts,
        retry_delay=config.retry_delay
    )
    concurrency_manager.start_timing()
    
    if verbose:
        logger.setLevel(logging.DEBUG)
        logger.debug(f"[{correlation_id}] Concurrency config: max_concurrent={config.max_concurrent_slides_processing}, batch_size={config.slides_batch_size}")

    try:
        # Phase 1: Enhanced data mapping with LLM processing (unchanged - already optimized)
        logger.info(f"[{correlation_id}] Phase 1: Starting enhanced paragraph processing...")
        text_map, sections, notes_map = await build_text_and_image_maps_enhanced(
            results, llm_processor, template_id=template_id
        )
        logger.info(f"[{correlation_id}] Enhanced processing complete. Renderable sections: {len(sections)}")
        
        if verbose:
            logger.debug(f"[{correlation_id}] Optimized text map preview: {len(text_map)} tokens")
            logger.debug(f"[{correlation_id}] Notes map preview: {len(notes_map)} entries")

        # Phase 2: Template duplication (unchanged - single operation)
        logger.info(f"[{correlation_id}] Phase 2: Template duplication...")
        out_name = f"final_presentation_{int(time.time())}_{correlation_id[-8:]}"
        presentation_id = copy_file(drive, template_id, out_name)
        logger.info(f"[{correlation_id}] Copied template -> {presentation_id}")
        
        if folder_id:
            try:
                move_file(drive, presentation_id, folder_id)
                logger.info(f"[{correlation_id}] Moved to folder {folder_id}")
            except Exception as e:
                logger.warning(f"[{correlation_id}] Move failed (continuing): {e}")

        # Phase 3: Image processing (existing logic - keep as is)
        image_map = {}
        uploads = []
        for sec in sections:
            slug = sec["slug"]
            pretty_name = f"{slug}_{int(time.time())}.png"
            file_id = upload_png(drive, sec["chart_path"], name=pretty_name, parent_folder_id=folder_id)
            try:
                make_file_public(drive, file_id)
            except Exception as e:
                logger.warning(f"make_file_public failed ({file_id}): {e}")

            url = f"https://drive.google.com/uc?export=view&id={file_id}"
            image_map["{{" + f"{slug}_chart" + "}}"] = url
            uploads.append({
                "title": sec["title"], 
                "file_id": file_id, 
                "image_url": url,
                "slide_paragraph": sec.get("slide_paragraph", ""),
                "key_insights": sec.get("key_insights", [])
            })

        logger.info(f"[{correlation_id}] Uploaded {len(uploads)} chart images")

        # Phase 4: CONCURRENT Text replacement (slide-level parallelism)
        logger.info(f"[{correlation_id}] Phase 4: Starting concurrent text replacement for {len(text_map)} tokens...")
        make_all_shapes_normal_weight(presentation_id)
        
        # Use enhanced batch text replacement with chart-specific styling
        from scalapay.scalapay_mcp_kam.concurrency_utils.batch_operations_styled_wrapper import enhanced_batch_text_replace_with_styling
        text_result = await enhanced_batch_text_replace_with_styling(
            slides, presentation_id, text_map,
            results=results,  # Pass Alfred results for styling context
            enable_styling=config.enable_concurrent_batch_operations,  # Use same config for styling
            enable_concurrent=config.enable_concurrent_batch_operations,
            correlation_id=f"{correlation_id}_text"
        )
        logger.info(f"[{correlation_id}] Text replacement complete: {text_result.get('replacements_processed', 0)} replacements")
        
        # Phase 5: CONCURRENT Image replacement (slide-level parallelism)
        logger.info(f"[{correlation_id}] Phase 5: Starting concurrent image replacement for {len(image_map)} tokens...")
        
        # Use enhanced batch image replacement with chart-specific styling  
        from scalapay.scalapay_mcp_kam.concurrency_utils.batch_operations_styled_wrapper import enhanced_batch_image_replace_with_styling
        image_result = await enhanced_batch_image_replace_with_styling(
            slides, presentation_id, image_map,
            results=results,  # Pass Alfred results for styling context
            # No static resize parameter - let chart-specific styling handle positioning
            replace_method="CENTER_INSIDE",
            enable_styling=config.enable_concurrent_batch_operations,  # Use same config for styling
            enable_concurrent=config.enable_concurrent_batch_operations,
            correlation_id=f"{correlation_id}_image"
        )
        logger.info(f"[{correlation_id}] Image replacement complete: {image_result.get('replacements_processed', 0)} replacements")

        # Phase 6: CONCURRENT Speaker notes integration
        notes_result = {"notes_added": 0, "errors": []}
        if enable_speaker_notes:
            logger.info(f"[{correlation_id}] Phase 6: Starting concurrent speaker notes processing...")
            notes_result = await process_speaker_notes_concurrent(
                slides, presentation_id, sections,
                batch_size=config.slides_batch_size,
                max_concurrent=config.max_concurrent_slides_processing // 2,  # Use half for speaker notes
                correlation_id=f"{correlation_id}_notes"
            )
            logger.info(f"[{correlation_id}] Speaker notes complete: {notes_result.get('notes_added', 0)} added")

        # Phase 7: CONCURRENT Validation and verification
        logger.info(f"[{correlation_id}] Phase 7: Running concurrent validation...")
        expected_chart_files = [upload["file_id"] for upload in uploads]
        validation_results = await run_validation_concurrent(
            results, template_id, presentation_id, expected_chart_files,
            correlation_id=f"{correlation_id}_validation"
        )
        
        logger.info(f"[{correlation_id}] Validation complete: slug={validation_results['validation_report'].get('success_rate', 0):.1%}, charts={validation_results['chart_verification'].get('success_rate', 0):.1%}")

        # Update metrics and log performance
        concurrency_manager.metrics.concurrent_operations_count = len(sections) + 2  # notes + validation operations
        concurrency_manager.end_timing()
        concurrency_manager.log_metrics()

        # Phase 8: Enhanced response assembly
        response = {
            "presentation_id": presentation_id,
            "sections_rendered": len(sections),
            "uploaded_images": uploads,
            "notes_added": notes_result.get("notes_added", 0),
            "llm_processing_enabled": True,
            "speaker_notes_enabled": enable_speaker_notes,
            "validation_report": validation_results["validation_report"],
            "chart_verification": validation_results["chart_verification"],
            # Concurrency metadata
            "concurrent_processing_enabled": True,
            "concurrent_batch_operations_enabled": config.enable_concurrent_batch_operations,
            "correlation_id": correlation_id,
            "processing_time": concurrency_manager.metrics.total_processing_time,
            "concurrent_operations": concurrency_manager.metrics.concurrent_operations_count,
            "speaker_notes_errors": notes_result.get("errors", []),
            # Batch operation results with styling information
            "text_replacement_result": text_result,
            "image_replacement_result": image_result,
            "chart_styling_enabled": text_result.get("processing_mode", "").startswith("styled"),
            "total_styles_applied": text_result.get("styles_applied", 0) + image_result.get("styles_applied", 0),
            "styling_mode": {
                "text_processing_mode": text_result.get("processing_mode", "unknown"),
                "image_processing_mode": image_result.get("processing_mode", "unknown")
            }
        }
        
        logger.info(f"[{correlation_id}] Enhanced concurrent template processing complete in {concurrency_manager.metrics.total_processing_time:.2f}s")
        return response
        
    except Exception as e:
        concurrency_manager.end_timing()
        logger.error(f"[{correlation_id}] Enhanced concurrent template processing failed after {concurrency_manager.metrics.total_processing_time:.2f}s: {e}")
        raise


# Backward compatibility wrapper
async def fill_template_for_all_sections_new_enhanced_with_fallback(
    drive, slides,
    results: Dict[str, Any],
    *,
    template_id: str,
    folder_id: Optional[str],
    llm_processor,
    verbose: bool = False,
    enable_speaker_notes: bool = True,
    enable_concurrent_processing: bool = True
):
    """
    Enhanced template processing with optional concurrent processing and fallback to sequential.
    """
    import os
    
    # Quick override for testing/debugging
    if os.getenv("SCALAPAY_FORCE_SEQUENTIAL_SLIDES", "").lower() in ("true", "1", "yes"):
        logger.info("SCALAPAY_FORCE_SEQUENTIAL_SLIDES is set, using sequential processing")
        enable_concurrent_processing = False
    
    config = get_concurrency_config()
    
    if enable_concurrent_processing and config.enable_concurrent_slides_processing:
        try:
            logger.info("Using concurrent enhanced template processing")
            return await fill_template_for_all_sections_new_enhanced_concurrent(
                drive, slides, results,
                template_id=template_id,
                folder_id=folder_id,
                llm_processor=llm_processor,
                verbose=verbose,
                enable_speaker_notes=enable_speaker_notes,
                concurrency_config=config
            )
        except Exception as e:
            logger.warning(f"Concurrent processing failed, falling back to sequential: {e}")
            # Fall back to original enhanced function
            from scalapay.scalapay_mcp_kam.tools_agent_kam_local import fill_template_for_all_sections_new_enhanced
            return await fill_template_for_all_sections_new_enhanced(
                drive, slides, results,
                template_id=template_id,
                folder_id=folder_id,
                llm_processor=llm_processor,
                verbose=verbose,
                enable_speaker_notes=enable_speaker_notes
            )
    else:
        logger.info("Using sequential enhanced template processing")
        from scalapay.scalapay_mcp_kam.tools_agent_kam_local import fill_template_for_all_sections_new_enhanced
        return await fill_template_for_all_sections_new_enhanced(
            drive, slides, results,
            template_id=template_id,
            folder_id=folder_id,
            llm_processor=llm_processor,
            verbose=verbose,
            enable_speaker_notes=enable_speaker_notes
        )