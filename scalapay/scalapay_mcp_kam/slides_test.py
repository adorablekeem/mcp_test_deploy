import os
import time
import logging

import GoogleApiSupport.drive as Drive
import GoogleApiSupport.slides as Slides
import matplotlib.pyplot as plt
import pandas as pd
from googleapiclient.discovery import build
from fastmcp import Context
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from mcp_use import MCPAgent, MCPClient
# Set up logging
logging.basicConfig(level=logging.DEBUG, format='[%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# Set credentials
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/etc/secrets/credentials.json"
drive_service = build("drive", "v3")


async def create_slides_wrapper(merchant_token: str, starting_date: str, end_date:str, ctx: Context | None = None) -> dict:

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
        Slides.batch_text_replace({"bot": merchant_token}, output_file_id)
        logger.info(f"Slides updated and moved: {output_file_id}")
        if ctx:
            await ctx.info("📄 Template duplicated and text replaced")
    except Exception:
        logger.exception("Slides preparation failed")
        if ctx:
            await ctx.error("❌ Slide template preparation failed")
        return {"error": "Slides preparation failed"}

    try:
        upload_result = Drive.upload_file(
            file_name="monthly_sales_profit_chart.png",
            parent_folder_id=[folder_id],
            local_file_path=chart_path
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

    image_success = False
    try:
        Slides.batch_replace_shape_with_image({"image1": direct_url, "image2": direct_url}, output_file_id)
        logger.info("Image inserted")
        if ctx:
            await ctx.info("🖼️ Chart inserted into slides")
        image_success = True
    except Exception:
        logger.exception("Image insertion failed")
        if ctx:
            await ctx.warning("⚠️ Image insertion failed")

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
        # "info": info,
        "pdf_path": pdf_path,
        "chart_file_id": chart_file_id,
        "chart_image_url": direct_url,
        "image_insertion_success": image_success,
        "presentation_id": output_file_id,
        # "alfred_result": alfred_result,
    }
