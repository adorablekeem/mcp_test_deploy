"""
Drop-in replacement functions for the existing positioning system.
Maintains full backward compatibility while providing clean implementation with fallback.
"""

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional, Tuple

# Import chart sizing components
from .chart_resizer import ChartPlacement, ChartResizer
from .chart_sizing_config import get_chart_sizing_config
from .declarative_config import get_chart_styling_config, resolve_chart_layout
from .feature_flags import record_positioning_performance, should_use_clean_positioning
from .google_api_wrapper import OperationResult, get_api_wrapper

# Import legacy wrapper to avoid circular imports
from .legacy_wrapper import get_legacy_positioning_function, mock_legacy_fill_template
from .size_utils import ChartSize, calculate_size_from_config, calculate_transform_for_size_change
from .template_discovery import ChartPlaceholderMapper, TemplatePlaceholderAnalyzer

logger = logging.getLogger(__name__)


class CleanChartPositioner:
    """Clean positioning system using declarative configuration."""

    def __init__(self, presentation_id: str, correlation_id: Optional[str] = None):
        self.presentation_id = presentation_id
        self.correlation_id = correlation_id or f"clean_pos_{int(time.time())}"
        self.api_wrapper = get_api_wrapper()

        # Initialize components
        self.analyzer = None
        self.mapper = None
        self._initialized = False

    async def initialize(self) -> bool:
        """Initialize the positioning system components."""
        if self._initialized:
            return True

        try:
            # Discover template placeholders
            self.analyzer = TemplatePlaceholderAnalyzer(self.presentation_id)
            discovery_result = self.analyzer.discover_all_placeholders(self.correlation_id)

            if not discovery_result.success:
                logger.error(
                    f"[{self.correlation_id}] Failed to discover placeholders: {discovery_result.error_message}"
                )
                return False

            # Initialize mapper
            self.mapper = ChartPlaceholderMapper(self.analyzer)

            chart_count = discovery_result.details.get("chart_count", 0)
            logger.info(f"[{self.correlation_id}] Initialized clean positioning with {chart_count} chart placeholders")

            self._initialized = True
            return True

        except Exception as e:
            logger.error(f"[{self.correlation_id}] Failed to initialize clean positioning: {e}")
            return False

    async def position_charts_batch(
        self,
        image_map: Dict[str, str],  # token -> image_url (legacy format)
        slide_metadata: Dict[str, Dict[str, Any]],
        max_batch_size: int = 5,
        enable_custom_sizing: bool = True,
        config_dir: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Position multiple charts using clean batch operations.

        Args:
            image_map: Dictionary mapping tokens to image URLs
            slide_metadata: Metadata for each chart type
            max_batch_size: Maximum charts per batch operation
            enable_custom_sizing: Whether to apply custom chart sizing
            config_dir: Directory for custom sizing configurations

        Returns:
            Operation results in legacy format for compatibility
        """

        start_time = time.time()

        try:
            # Try to initialize, but don't fail if initialization fails
            # (e.g., when presentation doesn't exist yet or has no placeholders)
            initialization_success = await self.initialize()
            if not initialization_success:
                logger.warning(
                    f"[{self.correlation_id}] Clean positioning initialization failed, falling back to direct API calls"
                )

                # Fall back to direct API wrapper calls without placeholder discovery
                return await self._direct_batch_operations(image_map, slide_metadata)

            # Convert legacy format to chart data types
            chart_mappings = {}
            for token, image_url in image_map.items():
                # Extract data type from token (e.g., {{monthly_sales_chart}} -> monthly_sales)
                data_type = token.strip("{}").replace("_chart", "").replace("_graph", "")
                chart_mappings[data_type] = image_url

            # Get placeholder mappings for all chart types
            chart_types = list(chart_mappings.keys())
            placeholder_mappings = self.mapper.get_mapping_for_charts(chart_types, self.correlation_id)

            # Build image mapping for batch operation (GoogleApiSupport format)
            googleapi_image_mapping = {}
            successful_mappings = []
            failed_mappings = []

            for data_type, image_url in chart_mappings.items():
                placeholder_info = placeholder_mappings.get(data_type)

                if placeholder_info:
                    # Use placeholder text as key for GoogleApiSupport
                    googleapi_image_mapping[placeholder_info.placeholder_text] = image_url
                    successful_mappings.append(
                        {
                            "data_type": data_type,
                            "placeholder": placeholder_info.placeholder_text,
                            "page_id": placeholder_info.page_id,
                        }
                    )
                else:
                    failed_mappings.append({"data_type": data_type, "error": "No suitable placeholder found"})

            # Execute batch image replacement
            replace_result = None
            resize_result = None

            if googleapi_image_mapping:
                page_ids = list(set(mapping["page_id"] for mapping in successful_mappings))

                if enable_custom_sizing:
                    # Use custom sizing approach
                    resize_result = await self._position_charts_with_custom_sizing(
                        chart_mappings, successful_mappings, config_dir
                    )
                    replace_result = resize_result  # For compatibility
                else:
                    # Use traditional replacement approach
                    replace_result = self.api_wrapper.batch_replace_shape_with_image(
                        image_mapping=googleapi_image_mapping,
                        presentation_id=self.presentation_id,
                        pages=page_ids,
                        correlation_id=self.correlation_id,
                    )

                    if not replace_result.success:
                        raise Exception(f"Batch image replacement failed: {replace_result.error_message}")

            # Prepare results in legacy format
            execution_time = time.time() - start_time
            total_operations = len(successful_mappings)

            if replace_result:
                api_calls = replace_result.api_calls_made if hasattr(replace_result, "api_calls_made") else 1
            else:
                api_calls = 0

            processing_mode = (
                "clean_declarative_positioning_with_sizing" if enable_custom_sizing else "clean_declarative_positioning"
            )

            result = {
                "success": len(failed_mappings) == 0,
                "styles_applied": total_operations,
                "api_calls": api_calls,
                "positioning_requests": total_operations,
                "processing_mode": processing_mode,
                "correlation_id": self.correlation_id,
                "execution_time": execution_time,
                "successful_positions": successful_mappings,
                "failed_positions": failed_mappings,
                "custom_sizing_enabled": enable_custom_sizing,
            }

            logger.info(
                f"[{self.correlation_id}] Clean positioning complete: "
                f"{total_operations} charts positioned in {execution_time:.2f}s"
            )

            return result

        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"[{self.correlation_id}] Clean positioning failed: {e}")

            return {
                "success": False,
                "error": str(e),
                "styles_applied": 0,
                "correlation_id": self.correlation_id,
                "execution_time": execution_time,
                "processing_mode": "clean_declarative_positioning_failed",
                "custom_sizing_enabled": enable_custom_sizing,
            }

    async def _position_charts_with_custom_sizing(
        self,
        chart_mappings: Dict[str, str],  # data_type -> image_url
        successful_mappings: List[Dict[str, Any]],
        config_dir: Optional[str] = None,
    ) -> OperationResult:
        """
        Position charts using custom sizing configuration.

        This method combines placeholder discovery with custom sizing to place
        charts with precise dimensions while maintaining proper positioning.
        """

        try:
            # Get sizing configuration for all chart types
            chart_data_types = list(chart_mappings.keys())
            sizing_config = get_chart_sizing_config(
                data_types=chart_data_types,
                presentation_id=self.presentation_id,
                config_dir=config_dir,
                correlation_id=self.correlation_id,
            )

            # Get current placeholder information for size calculation
            presentation_info = self.api_wrapper._get_presentation_info_sync(self.presentation_id, self.correlation_id)

            if not presentation_info.success:
                raise Exception(f"Failed to get presentation info: {presentation_info.error_message}")

            # Build chart placements with custom sizing
            chart_placements = []
            placeholder_elements = {}  # Store original elements for reference

            # Index placeholder elements by page and object ID
            for slide in presentation_info.details.get("slides", []):
                for element in slide.get("pageElements", []):
                    if element.get("shape") and "text" in element["shape"]:
                        placeholder_elements[element["objectId"]] = {"element": element, "page_id": slide["objectId"]}

            for mapping in successful_mappings:
                data_type = mapping["data_type"]
                page_id = mapping["page_id"]
                image_url = chart_mappings[data_type]

                # Find placeholder element for this mapping
                placeholder_element = None
                for elem_id, elem_info in placeholder_elements.items():
                    if elem_info["page_id"] == page_id:
                        element = elem_info["element"]
                        shape = element.get("shape", {})
                        if "text" in shape:
                            # Check if this element contains our placeholder text
                            text_elements = shape["text"].get("textElements", [])
                            for text_elem in text_elements:
                                text_run = text_elem.get("textRun", {})
                                content = text_run.get("content", "")
                                if mapping["placeholder"] in content:
                                    placeholder_element = element
                                    break
                        if placeholder_element:
                            break

                if not placeholder_element:
                    logger.warning(f"[{self.correlation_id}] Could not find placeholder element for {data_type}")
                    continue

                # Calculate custom size based on configuration
                original_size = placeholder_element.get("size", {})
                chart_size = calculate_size_from_config(
                    original_size, sizing_config.get(data_type, sizing_config.get("default", {})), self.correlation_id
                )

                # Calculate position to maintain placeholder center
                original_transform = placeholder_element.get("transform", {})
                anchor_point = sizing_config.get(data_type, {}).get("anchor_point", "center")

                original_chart_size = ChartSize(
                    width_emu=original_size.get("width", {}).get("magnitude", 0),
                    height_emu=original_size.get("height", {}).get("magnitude", 0),
                )

                chart_transform = calculate_transform_for_size_change(
                    original_transform, original_chart_size, chart_size, anchor_point
                )

                # Create chart placement
                chart_placements.append(
                    ChartPlacement(
                        image_url=image_url,
                        page_id=page_id,
                        object_id=f"chart_{data_type}_{int(time.time() * 1000)}",
                        size=chart_size,
                        transform=chart_transform,
                        data_type=data_type,
                        placeholder_text=mapping["placeholder"],
                    )
                )

            # Execute chart placement with custom sizing
            if chart_placements:
                resizer = ChartResizer(self.presentation_id, self.correlation_id)
                return await resizer.place_charts_with_custom_sizing(chart_placements)
            else:
                return OperationResult(
                    success=True,
                    mode_used="no_charts_to_place",
                    execution_time=0,
                    objects_processed=0,
                    api_calls_made=0,
                    details={"message": "No valid chart placements prepared"},
                )

        except Exception as e:
            logger.error(f"[{self.correlation_id}] Custom sizing positioning failed: {e}")
            return OperationResult(
                success=False,
                error_message=str(e),
                mode_used="custom_sizing_failed",
                execution_time=0,
                objects_processed=0,
                api_calls_made=0,
            )

    async def _direct_batch_operations(
        self, image_map: Dict[str, str], slide_metadata: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Fallback method that uses direct API wrapper calls without placeholder discovery.
        Used when initialization fails or presentation doesn't exist yet.
        """

        start_time = time.time()

        try:
            logger.info(f"[{self.correlation_id}] Using direct batch operations (no placeholder discovery)")

            # Prepare image mapping for API wrapper (remove braces from tokens)
            clean_image_mapping = {}
            for token, image_url in image_map.items():
                clean_token = token.strip("{}")
                clean_image_mapping[clean_token] = image_url

            # Use API wrapper directly
            if clean_image_mapping:
                replace_result = self.api_wrapper.batch_replace_shape_with_image(
                    image_mapping=clean_image_mapping,
                    presentation_id=self.presentation_id,
                    correlation_id=self.correlation_id,
                )

                if replace_result.success:
                    successful_mappings = [
                        {"data_type": token.strip("{}").replace("_chart", "").replace("_graph", ""), "token": token}
                        for token in image_map.keys()
                    ]
                    failed_mappings = []
                else:
                    successful_mappings = []
                    failed_mappings = [
                        {"data_type": token.strip("{}"), "error": replace_result.error_message}
                        for token in image_map.keys()
                    ]

                execution_time = time.time() - start_time

                return {
                    "success": replace_result.success,
                    "styles_applied": replace_result.objects_processed,
                    "api_calls": replace_result.api_calls_made,
                    "positioning_requests": len(clean_image_mapping),
                    "processing_mode": "direct_api_fallback",
                    "correlation_id": self.correlation_id,
                    "execution_time": execution_time,
                    "successful_positions": successful_mappings,
                    "failed_positions": failed_mappings,
                    "custom_sizing_enabled": False,
                }
            else:
                execution_time = time.time() - start_time
                return {
                    "success": True,
                    "styles_applied": 0,
                    "api_calls": 0,
                    "positioning_requests": 0,
                    "processing_mode": "direct_api_fallback_empty",
                    "correlation_id": self.correlation_id,
                    "execution_time": execution_time,
                    "successful_positions": [],
                    "failed_positions": [],
                    "custom_sizing_enabled": False,
                }

        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"[{self.correlation_id}] Direct batch operations failed: {e}")

            return {
                "success": False,
                "error": str(e),
                "styles_applied": 0,
                "correlation_id": self.correlation_id,
                "execution_time": execution_time,
                "processing_mode": "direct_api_fallback_failed",
                "custom_sizing_enabled": False,
            }


