import base64
import os
from dotenv import load_dotenv
from fastmcp import FastMCP
from langchain_core.runnables import RunnableConfig
import sys
from fastmcp import Context
from dataclasses import dataclass
from markitdown import MarkItDown

md = MarkItDown()
import logging
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s %(name)s: %(message)s')
logger = logging.getLogger(__name__)

load_dotenv()
mcp = FastMCP("company-intelligence", instructions="""
        This server allows to create slides about merchants given the merchant token and the period.
        Call create_slides_wrapper() to generate the slides, considering that the tool will take a dataframe from another mcp server (alfred). Call this tool only when you have the merchant token and the period given by the user. don't make them up.
               
    """)
config = RunnableConfig()

@dataclass
class UserInfo:
    merchant_token: str
@mcp.tool(
    annotations={
        "title": "Read PDF Document",
        "readOnlyHint": True,
        "openWorldHint": False
    }
)
def read_pdf(file_path: str) -> str:
    """Read a PDF file and return the text content.
    
    Args:
        file_path: Path to the PDF file to read
    """
    try:
        # Expand the tilde (if part of the path) to the home directory path
        expanded_path = os.path.expanduser(file_path)
        
        # Use markitdown to convert the PDF to text
        return md.convert(expanded_path).text_content
    except Exception as e:
        # Return error message that the LLM can understand
        return f"Error reading PDF: {str(e)}"


@mcp.tool()
async def create_slides_wrapper(merchant_token: str, starting_date: str, end_date:str, ctx: Context | None = None) -> dict:
    logger.info("create_slides_wrapper invoked")
    logger.debug(f"Input string: {merchant_token, ctx}")
    try:
        from slides_test_local import create_slides
        # TO-DO: Remove elicit part in production
        
        result = await ctx.elicit(
            message="Please provide your information",
            response_type=UserInfo
        )
        if result.action == "accept":
            result_slides = await create_slides(merchant_token, starting_date, end_date, ctx=ctx)
            pdf_path = result_slides.get("pdf_path")
            logger.info("Slides created successfully with PDF: %s", pdf_path)
            ctx.info("Slides created successfully")
        elif result.action == "decline":
            return "Information not provided"
        else:
            return "Operation cancelled"

        return {
            "message": "Slides created successfully",
            "presentation_id": result_slides["presentation_id"],
            "pdf_resource_uri": f"file://{pdf_path}",
            "alfred_result": result_slides.get("alfred_result", {}),
            "chart_file_id": result_slides.get("chart_file_id", "N/A"),
            "chart_image_url": result_slides.get("chart_image_url", "N/A"),
            # "info": result.get("info", {}),
        }
    except Exception as e:
        logger.exception("Error in create_slides_wrapper")
        # if within an MCP tool, optionally send to client
        if ctx is not None:
            await ctx.error(f"create_slides_wrapper failed: {e}")
        return {"error": "Slides creation failed"}


@mcp.resource(uri="file://{path}")
async def serve_pdf(path: str):
    logger.debug("serve_pdf called with path: %s", path)
    full_path = path
    if not os.path.exists(full_path):
        logger.error("serve_pdf: File not found %s", full_path)
        raise FileNotFoundError()
    with open(full_path, "rb") as f:
        data = f.read()
    logger.info("serve_pdf: serving file %s (size: %d bytes)", path, len(data))
    return dict(
        uri=f"file://{full_path}",
        mime_type="application/pdf",
        blob=base64.b64encode(data).decode("utf-8"),
    )

@mcp.resource("file://{path}")
def provide_recent_document(path: str):
    """Provide access to a recently used document.
    
    This resource shows how to use path parameters to provide dynamic resources.
    """
    try:
        # Construct the path to the recent documents folder
        recent_docs_folder = os.path.expanduser("~/Documents/Recent")
        file_path = os.path.join(recent_docs_folder, path)
        
        # Validate the file exists
        if not os.path.exists(file_path):
            return f"File not found: {file_path}"
            
        # Convert to text using markitdown
        return md.convert(file_path).text_content
    except Exception as e:
        return f"Error accessing document: {str(e)}"

if __name__ == "__main__":
    logger.info("🚀 Starting MCP server")
    try:
        mcp.run(transport="streamable-http", host="0.0.0.0", port=8005)
    except Exception:
        logger.exception("❌ MCP crashed")
        sys.exit(1)
