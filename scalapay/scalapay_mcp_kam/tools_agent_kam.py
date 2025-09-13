import logging
import os
import time

import GoogleApiSupport.drive as Drive
import GoogleApiSupport.slides as Slides
import matplotlib.pyplot as plt
import pandas as pd
from dotenv import load_dotenv
from fastmcp import Context
from googleapiclient.discovery import build
from langchain_openai import ChatOpenAI
from mcp_use import MCPAgent, MCPClient

# Import our simple batch operations
from .simple_batch_operations import batch_replace_with_positioning

# Set up logging
logging.basicConfig(level=logging.DEBUG, format="[%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Set credentials
# os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/etc/secrets/credentials.json"
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "./scalapay/scalapay_mcp_kam/credentials.json"

drive_service = build("drive", "v3")


async def create_slides(merchant_token: str, starting_date: str, end_date: str, ctx: Context | None = None) -> dict:
    logger.debug("Starting create_slides function")
    logger.debug(f"Input string: {merchant_token}")
    if ctx:
        await ctx.info("🚀 Starting slide generation")

    load_dotenv()
    """
    config = {
        "mcpServers": {
            "http": {
                "url": "http://127.0.0.1:8000/mcp"
            }
        }
    }

    # Create MCPClient from config file
    client = MCPClient.from_dict(config)

    # Create LLM
    llm = ChatOpenAI(model="gpt-4o")

    # Create agent with the client
    agent = MCPAgent(llm=llm, client=client, max_steps=30)

    # Run the query
    alfred_result = await agent.run(
        "output a dataframe for merchant Zalando in the last month",
        max_steps=30,
    )
    print(f"\nResult: {alfred_result}")
    """
    # Static data
    data = {
        "Month": ["Jan", "Feb", "Mar", "Apr", "May", "Jun"],
        "Sales": [4174, 4507, 1860, 2294, 2130, 3468],
        "Profit": [1244, 321, 666, 1438, 530, 892],
    }
    df = pd.DataFrame(data)
    logger.debug("DataFrame created successfully")

    chart_path = "/tmp/monthly_sales_profit_chart.png"
    try:
        plt.figure(figsize=(8, 5))
        plt.plot(df["Month"], df["Sales"], marker="o", label="Sales")
        plt.plot(df["Month"], df["Profit"], marker="o", label="Profit")
        plt.title("Monthly Sales and Profit", fontsize=16)
        plt.xlabel("Month", fontsize=12)
        plt.ylabel("Amount", fontsize=12)
        plt.legend()
        plt.savefig(chart_path, dpi=300)
        plt.close()
        logger.info(f"Chart saved to: {chart_path}")
        if ctx:
            await ctx.info("📈 Chart image generated")

    except Exception:
        logger.exception("Chart creation failed")
        if ctx:
            await ctx.error("❌ Chart creation failed")
        return {"error": "Chart creation failed"}

    presentation_id = "1hDkICKx4D3jHdxky_3_1iJcPFVQFxTkvlH7mVSFCx_o"
    folder_id = "1x03ugPUeGSsLYY2kH-FsNC9_f_M6iLGL"
    try:
        output_file_id = Drive.copy_file(presentation_id, "final_presentation")
        Drive.move_file(output_file_id, folder_id)
        logger.info(f"Slides copied and moved: {output_file_id}")
        if ctx:
            await ctx.info("📄 Template duplicated")
    except Exception:
        logger.exception("Slides preparation failed")
        if ctx:
            await ctx.error("❌ Slide template preparation failed")
        return {"error": "Slides preparation failed"}

    try:
        upload_result = Drive.upload_file(
            file_name="monthly_sales_profit_chart.png", parent_folder_id=[folder_id], local_file_path=chart_path
        )
        chart_file_id = upload_result.get("file_id")
        logger.info(f"Chart uploaded: {chart_file_id}")
        if ctx:
            await ctx.info("☁️ Chart uploaded to Drive")
        if not chart_file_id:
            return {"error": "Upload failed - no file ID"}
    except Exception:
        logger.exception("Upload failed")
        if ctx:
            await ctx.error("❌ Upload to Drive failed")
        return {"error": "Upload failed"}

    direct_url = f"https://drive.google.com/uc?export=view&id={chart_file_id}"

    # Use simple batch operations with original translateX/translateY positioning
    image_success = False
    try:
        # Text and image replacements with positioning (original pattern)
        text_mapping = {"bot": merchant_token}
        image_mapping = {"image1": direct_url, "image2": direct_url}
        
        # Original positioning logic - simple translateX/translateY in points
        positioning = {
            "image1": {
                "translateX": 130,  # X position in points
                "translateY": 250,  # Y position in points
                "scaleX": 1.0,
                "scaleY": 1.0,
                "unit": "PT"
            },
            "image2": {
                "translateX": 400,  # Second image to the right
                "translateY": 250,  # Same Y position
                "scaleX": 1.0,
                "scaleY": 1.0, 
                "unit": "PT"
            }
        }
        
        await batch_replace_with_positioning(
            text_mapping=text_mapping,
            image_mapping=image_mapping,
            presentation_id=output_file_id,
            transform_configs=positioning,
            ctx=ctx
        )
        
        logger.info("Text and images inserted with positioning")
        if ctx:
            await ctx.info("🖼️ Charts inserted with original positioning logic")
        image_success = True
    except Exception:
        logger.exception("Batch replacement failed")
        if ctx:
            await ctx.warning("⚠️ Batch replacement failed")

    pdf_path = None
    try:
        info = Slides.get_presentation_info(output_file_id)
        pdf_path = f"/tmp/{output_file_id}.pdf"
        Slides.download_presentation_as_pdf(drive_service, output_file_id, pdf_path)
        logger.info("PDF exported")
        if ctx:
            await ctx.info("📥 Slides exported as PDF")
    except Exception:
        logger.exception("PDF export failed")
        if ctx:
            await ctx.warning("⚠️ PDF export failed")

    if ctx:
        await ctx.info("✅ Slide generation complete")

    return {
        "info": info,
        "pdf_path": pdf_path,
        "chart_file_id": chart_file_id,
        "chart_image_url": direct_url,
        "image_insertion_success": image_success,
        "presentation_id": output_file_id,
        # "alfred_result": alfred_result,
    }
