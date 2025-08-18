from dataclasses import dataclass
import os
import time
import logging
import asyncio
import GoogleApiSupport.drive as Drive
import GoogleApiSupport.slides as Slides
import matplotlib.pyplot as plt
import pandas as pd
from googleapiclient.discovery import build
from fastmcp import Context
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from mcp_use import MCPAgent, MCPClient
from googleapiclient.http import MediaIoBaseDownload
import io
from plot_chart import plot_monthly_sales_chart
from prompts.charts_prompt import MONTHLY_SALES_CHART_PROMPT, SLIDES_GENERATION_PROMPT
import ast

# Set up logging
logging.basicConfig(level=logging.DEBUG, format='[%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# Set credentials
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "./scalapay/scalapay_mcp_kam/credentials.json"
drive_service = build("drive", "v3")

@dataclass
class SlidesContent:
    paragraph: str = ""
    structured_data: dict = None

async def create_slides(string: str, starting_date: str, end_date: str, ctx: Context | None = None) -> dict:
    logger.debug("Starting create_slides function")
    logger.debug(f"Input string: {string}")
    if ctx:
        await ctx.info("🚀 Starting slide generation")

    load_dotenv()

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
    agent = MCPAgent(llm=llm, client=client, max_steps=30, verbose=True)

    # Run the query
    alfred_result = await agent.run(
        MONTHLY_SALES_CHART_PROMPT.format(
            merchant_token=string,
        ),
        max_steps=30
    )

    # Save result to a file in /tmp
    output_path = "./tmp/alfred_result.txt"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(str(alfred_result))

    print(f"\nResult saved to: {output_path}")
    logger.debug("DataFrame created successfully")

    chart_path = "/tmp/monthly_sales_profit_chart.png"
    try:
        llm = llm.with_structured_output(SlidesContent)
        try:
            resp = await llm.ainvoke(SLIDES_GENERATION_PROMPT.format(
                alfred_result=alfred_result
            ))
        except Exception as e:
            logger.exception("Error invoking LLM for slides generation")
            if ctx:
                await ctx.error(f"❌ LLM invocation failed: {e}")
            return {"error": "LLM invocation failed"}       
        print(f"resp result is: {resp.get('structured_data', {})}")
        raw_data = resp.get("structured_data", {}).get("months", {})

        # Normalize: convert year keys to int
        normalized_data = {
            month: {int(year): val for year, val in yearly_data.items()}
            for month, yearly_data in raw_data.items()
        }
        print(f"normalized_data is: {normalized_data}")
        chart_path, width_px, height_px = plot_monthly_sales_chart(normalized_data, output_path=chart_path)
        print(f"Chart size: {width_px}px × {height_px}px")

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
        Slides.batch_text_replace({"monthly_sales_paragraph": resp.get('paragraph', '')}, output_file_id)
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
        Slides.batch_replace_shape_with_image(
            {"monthly_sales_chart": direct_url},
            output_file_id,
            position=(144, 108),  # 2in X, 1.5in Y in pt
            size=(400, 300)       # 400pt wide, 300pt high
        )
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
        request = drive_service.files().export_media(fileId=output_file_id, mimeType="application/pdf")
        fh = io.FileIO(pdf_path, "wb")
        downloader = MediaIoBaseDownload(fh, request)
        
        done = False
        while not done:
            status, done = downloader.next_chunk()
            logger.debug(f"PDF Download Progress: {int(status.progress() * 100)}%")

        logger.info(f"PDF exported to: {pdf_path}")
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
        "alfred_result": alfred_result,
        "pdf_path": pdf_path,
        "chart_file_id": chart_file_id,
        "chart_image_url": direct_url,
        "image_insertion_success": image_success,
        "presentation_id": output_file_id,
    }


"""
# 🔧 ENTRY POINT
def main():
    print("[DEBUG] Starting main function...")
    try:
        result = asyncio.run(create_slides("Here's your automated update!"))
        print("\n[🎉] Final Result:")
        for k, v in result.items():
            print(f"  {k}: {v}")
    except Exception as e:
        print(f"[✗] Main function failed: {e}")
        print(f"[DEBUG] Error type: {type(e).__name__}")

if __name__ == "__main__":
    main()
"""