# Drop-in replacement functions with fallback


async def apply_chart_specific_positioning_correctly(
    slides_service,  # Kept for compatibility
    presentation_id: str,
    image_map: Dict[str, str],
    slide_metadata: Dict[str, Dict[str, Any]],
    correlation_id: str = None,
) -> Dict[str, Any]:
    """
    Drop-in replacement for the legacy positioning function.
    Uses clean positioning with automatic fallback to legacy implementation.
    """

    correlation_id = correlation_id or f"pos_{int(time.time())}"
    start_time = time.time()

    # Determine which implementation to use
    use_clean = should_use_clean_positioning(presentation_id, correlation_id)

    if use_clean:
        logger.info(f"[{correlation_id}] Using CLEAN positioning implementation")

        try:
            # Use clean positioning system
            positioner = CleanChartPositioner(presentation_id, correlation_id)
            result = await positioner.position_charts_batch(image_map, slide_metadata)

            # Record performance
            record_positioning_performance(
                mode="clean",
                success=result["success"],
                execution_time=result.get("execution_time", 0),
                correlation_id=correlation_id,
            )

            return result

        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"[{correlation_id}] Clean positioning failed, falling back to legacy: {e}")

            # Record failure
            record_positioning_performance(
                mode="clean", success=False, execution_time=execution_time, correlation_id=correlation_id
            )

            # Fall back to legacy if clean fails
            use_clean = False

    if not use_clean:
        logger.info(f"[{correlation_id}] Using LEGACY positioning implementation")

        try:
            # Use legacy positioning system
            legacy_apply_positioning = get_legacy_positioning_function()

            if legacy_apply_positioning:
                result = await legacy_apply_positioning(
                    slides_service, presentation_id, image_map, slide_metadata, correlation_id
                )
            else:
                raise Exception("Legacy positioning function not available")

            # Record performance
            execution_time = time.time() - start_time
            record_positioning_performance(
                mode="legacy",
                success=result.get("success", False),
                execution_time=execution_time,
                correlation_id=correlation_id,
            )

            return result

        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"[{correlation_id}] Legacy positioning also failed: {e}")

            record_positioning_performance(
                mode="legacy", success=False, execution_time=execution_time, correlation_id=correlation_id
            )

            return {
                "success": False,
                "error": f"Both clean and legacy positioning failed: {str(e)}",
                "styles_applied": 0,
                "correlation_id": correlation_id,
                "processing_mode": "both_implementations_failed",
            }


