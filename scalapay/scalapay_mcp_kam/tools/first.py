from googleapiclient.discovery import Resource
from typing import Any, Dict, Optional
from error_handler import handle_google_api_error  # You should implement this
from schemas import BatchUpdatePresentationArgs  # You should define this schema
import json

def batch_update_presentation_tool(
    slides: Resource,
    args: BatchUpdatePresentationArgs
) -> Dict[str, Any]:
    """
    Applies a batch of updates to a Google Slides presentation.

    Args:
        slides: The authenticated Google Slides API client.
        args: A dataclass or dict containing presentationId, requests, and optionally writeControl.

    Returns:
        A dict containing the API response content.

    Raises:
        McpError: if the Google API call fails.
    """
    try:
        response = slides.presentations().batchUpdate(
            presentationId=args.presentation_id,
            body={
                "requests": args.requests,
                "writeControl": getattr(args, "write_control", None),
            }
        ).execute()

        return {
            "content": [{"type": "text", "text": json.dumps(response, indent=2)}]
        }

    except Exception as error:
        raise handle_google_api_error(error, "batch_update_presentation")
