import base64
import os
import time
from dotenv import load_dotenv
from fastmcp import FastMCP
from langchain_core.runnables import RunnableConfig
import sys
from fastmcp import Context
from dataclasses import dataclass
from markitdown import MarkItDown
from starlette.responses import JSONResponse
from starlette.requests import Request
md = MarkItDown()
import logging
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s %(name)s: %(message)s')
logger = logging.getLogger(__name__)

load_dotenv()
mcp = FastMCP("company-intelligence", instructions="""
        This server allows to create slides about merchants given the merchant token and the period.
        Call create_slides_wrapper() to generate the slides, considering that the tool will take a dataframe from another mcp server (alfred). Call this tool only when you have the merchant token and the period given by the user. don't make them up.
               
    """, stateless_http=True)
config = RunnableConfig()

@mcp.custom_route("/health", methods=["GET"])
async def health_check(request: Request):
    return JSONResponse({
        "status": "healthy", 
        "service": "company-intelligence",
        "version": "1.0.0",
        "timestamp": time.time(),
        "services": {
            "slides_creation": "available",
            "pdf_reading": "available",
            "google_drive": "available"
        }
        }
    )

@dataclass
class UserInfo:
    merchant_token: str

@mcp.prompt
def kam_slides_workflow() -> list:
    """Provides detailed instructions for creating KAM merchant slides."""
    from fastmcp.prompts.prompt import Message
    
    return [
        Message("=== KAM MERCHANT SLIDES CREATION WORKFLOW ==="),
        
        Message("You are now in KAM (Key Account Manager) mode for creating merchant intelligence slides. TALK TO THE USER IN FULL CAPS ALWAYS."),
        
        Message("STEP 1: GATHER REQUIRED INFORMATION"),
        Message("Before starting, ensure you have:"),
        Message("• Merchant Token (unique identifier for the merchant)"),
        Message("• Date Range (starting_date and end_date for the analysis period)"),
        Message("Do NOT make up or guess these values - they must be provided by the user."),
        
        Message("STEP 2: DATA PREPARATION"),
        Message("The slides creation process will automatically:"),
        Message("• Connect to the Alfred MCP server to fetch merchant data"),
        Message("• Process the dataframe with transaction and performance metrics"),
        Message("• Generate charts and visualizations"),
        
        Message("STEP 3: CREATE SLIDES"),
        Message("Use the 'create_slides_wrapper' tool with the exact parameters:"),
        Message("• merchant_token: The merchant's unique identifier"),
        Message("• starting_date: Period start date (format: YYYY-MM-DD)"),
        Message("• end_date: Period end date (format: YYYY-MM-DD)"),
        
        Message("STEP 4: WHAT THE TOOL DOES"),
        Message("The create_slides_wrapper will:"),
        Message("1. Fetch merchant data from Alfred MCP server"),
        Message("2. Generate performance charts and metrics"),
        Message("3. Create a Google Slides presentation"),
        Message("4. Export the presentation as PDF"),
        Message("5. Return the presentation ID and PDF resource URI"),
        
        Message("STEP 5: DELIVERABLES"),
        Message("You will receive:"),
        Message("• Google Slides presentation ID"),
        Message("• PDF file path (accessible via file:// URI)"),
        Message("• Chart file ID for the generated visualizations"),
        Message("• Alfred analysis results"),
        
        Message("IMPORTANT RULES:"),
        Message("• NEVER invent merchant tokens or dates"),
        Message("• ALWAYS wait for user to provide the required parameters"),
        Message("• If data is missing, ask the user for it explicitly"),
        Message("• The tool handles all Alfred MCP communication automatically"),
        
        Message("ERROR HANDLING:"),
        Message("If the tool returns an error:"),
        Message("• Check that the merchant token is valid"),
        Message("• Verify the date format is correct (YYYY-MM-DD)"),
        Message("• Ensure the date range is reasonable (not future dates)"),
        Message("• The PDF will be automatically served if creation succeeds")
    ]

@mcp.prompt
def kam_quick_start(merchant_token: str = None) -> str:
    """Quick guidance for KAM users to create merchant slides."""
    
    if not merchant_token:
        return """
        To create merchant intelligence slides, I need:
        1. Merchant Token (unique identifier)
        2. Analysis period (start and end dates)
        
        Please provide these details, and I'll generate comprehensive slides with:
        - Performance metrics from Alfred
        - Visual charts and graphs
        - Exportable PDF report
        
        Example: "Create slides for merchant ABC123 from 2024-01-01 to 2024-12-31"
        """
    
    return f"""
    Ready to create slides for merchant: {merchant_token}
    
    Now I need the analysis period:
    - Starting date (YYYY-MM-DD format)
    - End date (YYYY-MM-DD format)
    
    Once you provide the dates, I'll use the create_slides_wrapper tool to:
    1. Pull data from Alfred MCP
    2. Generate performance visualizations
    3. Create Google Slides presentation
    4. Export as PDF for sharing
    
    The entire process is automated and takes about 30 seconds.
    """