async def fill_template_with_clean_positioning(
    drive,
    slides,
    results: Dict[str, Any],
    *,
    template_id: str,
    folder_id: Optional[str],
    verbose: bool = False,
    correlation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Enhanced template processing with integrated clean positioning.
    Provides better performance and cleaner code while maintaining compatibility.
    """

    correlation_id = correlation_id or f"template_{int(time.time())}"
    start_time = time.time()

    # Determine which implementation to use
    use_clean = should_use_clean_positioning(template_id, correlation_id)

    if use_clean:
        logger.info(f"[{correlation_id}] Using CLEAN template processing with integrated positioning")

        try:
            # Enhanced template processing with clean positioning integration
            result = await _process_template_clean_integrated(
                drive,
                slides,
                results,
                template_id=template_id,
                folder_id=folder_id,
                verbose=verbose,
                correlation_id=correlation_id,
            )

            execution_time = time.time() - start_time
            result["processing_time"] = execution_time
            result["clean_positioning_enabled"] = True

            record_positioning_performance(
                mode="clean",
                success=result.get("success", True),
                execution_time=execution_time,
                correlation_id=correlation_id,
            )

            return result

        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"[{correlation_id}] Clean template processing failed, falling back to legacy: {e}")

            record_positioning_performance(
                mode="clean", success=False, execution_time=execution_time, correlation_id=correlation_id
            )

            # Fall back to legacy
            use_clean = False

    if not use_clean:
        logger.info(f"[{correlation_id}] Using LEGACY template processing")

        try:
            # Try to use the real template processing function directly
            try:
                # Try the enhanced concurrent version first (most feature-complete)
                from scalapay.scalapay_mcp_kam.tools_agent_kam_concurrent import (
                    fill_template_for_all_sections_new_enhanced_with_fallback,
                )

                logger.info(f"[{correlation_id}] Using real enhanced template processing with fallback")

                # Create a minimal LLM processor for enhanced processing if needed
                try:
                    from langchain_openai import ChatOpenAI
                    llm_processor = ChatOpenAI(model="gpt-3.5-turbo")  # Use default model
                except ImportError:
                    logger.warning(f"[{correlation_id}] Could not import ChatOpenAI, using None")
                    llm_processor = None
                
                result = await fill_template_for_all_sections_new_enhanced_with_fallback(
                    drive, slides, results, template_id=template_id, folder_id=folder_id, 
                    llm_processor=llm_processor, verbose=verbose
                )

            except ImportError as e1:
                try:
                    # Fallback to the regular version
                    from scalapay.scalapay_mcp_kam.tests.test_fill_template_sections import (
                        fill_template_for_all_sections,
                    )

                    logger.info(f"[{correlation_id}] Using real basic template processing")

                    result = fill_template_for_all_sections(
                        drive, slides, results, template_id=template_id, folder_id=folder_id, verbose=verbose
                    )

                except ImportError as e2:
                    logger.warning(f"[{correlation_id}] Could not import enhanced function: {e1}")
                    logger.warning(f"[{correlation_id}] Could not import basic function: {e2}")
                    logger.warning(f"[{correlation_id}] Using mock template processing")

                    # Fallback to mock only when real function is not available
                    result = await mock_legacy_fill_template(
                        drive, slides, results, template_id=template_id, folder_id=folder_id, verbose=verbose
                    )

            execution_time = time.time() - start_time
            result["processing_time"] = execution_time
            result["clean_positioning_enabled"] = False

            record_positioning_performance(
                mode="legacy",
                success=True,  # Assume success if no exception
                execution_time=execution_time,
                correlation_id=correlation_id,
            )

            return result

        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"[{correlation_id}] Legacy template processing failed: {e}")

            record_positioning_performance(
                mode="legacy", success=False, execution_time=execution_time, correlation_id=correlation_id
            )

            return {
                "success": False,
                "error": f"Template processing failed: {str(e)}",
                "correlation_id": correlation_id,
                "processing_time": execution_time,
            }


async def _process_template_clean_integrated(
    drive,
    slides,
    results: Dict[str, Any],
    *,
    template_id: str,
    folder_id: Optional[str],
    verbose: bool = False,
    correlation_id: str,
) -> Dict[str, Any]:
    """
    Internal clean template processing with integrated positioning.
    Combines all operations for optimal performance.
    """

    api_wrapper = get_api_wrapper()

    # 1. Duplicate template
    timestamp = int(time.time())
    new_pres_id = None  # This would need to be implemented with proper service

    # For now, fall back to legacy duplication (this keeps the function working)
    # In full implementation, this would use GoogleApiSupport or existing duplication logic
    try:
        import os

        from google.oauth2 import service_account
        from googleapiclient.discovery import build
        from scalapay.scalapay_mcp_kam.tests.test_fill_template_sections import copy_file

        credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "./scalapay/scalapay_mcp_kam/credentials.json")
        credentials = service_account.Credentials.from_service_account_file(credentials_path)
        drive = build("drive", "v3", credentials=credentials)

        new_pres_id = copy_file(drive, template_id, f"KAM Report - {timestamp}")
    except Exception as e:
        logger.warning(f"[{correlation_id}] Using legacy copy_file: {e}")
        # Could implement GoogleApiSupport duplication here
        raise Exception(f"Template duplication failed: {e}")

    # 2. Prepare chart and text mappings
    chart_file_mappings = {}  # data_type -> local_file_path
    text_mappings = {}  # placeholder -> text_content

    for data_type, section_data in results.items():
        chart_path = section_data.get("chart_path")
        if chart_path:
            chart_file_mappings[data_type] = chart_path

        # Prepare text replacements
        base_slug = data_type.replace(" ", "_").lower()
        text_mappings[f"{base_slug}_title"] = section_data.get("title", data_type)
        text_mappings[f"{base_slug}_paragraph"] = section_data.get("paragraph", "")

    # 3. Concurrent image upload and processing
    upload_result = await api_wrapper.upload_and_publish_images(
        chart_mappings=chart_file_mappings, folder_id=folder_id, correlation_id=correlation_id
    )

    if not upload_result.success:
        raise Exception(f"Image upload failed: {upload_result.error_message}")

    successful_uploads = upload_result.details.get("successful_uploads", {})

    # 4. Clean positioning using uploaded images
    # Convert to legacy image_map format for positioning
    image_map = {}
    slide_metadata = {}

    for data_type, image_url in successful_uploads.items():
        # Create legacy-style token
        token = f"{{{{{data_type.replace(' ', '_')}_chart}}}}"
        image_map[token] = image_url

        # Create slide metadata entry
        slide_metadata[data_type] = results.get(data_type, {})

    # Use the API wrapper directly for batch operations instead of CleanChartPositioner
    # since the presentation was just created and may not have placeholders yet
    positioning_result = {
        "success": True,
        "api_calls": 0,
        "styles_applied": 0,
        "successful_positions": [],
        "failed_positions": [],
    }

    if image_map:
        # Use direct batch replace from API wrapper
        try:
            replace_result = api_wrapper.batch_replace_shape_with_image(
                image_mapping={k.strip("{}"): v for k, v in image_map.items()},  # Remove braces
                presentation_id=new_pres_id,
                correlation_id=correlation_id,
            )

            positioning_result = {
                "success": replace_result.success,
                "api_calls": replace_result.api_calls_made,
                "styles_applied": replace_result.objects_processed,
                "successful_positions": [{"data_type": dt} for dt in successful_uploads.keys()],
                "failed_positions": [],
            }

        except Exception as e:
            logger.warning(f"[{correlation_id}] Direct batch replace failed: {e}")
            positioning_result = {"success": False, "api_calls": 0, "styles_applied": 0, "error": str(e)}

    # 5. Text replacements
    text_result = api_wrapper.batch_text_replace(
        text_mapping=text_mappings, presentation_id=new_pres_id, correlation_id=correlation_id
    )

    # 6. Compile final results
    total_api_calls = upload_result.api_calls_made + positioning_result.get("api_calls", 0) + text_result.api_calls_made

    return {
        "presentation_id": new_pres_id,
        "sections_rendered": len(results),
        "uploaded_images": list(successful_uploads.keys()),
        "successful_positions": positioning_result.get("successful_positions", []),
        "failed_positions": positioning_result.get("failed_positions", []),
        "total_api_calls": total_api_calls,
        "upload_performance": {
            "mode": upload_result.mode_used,
            "execution_time": upload_result.execution_time,
            "objects_processed": upload_result.objects_processed,
        },
        "positioning_performance": {
            "execution_time": positioning_result.get("execution_time", 0),
            "styles_applied": positioning_result.get("styles_applied", 0),
        },
        "text_performance": {
            "mode": text_result.mode_used,
            "execution_time": text_result.execution_time,
            "objects_processed": text_result.objects_processed,
        },
        "success": True,
    }


# Convenience wrapper that maintains exact legacy API
async def apply_chart_specific_positioning_correctly_with_fallback(
    slides_service,
    presentation_id: str,
    image_map: Dict[str, str],
    slide_metadata: Dict[str, Dict[str, Any]],
    correlation_id: str = None,
) -> Dict[str, Any]:
    """
    Exact drop-in replacement with identical signature to legacy function.
    This function can be imported as a direct replacement.
    """
    return await apply_chart_specific_positioning_correctly(
        slides_service, presentation_id, image_map, slide_metadata, correlation_id
    )
