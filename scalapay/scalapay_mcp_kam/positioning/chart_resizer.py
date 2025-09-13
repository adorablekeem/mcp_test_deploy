"""
Chart resizing functionality for Google Slides.
Implements the core chart resizing operations using Google Slides API.
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from .chart_sizing_config import get_chart_sizing_config
from .google_api_wrapper import OperationResult, get_api_wrapper
from .size_utils import (
    ChartSize,
    ChartSizingError,
    ChartTransform,
    calculate_size_from_config,
    calculate_transform_for_size_change,
)

logger = logging.getLogger(__name__)


@dataclass
class ChartPlacement:
    """Represents a chart to be placed with specific size and position."""

    image_url: str
    page_id: str
    object_id: str
    size: ChartSize
    transform: ChartTransform
    data_type: str
    placeholder_text: Optional[str] = None


@dataclass
class ResizeOperation:
    """Represents a chart resize operation."""

    object_id: str
    page_id: str
    new_size: ChartSize
    new_transform: ChartTransform
    data_type: str


class ChartResizer:
    """Handles chart resizing operations using Google Slides API."""

    def __init__(self, presentation_id: str, correlation_id: Optional[str] = None):
        """
        Initialize chart resizer.

        Args:
            presentation_id: Google Slides presentation ID
            correlation_id: Correlation ID for tracking operations
        """
        self.presentation_id = presentation_id
        self.correlation_id = correlation_id or f"resize_{int(time.time())}"
        self.api_wrapper = get_api_wrapper()

    async def resize_existing_charts(
        self, chart_object_ids: List[str], sizing_config: Dict[str, Dict[str, Any]], data_type_mapping: Dict[str, str]
    ) -> OperationResult:
        """
        Resize charts that have already been placed in the presentation.

        Args:
            chart_object_ids: List of chart object IDs to resize
            sizing_config: Configuration mapping data_type -> sizing_config
            data_type_mapping: Mapping object_id -> data_type

        Returns:
            OperationResult with resize operation details
        """

        start_time = time.time()

        try:
            # Get current presentation info
            presentation_info = self.api_wrapper._get_presentation_info_sync(self.presentation_id, self.correlation_id)

            if not presentation_info.success:
                raise ChartSizingError(f"Failed to get presentation info: {presentation_info.error_message}")

            # Find chart objects and prepare resize operations
            resize_operations = []

            for slide in presentation_info.details.get("slides", []):
                for page_element in slide.get("pageElements", []):
                    object_id = page_element.get("objectId")

                    if object_id in chart_object_ids:
                        data_type = data_type_mapping.get(object_id)
                        if not data_type or data_type not in sizing_config:
                            logger.warning(f"[{self.correlation_id}] No sizing config for object {object_id}, skipping")
                            continue

                        # Get current size and transform
                        current_size = page_element.get("size", {})
                        current_transform = page_element.get("transform", {})

                        # Calculate new size
                        new_size = calculate_size_from_config(
                            current_size, sizing_config[data_type], self.correlation_id
                        )

                        # Calculate new transform to maintain positioning
                        original_size = ChartSize(
                            width_emu=current_size.get("width", {}).get("magnitude", 0),
                            height_emu=current_size.get("height", {}).get("magnitude", 0),
                        )

                        anchor_point = sizing_config[data_type].get("anchor_point", "center")
                        new_transform = calculate_transform_for_size_change(
                            current_transform, original_size, new_size, anchor_point
                        )

                        resize_operations.append(
                            ResizeOperation(
                                object_id=object_id,
                                page_id=slide["objectId"],
                                new_size=new_size,
                                new_transform=new_transform,
                                data_type=data_type,
                            )
                        )

            if not resize_operations:
                logger.warning(f"[{self.correlation_id}] No valid charts found to resize")
                return OperationResult(
                    success=True,
                    mode_used="no_operations_needed",
                    execution_time=time.time() - start_time,
                    objects_processed=0,
                    api_calls_made=1,
                    details={"message": "No charts found to resize"},
                )

            # Execute resize operations
            result = await self._execute_resize_operations(resize_operations)

            logger.info(
                f"[{self.correlation_id}] Resized {len(resize_operations)} charts in {result.execution_time:.2f}s"
            )
            return result

        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"[{self.correlation_id}] Chart resizing failed: {e}")

            return OperationResult(
                success=False,
                error_message=str(e),
                mode_used="resize_failed",
                execution_time=execution_time,
                objects_processed=0,
                api_calls_made=0,
            )

    async def place_charts_with_custom_sizing(self, chart_placements: List[ChartPlacement]) -> OperationResult:
        """
        Place charts with full control over size and position.

        This method replaces placeholder shapes with images, but with custom sizing.

        Args:
            chart_placements: List of ChartPlacement objects

        Returns:
            OperationResult with placement details
        """

        start_time = time.time()

        try:
            if not chart_placements:
                return OperationResult(
                    success=True,
                    mode_used="no_placements_needed",
                    execution_time=0,
                    objects_processed=0,
                    api_calls_made=0,
                )

            # Group placements by page for batch operations
            placements_by_page = {}
            for placement in chart_placements:
                if placement.page_id not in placements_by_page:
                    placements_by_page[placement.page_id] = []
                placements_by_page[placement.page_id].append(placement)

            # Execute placements for each page
            total_operations = 0
            total_api_calls = 0
            successful_placements = []
            failed_placements = []

            for page_id, page_placements in placements_by_page.items():
                try:
                    result = await self._place_charts_on_page(page_id, page_placements)

                    total_operations += result.objects_processed
                    total_api_calls += result.api_calls_made

                    if result.success:
                        successful_placements.extend([p.data_type for p in page_placements])
                    else:
                        failed_placements.extend(
                            [{"data_type": p.data_type, "error": result.error_message} for p in page_placements]
                        )

                except Exception as e:
                    logger.error(f"[{self.correlation_id}] Failed to place charts on page {page_id}: {e}")
                    failed_placements.extend([{"data_type": p.data_type, "error": str(e)} for p in page_placements])

            execution_time = time.time() - start_time
            success = len(failed_placements) == 0

            return OperationResult(
                success=success,
                mode_used="custom_chart_placement",
                execution_time=execution_time,
                objects_processed=total_operations,
                api_calls_made=total_api_calls,
                details={
                    "successful_placements": successful_placements,
                    "failed_placements": failed_placements,
                    "total_charts": len(chart_placements),
                },
            )

        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"[{self.correlation_id}] Chart placement with custom sizing failed: {e}")

            return OperationResult(
                success=False,
                error_message=str(e),
                mode_used="custom_placement_failed",
                execution_time=execution_time,
                objects_processed=0,
                api_calls_made=0,
            )

    async def _execute_resize_operations(self, resize_operations: List[ResizeOperation]) -> OperationResult:
        """Execute chart resize operations using batch API calls."""

        start_time = time.time()

        try:
            # Build batch update requests
            requests = []

            for operation in resize_operations:
                # Update size
                requests.append(
                    {
                        "updatePageElementSize": {
                            "objectId": operation.object_id,
                            "size": operation.new_size.to_googleapi_size(),
                        }
                    }
                )

                # Update transform (position)
                requests.append(
                    {
                        "updatePageElementTransform": {
                            "objectId": operation.object_id,
                            "transform": operation.new_transform.to_googleapi_transform(),
                            "applyMode": "ABSOLUTE",
                        }
                    }
                )

            # Execute batch update
            result = self.api_wrapper._execute_batch_update_sync(requests, self.presentation_id, self.correlation_id)

            if not result.success:
                raise ChartSizingError(f"Batch resize failed: {result.error_message}")

            execution_time = time.time() - start_time

            return OperationResult(
                success=True,
                mode_used="batch_resize",
                execution_time=execution_time,
                objects_processed=len(resize_operations),
                api_calls_made=1,  # Single batch call
                details={"resized_charts": [op.data_type for op in resize_operations], "total_requests": len(requests)},
            )

        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"[{self.correlation_id}] Batch resize execution failed: {e}")

            return OperationResult(
                success=False,
                error_message=str(e),
                mode_used="batch_resize_failed",
                execution_time=execution_time,
                objects_processed=0,
                api_calls_made=0,
            )

    async def _place_charts_on_page(self, page_id: str, placements: List[ChartPlacement]) -> OperationResult:
        """Place multiple charts on a single page with custom sizing."""

        try:
            # Step 1: Delete placeholder shapes if they exist
            delete_requests = []
            if placements[0].placeholder_text:  # If we know placeholder text, find and delete shapes
                # This would require discovering placeholder shapes first
                # For now, we assume shapes will be replaced via replaceAllShapesWithImage
                pass

            # Step 2: Insert images with custom size and position
            insert_requests = []
            for placement in placements:
                insert_requests.append(
                    {
                        "createImage": {
                            "objectId": placement.object_id,
                            "url": placement.image_url,
                            "elementProperties": {
                                "pageObjectId": page_id,
                                "size": placement.size.to_googleapi_size(),
                                "transform": placement.transform.to_googleapi_transform(),
                            },
                        }
                    }
                )

            # Execute batch operation
            all_requests = delete_requests + insert_requests
            result = self.api_wrapper._execute_batch_update_sync(
                all_requests, self.presentation_id, self.correlation_id
            )

            if result.success:
                return OperationResult(
                    success=True,
                    mode_used="custom_page_placement",
                    execution_time=0,  # Will be calculated by parent
                    objects_processed=len(placements),
                    api_calls_made=1,
                )
            else:
                raise ChartSizingError(f"Page placement failed: {result.error_message}")

        except Exception as e:
            logger.error(f"[{self.correlation_id}] Failed to place charts on page {page_id}: {e}")
            return OperationResult(
                success=False,
                error_message=str(e),
                mode_used="page_placement_failed",
                execution_time=0,
                objects_processed=0,
                api_calls_made=0,
            )


# Convenience functions for integration with existing code


async def resize_charts_after_replacement(
    presentation_id: str,
    chart_data_types: List[str],
    object_id_mapping: Dict[str, str],  # data_type -> object_id
    config_dir: Optional[str] = None,
    correlation_id: Optional[str] = None,
) -> OperationResult:
    """
    Resize charts after they've been placed via shape replacement.

    Args:
        presentation_id: Google Slides presentation ID
        chart_data_types: List of chart data types that were placed
        object_id_mapping: Mapping from data_type to object_id
        config_dir: Directory for custom sizing configs
        correlation_id: For tracking operations

    Returns:
        OperationResult with resize operation details
    """

    correlation_id = correlation_id or f"resize_{int(time.time())}"

    try:
        # Get sizing configuration for chart types
        sizing_config = get_chart_sizing_config(
            data_types=chart_data_types,
            presentation_id=presentation_id,
            config_dir=config_dir,
            correlation_id=correlation_id,
        )

        # Prepare parameters for resize operation
        chart_object_ids = list(object_id_mapping.values())
        data_type_mapping = {obj_id: data_type for data_type, obj_id in object_id_mapping.items()}

        # Execute resize
        resizer = ChartResizer(presentation_id, correlation_id)
        return await resizer.resize_existing_charts(chart_object_ids, sizing_config, data_type_mapping)

    except Exception as e:
        logger.error(f"[{correlation_id}] Resize after replacement failed: {e}")
        return OperationResult(
            success=False,
            error_message=str(e),
            mode_used="resize_after_replacement_failed",
            execution_time=0,
            objects_processed=0,
            api_calls_made=0,
        )
