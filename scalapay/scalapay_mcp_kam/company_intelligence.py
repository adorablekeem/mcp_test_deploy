import base64
import os
from dotenv import load_dotenv
from fastmcp import FastMCP
from langchain_core.runnables import RunnableConfig
import sys
from fastmcp import Context
from dataclasses import dataclass

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
    start_date: str
    end_date: str

@mcp.tool()
async def create_slides_wrapper(merchant_token: str, starting_date: str, end_date:str, ctx: Context | None = None) -> dict:
    logger.info("create_slides_wrapper invoked")
    logger.debug(f"Input string: {merchant_token, ctx}")
    try:
        from slides_test_local import create_slides
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


if __name__ == "__main__":
    logger.info("🚀 Starting MCP server")
    try:
        mcp.run(transport="stdio")
    except Exception:
        logger.exception("❌ MCP crashed")
        sys.exit(1)
