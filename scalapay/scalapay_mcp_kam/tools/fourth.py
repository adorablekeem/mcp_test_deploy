import json
from typing import Any, Dict, Optional

from error_handler import handle_google_api_error  # Your custom error handler
from googleapiclient.discovery import Resource
from schemas import GetPresentationArgs  # Should contain presentation_id and optionally fields


def get_presentation_tool(slides: Resource, args: GetPresentationArgs) -> Dict[str, Any]:
    """
    Gets details about a Google Slides presentation.

    Args:
        slides: The authenticated Google Slides API client.
        args: An object with 'presentation_id' and optional 'fields'.

    Returns:
        A dictionary containing the API response content.

    Raises:
        McpError: If the Google API call fails.
    """
    try:
        request = slides.presentations().get(
            presentationId=args.presentation_id, fields=args.fields if getattr(args, "fields", None) else None
        )
        response = request.execute()

        return {"content": [{"type": "text", "text": json.dumps(response, indent=2)}]}

    except Exception as error:
        raise handle_google_api_error(error, "get_presentation")
