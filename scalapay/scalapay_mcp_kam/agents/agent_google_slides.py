#!/usr/bin/env python3
"""
Google Slides MCP Server
A Model Context Protocol server for Google Slides operations using FastMCP
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional, Tuple

from fastmcp import FastMCP
from GoogleApiSupport import auth

# Set up Google API credentials
# Update this path to match your credentials file location
os.environ[
    "GOOGLE_APPLICATION_CREDENTIALS"
] = "/Users/keem.adorable@scalapay.com/scalapay/scalapay_mcp_kam/scalapay/scalapay_mcp_kam/credentials.json"


# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastMCP server
mcp = FastMCP("Google Slides MCP Server")


class Size:
    def __init__(self, width: float = 3000000.0, height: float = 3000000.0, unit: str = "EMU"):
        self.json = {"width": {"magnitude": width, "unit": unit}, "height": {"magnitude": height, "unit": unit}}

    def __repr__(self):
        return json.dumps(self.json, indent=4)


class Transform:
    def __init__(
        self,
        scale_x: float = 1,
        scale_y: float = 1,
        shear_x: float = 0,
        shear_y: float = 0,
        translate_x: float = 0,
        translate_y: float = 0,
        unit: str = "EMU",
    ):
        self.json = {
            "scaleX": scale_x,
            "scaleY": scale_y,
            "shearX": shear_x,
            "shearY": shear_y,
            "translateX": translate_x,
            "translateY": translate_y,
            "unit": unit,
        }

    def __repr__(self):
        return json.dumps(self.json, indent=4)


def execute_batch_update(requests, presentation_id, additional_apis=[]):
    """Execute batch update requests on a presentation"""
    body = {"requests": requests}
    service = auth.get_service("slides", additional_apis=additional_apis)
    response = service.presentations().batchUpdate(presentationId=presentation_id, body=body).execute()
    return response


# Core functions (not MCP tools) - can be called internally
def _get_presentation_info(presentation_id: str) -> Dict[str, Any]:
    """Internal function to get presentation info"""
    service = auth.get_service("slides")
    presentation = service.presentations().get(presentationId=presentation_id).execute()
    return presentation


def _get_presentation_slides(presentation_id: str) -> List[Dict[str, Any]]:
    """Internal function to get presentation slides"""
    slides = _get_presentation_info(presentation_id).get("slides", [])
    return slides


@mcp.tool()
def create_presentation(name: str) -> str:
    """Create a new Google Slides presentation

    Args:
        name: The title for the new presentation

    Returns:
        The presentation ID of the created presentation
    """
    try:
        service = auth.get_service("slides")
        presentation = service.presentations().create(body={"title": name}).execute()
        logger.info(f"Created presentation: {name} with ID: {presentation['presentationId']}")
        return presentation["presentationId"]
    except Exception as e:
        logger.error(f"Failed to create presentation: {e}")
        raise


@mcp.tool()
def get_presentation_info(presentation_id: str) -> Dict[str, Any]:
    """Get information about a Google Slides presentation

    Args:
        presentation_id: The ID of the presentation

    Returns:
        Dictionary containing presentation information
    """
    try:
        presentation = _get_presentation_info(presentation_id)
        logger.info(f"Retrieved info for presentation: {presentation_id}")
        return presentation
    except Exception as e:
        logger.error(f"Failed to get presentation info: {e}")
        raise


@mcp.tool()
def get_presentation_slides(presentation_id: str) -> List[Dict[str, Any]]:
    """Get all slides from a presentation

    Args:
        presentation_id: The ID of the presentation

    Returns:
        List of slide objects
    """
    try:
        slides = _get_presentation_slides(presentation_id)
        logger.info(f"Retrieved {len(slides)} slides from presentation: {presentation_id}")
        return slides
    except Exception as e:
        logger.error(f"Failed to get presentation slides: {e}")
        raise


@mcp.tool()
def batch_text_replace(
    text_mapping: Dict[str, str], presentation_id: str, pages: Optional[List[str]] = None
) -> Dict[str, Any]:
    """Replace placeholder text in a presentation

    Args:
        text_mapping: Dictionary of placeholder_text -> replacement_text
        presentation_id: The ID of the presentation
        pages: Optional list of page IDs to limit replacement scope

    Returns:
        API response from the batch update
    """
    try:
        if pages is None:
            pages = []

        requests = []
        for placeholder_text, new_value in text_mapping.items():
            if isinstance(new_value, str):
                requests.append(
                    {
                        "replaceAllText": {
                            "containsText": {"text": "{{" + placeholder_text + "}}"},
                            "replaceText": new_value,
                            "pageObjectIds": pages,
                        }
                    }
                )
            else:
                raise ValueError(f"The text from key {placeholder_text} is not a string")

        response = execute_batch_update(requests, presentation_id)
        logger.info(f"Replaced {len(requests)} text placeholders in presentation: {presentation_id}")
        return response
    except Exception as e:
        logger.error(f"Failed to replace text: {e}")
        raise


@mcp.tool()
def insert_image(
    url: str,
    page_id: str,
    presentation_id: str,
    object_id: Optional[str] = None,
    transform_params: Optional[Dict[str, float]] = None,
    size_params: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """Insert an image into a slide

    Args:
        url: URL of the image to insert
        page_id: ID of the slide to insert the image into
        presentation_id: ID of the presentation
        object_id: Optional object ID for the image
        transform_params: Optional transform parameters (translateX, translateY, scaleX, scaleY, unit)
        size_params: Optional size parameters (width, height, unit)

    Returns:
        API response from the batch update
    """
    try:
        # Build transform object if parameters provided
        transform = None
        if transform_params:
            transform = Transform(
                scale_x=transform_params.get("scaleX", 1.0),
                scale_y=transform_params.get("scaleY", 1.0),
                translate_x=transform_params.get("translateX", 0),
                translate_y=transform_params.get("translateY", 0),
                unit=transform_params.get("unit", "EMU"),
            ).json

        # Build size object if parameters provided
        size = None
        if size_params:
            size = Size(
                width=size_params.get("width", 3000000.0),
                height=size_params.get("height", 3000000.0),
                unit=size_params.get("unit", "EMU"),
            ).json

        requests = [
            {
                "createImage": {
                    "objectId": object_id,
                    "url": url,
                    "elementProperties": {"pageObjectId": page_id, "transform": transform, "size": size},
                }
            }
        ]

        response = execute_batch_update(requests, presentation_id)
        logger.info(f"Inserted image from {url} into slide {page_id}")
        return response
    except Exception as e:
        logger.error(f"Failed to insert image: {e}")
        raise


@mcp.tool()
def batch_replace_shape_with_image(
    image_mapping: Dict[str, str], presentation_id: str, pages: Optional[List[str]] = None, fill: bool = False
) -> Dict[str, Any]:
    """Replace shapes containing placeholder text with images

    Args:
        image_mapping: Dictionary of placeholder_text -> image_url
        presentation_id: ID of the presentation
        pages: Optional list of page IDs to limit replacement scope
        fill: Whether to use CENTER_CROP (True) or CENTER_INSIDE (False)

    Returns:
        API response from the batch update
    """
    try:
        if pages is None:
            pages = []

        requests = []
        replace_method = "CENTER_CROP" if fill else "CENTER_INSIDE"

        for contains_text, url in image_mapping.items():
            request = {
                "replaceAllShapesWithImage": {
                    "imageUrl": url,
                    "replaceMethod": replace_method,
                    "pageObjectIds": pages,
                    "containsText": {
                        "text": "{{" + contains_text + "}}",
                    },
                }
            }
            requests.append(request)

        response = execute_batch_update(requests, presentation_id)
        logger.info(f"Replaced {len(requests)} shapes with images in presentation: {presentation_id}")
        return response
    except Exception as e:
        logger.error(f"Failed to replace shapes with images: {e}")
        raise


@mcp.tool()
def delete_object(presentation_id: str, object_id: str) -> Dict[str, Any]:
    """Delete an object from a presentation

    Args:
        presentation_id: ID of the presentation
        object_id: ID of the object to delete

    Returns:
        API response from the batch update
    """
    try:
        requests = [{"deleteObject": {"objectId": object_id}}]

        response = execute_batch_update(requests, presentation_id)
        logger.info(f"Deleted object {object_id} from presentation: {presentation_id}")
        return response
    except Exception as e:
        logger.error(f"Failed to delete object: {e}")
        raise


@mcp.tool()
def batch_delete_objects(presentation_id: str, object_id_list: List[str]) -> Dict[str, Any]:
    """Delete multiple objects from a presentation

    Args:
        presentation_id: ID of the presentation
        object_id_list: List of object IDs to delete

    Returns:
        API response from the batch update
    """
    try:
        requests = []
        for object_id in object_id_list:
            requests.append({"deleteObject": {"objectId": object_id}})

        response = execute_batch_update(requests, presentation_id)
        logger.info(f"Deleted {len(object_id_list)} objects from presentation: {presentation_id}")
        return response
    except Exception as e:
        logger.error(f"Failed to delete objects: {e}")
        raise


@mcp.tool()
def get_all_shapes_placeholders(presentation_id: str) -> Dict[str, Any]:
    """Get all shape placeholders in a presentation

    Args:
        presentation_id: ID of the presentation

    Returns:
        Dictionary mapping object IDs to their placeholder information
    """
    try:
        shape_ids = {}
        presentation = _get_presentation_info(presentation_id)

        for slide in presentation["slides"]:
            for page_element in slide["pageElements"]:
                shape_ids[page_element["objectId"]] = None
                if "shape" in page_element:
                    if "text" in page_element["shape"]:
                        has_inner_text = [
                            text for text in page_element["shape"]["text"]["textElements"] if text.get("textRun")
                        ]
                        if has_inner_text:
                            shape_ids[page_element["objectId"]] = {
                                "inner_text": has_inner_text[0]["textRun"]["content"].strip(),
                                "page_id": slide["objectId"],
                            }

        logger.info(f"Found {len(shape_ids)} shapes in presentation: {presentation_id}")
        return shape_ids
    except Exception as e:
        logger.error(f"Failed to get shape placeholders: {e}")
        raise


@mcp.tool()
def duplicate_object(presentation_id: str, object_id: str) -> Dict[str, Any]:
    """Duplicate an object in a presentation

    Args:
        presentation_id: ID of the presentation
        object_id: ID of the object to duplicate

    Returns:
        API response from the batch update
    """
    try:
        requests = [{"duplicateObject": {"objectId": object_id}}]

        response = execute_batch_update(requests, presentation_id)
        logger.info(f"Duplicated object {object_id} in presentation: {presentation_id}")
        return response
    except Exception as e:
        logger.error(f"Failed to duplicate object: {e}")
        raise


@mcp.tool()
def transform_object(
    presentation_id: str, object_id: str, transform_params: Dict[str, float], apply_mode: str = "ABSOLUTE"
) -> Dict[str, Any]:
    """Transform an object in a presentation

    Args:
        presentation_id: ID of the presentation
        object_id: ID of the object to transform
        transform_params: Transform parameters (scaleX, scaleY, translateX, translateY, etc.)
        apply_mode: Transform application mode ('ABSOLUTE' or 'RELATIVE')

    Returns:
        API response from the batch update
    """
    try:
        transform = Transform(
            scale_x=transform_params.get("scaleX", 1.0),
            scale_y=transform_params.get("scaleY", 1.0),
            translate_x=transform_params.get("translateX", 0),
            translate_y=transform_params.get("translateY", 0),
            unit=transform_params.get("unit", "EMU"),
        ).json

        requests = [
            {"updatePageElementTransform": {"objectId": object_id, "transform": transform, "applyMode": apply_mode}}
        ]

        response = execute_batch_update(requests, presentation_id)
        logger.info(f"Transformed object {object_id} in presentation: {presentation_id}")
        return response
    except Exception as e:
        logger.error(f"Failed to transform object: {e}")
        raise


@mcp.tool()
def replace_shape_with_chart(
    presentation_id: str,
    placeholder_text: str,
    spreadsheet_id: str,
    chart_id: str,
    linking_mode: str = "NOT_LINKED_IMAGE",
    target_id_pages: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Replace a shape with a Google Sheets chart

    Args:
        presentation_id: ID of the presentation
        placeholder_text: Text in the shape to replace
        spreadsheet_id: ID of the Google Sheets spreadsheet
        chart_id: ID of the chart in the spreadsheet
        linking_mode: How to link the chart ('NOT_LINKED_IMAGE', 'LINKED', etc.)
        target_id_pages: Optional list of page IDs to limit replacement scope

    Returns:
        API response from the batch update
    """
    try:
        if target_id_pages is None:
            target_id_pages = []

        requests = [
            {
                "replaceAllShapesWithSheetsChart": {
                    "containsText": {"text": placeholder_text, "matchCase": True},
                    "spreadsheetId": spreadsheet_id,
                    "chartId": chart_id,
                    "linkingMode": linking_mode,
                    "pageObjectIds": target_id_pages,
                }
            }
        ]

        response = execute_batch_update(requests, presentation_id, additional_apis=["sheets"])
        logger.info(f"Replaced shape with chart in presentation: {presentation_id}")
        return response
    except Exception as e:
        logger.error(f"Failed to replace shape with chart: {e}")
        raise


if __name__ == "__main__":
    # Run the MCP server
    mcp.run(transport="http", host="0.0.0.0", port=8006)