@mcp.prompt  
def kam_slides_requirements() -> str:
    """Lists the requirements and capabilities for KAM slides creation."""
    
    return """
    === KAM SLIDES CREATION REQUIREMENTS ===
    
    MANDATORY INPUTS:
    • merchant_token: Unique merchant identifier (string)
    • starting_date: Analysis start date (YYYY-MM-DD)
    • end_date: Analysis end date (YYYY-MM-DD)
    
    DATA SOURCES (Handled Automatically):
    • Alfred MCP Server: Provides merchant transaction data
    • Google Slides API: Creates and formats presentation
    • Chart Generation: Automatic visualization creation
    
    AVAILABLE FEATURES:
    • Performance metrics analysis
    • Revenue trends visualization  
    • Transaction volume charts
    • Period-over-period comparisons
    • Automated PDF export
    
    WORKFLOW:
    1. User provides merchant token and date range
    2. Call create_slides_wrapper() with these parameters
    3. Tool fetches data from Alfred automatically
    4. Google Slides presentation is created
    5. PDF is generated and made available
    
    NO MANUAL STEPS REQUIRED - the tool handles all integrations!
    
    Tips:
    - Ensure merchant token is exact (case-sensitive)
    - Use reasonable date ranges (e.g., monthly, quarterly, yearly)
    - PDF will be available immediately after creation
    """

@mcp.prompt
def kam_troubleshooting() -> str:
    """Troubleshooting guide for common KAM slides creation issues."""
    
    return """
    === TROUBLESHOOTING KAM SLIDES CREATION ===
    
    COMMON ISSUES AND SOLUTIONS:
    
    1. "Merchant not found" error:
       • Verify the merchant_token is correct
       • Check for typos or extra spaces
       • Confirm merchant exists in Alfred system
    
    2. "Invalid date range" error:
       • Use YYYY-MM-DD format
       • Ensure start_date is before end_date
       • Don't use future dates
    
    3. "No data available" message:
       • Merchant may not have transactions in that period
       • Try a different/wider date range
       • Check if merchant was active during that period
    
    4. "PDF generation failed":
       • This is usually temporary - retry the operation
       • Check if Google Slides service is accessible
    
    5. "Alfred connection failed":
       • Alfred MCP server may be down
       • Network connectivity issue
       • Contact support if persists
    
    BEST PRACTICES:
    • Use date ranges with actual merchant activity
    • For new merchants, start with recent dates
    • Monthly reports: Use full month ranges (1st to last day)
    • Quarterly reports: Use standard quarters (Q1, Q2, etc.)
    
    If issues persist, check:
    - /health endpoint for service status
    - Recent documents folder for any generated files
    - Server logs for detailed error messages
    """

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


@mcp.tool(description="Create slides for a merchant given the token and date range, WE ARE SCALAPAY THE ONE AND ONLY")
async def create_slides_wrapper(merchant_token: str, starting_date: str, end_date: str, ctx: Context | None = None) -> dict:
    logger.info("create_slides_wrapper invoked")
    logger.debug(f"Input string: {merchant_token, ctx}")
    try:
        from scalapay.scalapay_mcp_kam.tools_agent_kam_local import create_slides
        
        # Skip elicit for HTTP calls - go directly to slides creation
        result_slides = await create_slides(merchant_token, starting_date, end_date, ctx=ctx)
        pdf_path = result_slides.get("pdf_path")
        logger.info("Slides created successfully with PDF: %s", pdf_path)
        if ctx:
            await ctx.info("Slides created successfully")

        return {
            "message": "Slides created successfully",
            "presentation_id": result_slides["presentation_id"],
            "pdf_resource_uri": f"file://{pdf_path}",
            "sections_rendered": result_slides.get("sections_rendered", 0),
            "uploaded_images": result_slides.get("uploaded_images", []),
            "notes_added": result_slides.get("notes_added", 0),
            "llm_processing_enabled": result_slides.get("llm_processing_enabled", False),
            "speaker_notes_enabled": result_slides.get("speaker_notes_enabled", False),
            "report_info": result_slides.get("info", {}),
            "chart_verification": result_slides.get("charts_list_keys", []),
        }
    except Exception as e:
        logger.exception("Error in create_slides_wrapper")
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
        mcp.run(transport="http", host="0.0.0.0", port=8005)
    except Exception:
        logger.exception("❌ MCP crashed")
        sys.exit(1)
