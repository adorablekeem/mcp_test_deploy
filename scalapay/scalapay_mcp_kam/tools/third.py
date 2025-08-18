from googleapiclient.discovery import Resource
from typing import Any, Dict
from error_handler import handle_google_api_error  # Your custom error handler
from schemas import GetPageArgs  # You need to define this with presentation_id and page_object_id
import json


def get_page_tool(
    slides: Resource,
    args: GetPageArgs
) -> Dict[str, Any]:
    """
    Gets details about a specific page (slide) in a presentation.

    Args:
        slides: The authenticated Google Slides API client.
        args: An object with presentation_id and page_object_id attributes.

    Returns:
        A dictionary containing the API response content.

    Raises:
        McpError: If the Google API call fails.
    """
    try:
        response = slides.presentations().pages().get(
            presentationId=args.presentation_id,
            pageObjectId=args.page_object_id
        ).execute()

        return {
            "content": [{"type": "text", "text": json.dumps(response, indent=2)}]
        }

    except Exception as error:
        raise handle_google_api_error(error, "get_page")
