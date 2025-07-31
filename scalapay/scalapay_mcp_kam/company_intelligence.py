import base64
import os
from dotenv import load_dotenv
from fastmcp import FastMCP
from langchain_core.runnables import RunnableConfig
import sys
from fastmcp import Context

import logging
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s %(name)s: %(message)s')
logger = logging.getLogger(__name__)

load_dotenv()
mcp = FastMCP("company-intelligence")
config = RunnableConfig()


@mcp.tool()
async def create_slides_wrapper(string: str, ctx: Context | None = None) -> dict:
    logger.info("create_slides_wrapper invoked")
    logger.debug(f"Input string: {string}")
    try:
        from slides_test import create_slides
        result = await create_slides(string)
        pdf_path = result.get("pdf_path")
        logger.info("Slides created successfully with PDF: %s", pdf_path)
        return {
            "message": "Slides created successfully",
            "presentation_id": result["presentation_id"],
            "pdf_resource_uri": f"file://{pdf_path}",
            "chart_file_id": result.get("chart_file_id", "N/A"),
            "chart_image_url": result.get("chart_image_url", "N/A"),
            "info": result.get("info", {}),
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

if __name__ == "__main__":
    logger.info("🚀 Starting MCP server")
    try:
        mcp.run(transport="streamable-http", host="0.0.0.0", port=8001)
    except Exception:
        logger.exception("❌ MCP crashed")
        sys.exit(1)
