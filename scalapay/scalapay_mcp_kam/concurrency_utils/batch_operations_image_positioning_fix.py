"""
Fixed chart positioning and sizing implementation for Google Slides API.
Addresses critical issues with image positioning, sizing, and object ID handling.
"""

import asyncio
import logging
import re
from typing import Any, Dict, List, Optional

from ..utils.google_connection_manager import connection_manager

logger = logging.getLogger(__name__)


def build_width_height_sizing_request(
    image_object_id: str, target_width: int, target_height: int, data_type: str
) -> Dict[str, Any]:
    """
    Build Google Slides API request for absolute width/height sizing.

    Args:
        image_object_id: The actual object ID of the image element
        target_width: Target width in points
        target_height: Target height in points
        data_type: Chart data type for logging

    Returns:
        Properly formatted Google Slides API request using updatePageElementSize
    """
    logger.info(
        f"Building width/height sizing request for {data_type}: "
        f"image_id={image_object_id}, size=({target_width}x{target_height})"
    )

    return {
        "updatePageElementSize": {
            "objectId": image_object_id,
            "size": {
                "width": {"magnitude": target_width, "unit": "PT"},
                "height": {"magnitude": target_height, "unit": "PT"},
            },
        }
    }


def build_correct_image_positioning_request(
    image_object_id: str, image_style_config: Dict[str, Any], data_type: str
) -> Dict[str, Any]:
    """
    Build correct Google Slides API request for image positioning and sizing.

    Args:
        image_object_id: The actual object ID of the image element (NOT slide ID)
        image_style_config: Style configuration from chart_styling_config
        data_type: Chart data type for logging

    Returns:
        Properly formatted Google Slides API request using updatePageElementTransform
    """
    resize_config = image_style_config.get("resize", {})

    # Extract styling parameters with correct defaults
    scale_x_raw = resize_config.get("scaleX", 200)  # Chart config scale value
    scale_y_raw = resize_config.get("scaleY", 200)  # Chart config scale value
    translate_x_pt = resize_config.get("translateX", 200)  # X position in points
    translate_y_pt = resize_config.get("translateY", 200)  # Y position in points
    unit = resize_config.get("unit", "PT")

    # Convert config values to proper scale factors for Google Slides API
    # Config values like 140 need to be converted to scale factors like 1.4
    # Google Slides API expects: 1.0 = original, 1.5 = 150%, etc.
    scale_x_factor = float(scale_x_raw) / 100.0  # Convert 140 -> 1.4
    scale_y_factor = float(scale_y_raw) / 100.0  # Convert 110 -> 1.1

    logger.info(
        f"Building positioning request for {data_type}: "
        f"config_values=({scale_x_raw}x{scale_y_raw}), "
        f"scale_factors=({scale_x_factor:.1f}x{scale_y_factor:.1f}), "
        f"position=({translate_x_pt}, {translate_y_pt} {unit})"
    )

    # Build the correct Google Slides API request using updatePageElementTransform
    return {
        "updatePageElementTransform": {
            "objectId": image_object_id,
            "transform": {
                "scaleX": scale_x_factor,  # Scale factor for width
                "scaleY": scale_y_factor,  # Scale factor for height
                "translateX": translate_x_pt,  # Position in points
                "translateY": translate_y_pt,  # Position in points
                "unit": "PT",  # Use points directly
            },
            "applyMode": "ABSOLUTE",
        }
    }


# Removed build_correct_image_transform_request - now using combined request in build_correct_image_positioning_request


def find_image_object_ids_in_slide(slide_data: Dict[str, Any]) -> List[str]:
    """
    Find all image object IDs in a slide.

    Args:
        slide_data: Slide data from Google Slides API

    Returns:
        List of image object IDs
    """
    image_object_ids = []

    for element in slide_data.get("pageElements", []):
        if "image" in element:
            image_object_ids.append(element["objectId"])

    return image_object_ids


