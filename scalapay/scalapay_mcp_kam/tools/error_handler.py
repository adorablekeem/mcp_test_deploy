import logging
from typing import Any, Union

# Define your custom McpError and ErrorCode (you may adjust this to match your structure)
class ErrorCode:
    InternalError = "InternalError"

class McpError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(f"[{code}] {message}")


def extract_raw_error_message(err: Any) -> str:
    """Extracts a readable message from a complex error object."""
    if isinstance(err, dict) and "response" in err:
        try:
            return (
                err.get("response", {})
                   .get("data", {})
                   .get("error", {})
                   .get("message", str(err))
            )
        except Exception:
            return str(err)

    if isinstance(err, Exception):
        return str(err)

    if isinstance(err, str):
        return err

    return "Unknown Google API error"


def handle_google_api_error(error: Any, tool_name: str) -> McpError:
    """Transforms any Google API error into a structured MCP error."""
    raw_message = extract_raw_error_message(error)
    final_message = f"Google API Error in {tool_name}: {raw_message}"

    logging.error(f"Google API Error ({tool_name}): %s", error)
    return McpError(ErrorCode.InternalError, final_message)


def get_startup_error_message(err: Union[str, Exception, Any]) -> str:
    """Formats a startup error into a string."""
    if isinstance(err, Exception):
        return str(err)
    if isinstance(err, str):
        return err
    return "Unknown error"
