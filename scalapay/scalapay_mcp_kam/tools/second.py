import json
from typing import Any, Dict

from error_handler import handle_google_api_error  # Implement this based on your project
from googleapiclient.discovery import Resource
from schemas import CreatePresentationArgs  # Define this with at least a `title` field


def create_presentation_tool(slides: Resource, args: CreatePresentationArgs) -> Dict[str, Any]:
    """
    Creates a new Google Slides presentation.

    Args:
        slides: The authenticated Google Slides API client.
        args: An object with a 'title' attribute.

    Returns:
        A dictionary containing the API response content.

    Raises:
        McpError: If the Google API call fails.
    """
    try:
        response = slides.presentations().create(body={"title": args.title}).execute()

        return {"content": [{"type": "text", "text": json.dumps(response, indent=2)}]}

    except Exception as error:
        raise handle_google_api_error(error, "create_presentation")
