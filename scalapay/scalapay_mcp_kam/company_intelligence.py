from fastmcp import FastMCP
# from src.agent.company_search import research_company_competitors
# from src.agent.person_search import linkedin_search
from langchain_core.runnables import RunnableConfig
import GoogleApiSupport.slides as slides
import base64
import os
from pydantic import AnyUrl
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Initialize FastMCP server
mcp = FastMCP("company-intelligence")
config = RunnableConfig()
"""
@mcp.tool()
async def research_company_competitors_wrapper(company_name: str, company_domain: str = None) -> dict:
    
    Wrapper function for research_company_competitors to be used with FastMCP.
    
    Args:
        company_name (str): The name of the company to research competitors for.
    
    Returns:
        dict: A dictionary containing the competitors of the specified company.
    
    similarweb_state = {
        "company_data": {
            "company_id": "",
            "company_name": company_name,
            "company_domain": company_domain or ""
        }
    }
    result = await research_company_competitors(similarweb_state, config)
    return result
"""
"""
@mcp.tool()
async def research_person_info_wrapper(lead_name: str, company_name: str, lead_email: str = None, company_domain: str = None) -> dict:

    Wrapper function for research_company_competitors to be used with FastMCP.
    
    Args:
        company_name (str): The name of the company to research competitors for.
    
    Returns:
        dict: A dictionary containing the competitors of the specified company.

    similarweb_state = {
        "lead_data": {
            "company_id": "",
            "lead_name": lead_name,
            "lead_email": lead_email or ""
        },
        "company_data": {
            "company_id": "",
            "company_name": company_name,
            "company_domain": company_domain or ""
        }
    }
    result = await linkedin_search(similarweb_state, config)
    return result


# Keep track of latest PDF
latest_pdf_path = None
"""

@mcp.tool()
async def create_slides_wrapper(string: str) -> dict:
    """
    Creates a Google Slides presentation and prepares a PDF resource for download.
    """
    global latest_pdf_path
    from slides_test import create_slides
    result = await create_slides(string)
    latest_pdf_path = result["pdf_path"]

    return {
        "message": "Slides created successfully",
        "presentation_id": result["presentation_id"],
        "pdf_resource_uri": f"file://{latest_pdf_path}",
        "chart_file_id": result.get("chart_file_id", "N/A"),
        "chart_image_url": result.get("chart_image_url", "N/A"),
        "info": result.get("info", {})
    }


@mcp.resource(uri="file://{path}")
async def serve_pdf(path: str):
    """
    Dynamic resource serving PDFs from local filesystem.
    """
    full_path = path
    if not os.path.exists(full_path):
        raise FileNotFoundError()
    with open(full_path, "rb") as f:
        data = f.read()
    return dict(
        uri=f"file://{full_path}",
        mime_type="application/pdf",
        blob=base64.b64encode(data).decode("utf-8")
    )

if __name__ == "__main__":
    import sys, traceback
    print("🚀 Starting MCP server...", file=sys.stderr)
    try:
        mcp.run(transport="streamable-http", host="127.0.0.1", port=8001)
    except Exception:
        print("❌ MCP crashed:", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)
