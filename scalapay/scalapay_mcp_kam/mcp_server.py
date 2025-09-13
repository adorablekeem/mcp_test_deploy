import base64
import logging
import os
import sys

from dotenv import load_dotenv
from fastmcp import Context, FastMCP
from langchain_core.runnables import RunnableConfig

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

load_dotenv()
mcp = FastMCP(
    "company-intelligence",
    instructions="""
        This server allows to create slides about merchants given the merchant token and the period.
        Call create_slides_wrapper() to generate the slides, considering that the tool will take a dataframe from another mcp server (alfred). Call this tool only when you have the merchant token and the period given by the user. don't make them up.
               
    """,
)
config = RunnableConfig()


@mcp.tool()
async def create_slides_wrapper(
    merchant_token: str, starting_date: str, end_date: str, ctx: Context | None = None
) -> dict:
    logger.info("create_slides_wrapper invoked")
    logger.debug(f"Input string: {merchant_token, ctx}")
    try:
        from scalapay.scalapay_mcp_kam.tools_agent_kam import create_slides

        result = await create_slides(merchant_token, starting_date, end_date, ctx=ctx)
        pdf_path = result.get("pdf_path")
        logger.info("Slides created successfully with PDF: %s", pdf_path)
        return {
            "message": "Slides created successfully",
            "presentation_id": result["presentation_id"],
            "pdf_resource_uri": f"file://{pdf_path}",
            "alfred_result": result.get("alfred_result", {}),
            "chart_file_id": result.get("chart_file_id", "N/A"),
            "chart_image_url": result.get("chart_image_url", "N/A"),
            # "info": result.get("info", {}),
        }
    except Exception as e:
        logger.exception("Error in create_slides_wrapper")
        # if within an MCP tool, optionally send to client
        if ctx is not None:
            await ctx.error(f"create_slides_wrapper failed: {e}")
        return {"error": "Slides creation failed"}


@mcp.tool()
async def create_complete_slides_workflow(
    merchant_token: str, 
    starting_date: str, 
    end_date: str,
    ctx: Context | None = None
) -> dict:
    """
    Complete end-to-end workflow with Alfred data retrieval, MatPlot chart generation, 
    and Google Slides creation - all with comprehensive context logging
    """
    logger.info("create_complete_slides_workflow invoked")
    try:
        from complete_workflow_orchestration import create_slides_with_charts_workflow
        
        result = await create_slides_with_charts_workflow(
            merchant_token=merchant_token,
            starting_date=starting_date,
            end_date=end_date,
            ctx=ctx
        )
        
        if result["success"]:
            slide_results = result.get("slide_results", {})
            pdf_path = slide_results.get("pdf_path")
            
            return {
                "message": "Complete workflow finished successfully",
                "success": True,
                "presentation_id": slide_results.get("presentation_id"),
                "pdf_resource_uri": f"file://{pdf_path}" if pdf_path else None,
                "alfred_results_summary": f"{len(result['alfred_results'])} data types processed",
                "chart_results_summary": f"{len(result['chart_results'])} charts generated", 
                "slide_results": slide_results,
                "errors": result.get("errors", [])
            }
        else:
            if ctx:
                await ctx.error(f"Workflow failed: {result.get('errors', ['Unknown error'])}")
            return {
                "message": "Workflow failed", 
                "success": False,
                "errors": result.get("errors", [])
            }
            
    except Exception as e:
        logger.exception("Error in create_complete_slides_workflow")
        if ctx is not None:
            await ctx.error(f"Complete workflow failed: {e}")
        return {"error": "Complete workflow failed", "success": False}


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
        mcp.run(transport="streamable-http", host="0.0.0.0", port=8002)
    except Exception:
        logger.exception("❌ MCP crashed")
        sys.exit(1)