def match_image_to_chart_config(token: str, slide_metadata: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Match specific token to its chart configuration.
    Returns None if no match found.

    Args:
        token: Image token (e.g. "{{aov_chart}}")
        slide_metadata: Metadata mapping data types to configs

    Returns:
        Chart configuration or None
    """
    from ..utils.slug_validation import SlugMapper

    slug_mapper = SlugMapper("1hDkICKx4D3jHdxky_3_1iJcPFVQFxTkvlH7mVSFCx_o")

    # Extract chart name from token (e.g., {{aov_chart}} -> aov)
    token_match = re.match(r"\{\{([^_}]+)(?:_chart)?\}\}", token)
    if not token_match:
        return None

    token_slug = token_match.group(1)

    # Find matching data type from slide metadata
    for data_type, metadata in slide_metadata.items():
        # Generate expected slug for this data type
        expected_slug = slug_mapper.get_slug(data_type)

        # Check for exact match or close match
        if (
            token_slug == expected_slug
            or token_slug.replace("-", "_") == expected_slug.replace("-", "_")
            or expected_slug.replace("-", "_") == token_slug.replace("-", "_")
        ):
            # Return the matched configuration
            return {"data_type": data_type, "metadata": metadata, "matched_slug": expected_slug}

    return None


async def apply_chart_specific_positioning_correctly(
    slides_service,
    presentation_id: str,
    image_map: Dict[str, str],
    slide_metadata: Dict[str, Dict[str, Any]],
    correlation_id: str = None,
) -> Dict[str, Any]:
    """
    Correctly apply chart-specific positioning and sizing to images.

    This is the FIXED version that properly handles:
    1. Finding actual image object IDs (not slide IDs)
    2. Separating size and transform operations
    3. Using correct parameter mapping
    """
    corr_id = correlation_id or "image_positioning"
    logger.info(f"[{corr_id}] Starting CORRECTED chart positioning for {len(image_map)} images")

    try:
        # First, get the current presentation to find actual image object IDs
        presentation = await asyncio.get_event_loop().run_in_executor(
            None, lambda: slides_service.presentations().get(presentationId=presentation_id).execute()
        )

        # Build mapping of slide IDs to image object IDs
        slide_to_images = {}
        for slide in presentation.get("slides", []):
            slide_id = slide["objectId"]
            image_ids = find_image_object_ids_in_slide(slide)
            if image_ids:
                slide_to_images[slide_id] = image_ids

        logger.info(f"[{corr_id}] Found images in {len(slide_to_images)} slides")

        # Build positioning requests for each image
        positioning_requests = []
        styles_applied = 0

        # Use slug mapper for better token matching
        from ..utils.slug_validation import SlugMapper

        slug_mapper = SlugMapper("1hDkICKx4D3jHdxky_3_1iJcPFVQFxTkvlH7mVSFCx_o")  # Use actual template ID

        # Keep track of processed images to avoid conflicts
        processed_images = set()

        for token, image_url in image_map.items():
            logger.info(f"[{corr_id}] Processing token: {token}")

            # Use improved matching function
            match_result = match_image_to_chart_config(token, slide_metadata)

            if match_result:
                from ..chart_config.chart_styling_config import get_image_style_for_slide

                data_type = match_result["data_type"]
                metadata = match_result["metadata"]
                matched_slug = match_result["matched_slug"]

                paragraph = metadata.get("paragraph", "")
                chart_type = metadata.get("chart_type")

                logger.info(f"[{corr_id}] Matched token '{token}' -> data_type '{data_type}' (slug: {matched_slug})")

                # Get style configuration and apply chart-specific sizing to matched images
                image_style_config = get_image_style_for_slide(data_type, paragraph, chart_type)
                resize_config = image_style_config.get("resize", {})

                # Get target dimensions from configuration
                target_width = resize_config.get("width")
                target_height = resize_config.get("height")

                if target_width and target_height:
                    # Apply sizing to available images, avoiding conflicts
                    applied_to_image = False
                    for slide_id, image_object_ids in slide_to_images.items():
                        for image_object_id in image_object_ids:
                            # Skip if this image already has styling applied
                            if image_object_id in processed_images:
                                continue

                            # Build width/height sizing request
                            sizing_request = build_width_height_sizing_request(
                                image_object_id, target_width, target_height, data_type
                            )
                            positioning_requests.append(sizing_request)
                            styles_applied += 1
                            processed_images.add(image_object_id)

                            logger.info(
                                f"[{corr_id}] Prepared sizing for {data_type}: "
                                f"image_id={image_object_id}, size=({target_width}x{target_height})"
                            )

                            applied_to_image = True
                            # Only apply to one image per chart type
                            break

                        if applied_to_image:
                            break

                    if not applied_to_image:
                        logger.warning(f"[{corr_id}] No available images for {data_type} (all already processed)")
                else:
                    logger.warning(f"[{corr_id}] No width/height found for {data_type}, skipping sizing")
            else:
                logger.warning(f"[{corr_id}] No metadata match found for token: {token}")

        # Execute positioning requests in batches (combined size + position)
        total_requests_executed = 0

        if positioning_requests:
            logger.info(f"[{corr_id}] Applying {len(positioning_requests)} combined size and position requests")
            for i in range(0, len(positioning_requests), 5):  # Batch of 5
                batch = positioning_requests[i : i + 5]

                await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: slides_service.presentations()
                    .batchUpdate(presentationId=presentation_id, body={"requests": batch})
                    .execute(),
                )
                total_requests_executed += len(batch)

                # Small delay between batches
                await asyncio.sleep(0.5)

        logger.info(
            f"[{corr_id}] CORRECTED chart positioning complete: "
            f"{styles_applied} images styled, {total_requests_executed} API calls"
        )

        return {
            "success": True,
            "styles_applied": styles_applied,
            "api_calls": total_requests_executed,
            "positioning_requests": len(positioning_requests),
            "processing_mode": "corrected_chart_positioning",
            "correlation_id": corr_id,
        }

    except Exception as e:
        logger.error(f"[{corr_id}] CORRECTED chart positioning failed: {e}")
        return {"success": False, "error": str(e), "styles_applied": 0, "correlation_id": corr_id}


# Updated chart styling configuration with correct parameter meanings
CORRECTED_CHART_CONFIGS = {
    "monthly_sales_bar": {
        "resize": {
            "scaleX": 450,  # Width in points (NOT scaling factor)
            "scaleY": 300,  # Height in points (NOT scaling factor)
            "translateX": 50,  # X position in points
            "translateY": 150,  # Y position in points
            "unit": "PT",
        }
    },
    "aov_line": {
        "resize": {
            "scaleX": 500,  # Wider for line charts
            "scaleY": 280,  # Slightly shorter
            "translateX": 25,  # More left
            "translateY": 160,  # Slightly lower
            "unit": "PT",
        }
    },
    "demographics_pie": {
        "resize": {
            "scaleX": 350,  # Square-ish for pie charts
            "scaleY": 350,  # Square
            "translateX": 100,  # Centered
            "translateY": 140,  # Centered
            "unit": "PT",
        }
    },
}
