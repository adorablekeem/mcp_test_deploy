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
from tools.alfred_automation import mcp_tool_run
from googleapiclient.http import MediaIoBaseDownload
import io
from prompts.charts_prompt import GENERAL_CHART_PROMPT, SLIDES_GENERATION_PROMPT, STRUCTURED_CHART_SCHEMA_PROMPT
from agent_matplot import mcp_matplot_run
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError
import unicodedata
import string
from typing import Dict, Any, List, Optional
from GoogleApiSupport.slides import Transform
from GoogleApiSupport.slides import execute_batch_update
from GoogleApiSupport.slides import get_all_shapes_placeholders
from test_fill_template_sections import make_all_shapes_normal_weight, upload_png, copy_file, move_file, batch_text_replace, build_text_and_image_maps, batch_replace_shapes_with_images_and_resize, make_file_public

# Set up logging
logging.basicConfig(level=logging.DEBUG, format='[%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# Set credentials
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "./scalapay/scalapay_mcp_kam/credentials.json"
drive_service = build("drive", "v3")
slides_service = build("slides", "v1")

def _slug(s: str, max_len: int = 40) -> str:
    s = "".join(c for c in unicodedata.normalize("NFKD", s) if ord(c) < 128)
    s = s.lower().strip()
    valid = f"{string.ascii_lowercase}{string.digits}-_"
    s = "".join(ch if ch in valid else "-" for ch in s.replace(" ", "-"))
    while "--" in s:
        s = s.replace("--", "-")
    return s[:max_len] or "section"

# ---------- drive helpers (upload + permissions + url + folder handling) ----------
def resolve_shortcut(file_id: str) -> str:
    f = drive_service.files().get(
        fileId=file_id,
        fields="id,mimeType,shortcutDetails",
        supportsAllDrives=True,
    ).execute()
    if f.get("mimeType") == "application/vnd.google-apps.shortcut":
        return f["shortcutDetails"]["targetId"]
    return file_id

def upload_chart_png(local_path: str, *, name: str, parent_folder_id: str) -> str:
    parent = resolve_shortcut(parent_folder_id) if parent_folder_id else None
    media = MediaFileUpload(local_path, mimetype="image/png", resumable=True)
    body = {"name": name if name.endswith(".png") else f"{name}.png", "mimeType": "image/png"}
    if parent: body["parents"] = [parent]
    f = drive_service.files().create(
        body=body, media_body=media, fields="id", supportsAllDrives=True
    ).execute()
    return f["id"]


def drive_direct_view_url(file_id: str) -> str:
    return f"https://drive.google.com/uc?export=view&id={file_id}"

def tokens_for_title(title: str) -> dict:
    """
    Given a section title, produce the three placeholders:
      {{<slug>_title}}, {{<slug>_paragraph}}, {{<slug>_chart}}
    """
    base = _slug(title)
    return {
        "title_token": f"{{{{{base}_title}}}}",
        "paragraph_token": f"{{{{{base}_paragraph}}}}",
        "image_token": f"{{{{{base}_chart}}}}",
        "base": base,
    }

# ---------- batch replace builder ----------
def build_batch_replace_requests(sections: list, folder_id: str | None):
    """
    For each section:
      - Upload PNG to Drive, make public
      - Create 3 requests: title text, paragraph text, replace shape with image
    Returns (requests, uploads) where uploads contains info you might reuse (e.g. TOC or logging)
    """
    requests = []
    uploads = []

    for sec in sections:
        toks = tokens_for_title(sec["title"])

        # Upload image
        pretty_name = f"{toks['base']}_{int(time.time())}.png"
        file_id = upload_chart_png(sec["chart_path"], name=pretty_name, parent_folder_id=folder_id)
        make_file_public(file_id)
        img_url = drive_direct_view_url(file_id)
        uploads.append({"title": sec["title"], "file_id": file_id, "image_url": img_url})

        # Replace title (if token exists in template)
        requests.append({
            "replaceAllText": {
                "containsText": {"text": toks["title_token"], "matchCase": False},
                "replaceText": sec["title"]
            }
        })

        # Replace paragraph
        requests.append({
            "replaceAllText": {
                "containsText": {"text": toks["paragraph_token"], "matchCase": False},
                "replaceText": sec["paragraph"]
            }
        })

        # Replace shape containing image token with the actual image
        requests.append({
            "replaceAllShapesWithImage": {
                "containsText": {"text": toks["image_token"], "matchCase": False},
                "imageUrl": img_url,
                "replaceMethod": "CENTER_INSIDE"  # or "STRETCH"
            }
        })

    return requests, uploads

# ---------- slide export (pdf) ----------
def export_presentation_pdf(presentation_id: str, out_path: str) -> str:
    req = drive_service.files().export_media(fileId=presentation_id, mimeType="application/pdf")
    fh = io.FileIO(out_path, "wb")
    downloader = MediaIoBaseDownload(fh, req)
    done = False
    while not done:
        status, done = downloader.next_chunk()
    return out_path


def build_section_slide(
    presentation_id: str,
    *,
    title: str,
    paragraph: str,
    image_url: str,
    slide_index: int | None = 1,
    slide_id: str | None = None,
) -> str:
    slide_id = slide_id or f"slide_{int(time.time())}"
    title_id = f"title_{slide_id}"
    para_id  = f"para_{slide_id}"
    img_id   = f"img_{slide_id}"

    # 👇 Use a layout that exists in your deck (from your list)
    LAYOUT_ID = "p84"  # LATERAL BOX (For Charts) - Blue

    requests = [
        {
            "createSlide": {
                "objectId": slide_id,
                "insertionIndex": slide_index if slide_index is not None else 1,
                "slideLayoutReference": {"layoutId": LAYOUT_ID},
            }
        },
        # Your own text boxes (left) + image (right) – keeps it robust regardless of placeholders
        {"createShape": {
            "objectId": title_id,
            "shapeType": "TEXT_BOX",
            "elementProperties": {
                "pageObjectId": slide_id,
                "size": {"width": {"magnitude": 896, "unit": "PT"}, "height": {"magnitude": 48, "unit": "PT"}},
                "transform": {"scaleX": 1, "scaleY": 1, "translateX": 32, "translateY": 32, "unit": "PT"},
            }
        }},
        {"insertText": {"objectId": title_id, "text": title}},
        {"updateTextStyle": {"objectId": title_id, "style": {"bold": True, "fontSize": {"magnitude": 24, "unit": "PT"}}, "fields": "bold,fontSize"}},

        {"createShape": {
            "objectId": para_id,
            "shapeType": "TEXT_BOX",
            "elementProperties": {
                "pageObjectId": slide_id,
                "size": {"width": {"magnitude": 416, "unit": "PT"}, "height": {"magnitude": 360, "unit": "PT"}},
                "transform": {"scaleX": 1, "scaleY": 1, "translateX": 32, "translateY": 96, "unit": "PT"},
            }
        }},
        {"insertText": {"objectId": para_id, "text": paragraph}},
        {"updateTextStyle": {"objectId": para_id, "style": {"fontSize": {"magnitude": 12, "unit": "PT"}}, "fields": "fontSize"}},

        {"createImage": {
            "objectId": img_id,
            "url": image_url,
            "elementProperties": {
                "pageObjectId": slide_id,
                "size": {"width": {"magnitude": 480, "unit": "PT"}, "height": {"magnitude": 360, "unit": "PT"}},
                "transform": {"scaleX": 1, "scaleY": 1, "translateX": 512, "translateY": 96, "unit": "PT"},
            }
        }},
    ]

    slides_service.presentations().batchUpdate(
        presentationId=presentation_id, body={"requests": requests}
    ).execute()
    return slide_id

def iter_sections(result_obj: dict) -> list[dict]:
    """
    Normalize your results dict into a list of {key, title, paragraph, chart_path}.
    Falls back across keys safely.
    """
    sections = []
    for key, val in result_obj.items():
        try:
            title = key
            paragraph = (
                val.get("slides_struct", {}).get("paragraph")
                or val.get("paragraph")
                or val.get("alfred_raw", "")
            )
            # Prefer agent-generated chart path, else your precomputed chart_path
            chart_path = (
                val.get("matplot_raw", {}).get("chart_path")
                or val.get("chart_path")
            )
            # Only include sections with an image path and some text
            if chart_path and isinstance(paragraph, str) and paragraph.strip():
                sections.append({
                    "key": key,
                    "title": title,
                    "paragraph": paragraph.strip(),
                    "chart_path": chart_path,
                })
        except Exception:
            continue
    return sections

import time
import unicodedata
import string
import logging

logger = logging.getLogger(__name__)

# ---------- helpers ----------
def _slug(s: str, max_len: int = 60) -> str:
    # ASCII fold
    s = "".join(c for c in unicodedata.normalize("NFKD", s) if ord(c) < 128)
    s = s.lower().strip()
    # replace spaces and invalid chars with underscore
    valid = f"{string.ascii_lowercase}{string.digits}_"
    s = s.replace(" ", "_")
    s = "".join(ch if ch in valid else "_" for ch in s)
    # collapse repeats
    while "__" in s:
        s = s.replace("__", "_")
    s = s.strip("_")
    return s[:max_len] or "section"

def _pick_paragraph(section_dict: dict) -> str | None:
    return (
        section_dict.get("slides_struct", {}).get("paragraph")
        or section_dict.get("paragraph")
        or section_dict.get("alfred_raw")  # last resort, might be verbose
    )

def _pick_chart_path(section_dict: dict) -> str | None:
    return (
        section_dict.get("matplot_raw", {}).get("chart_path")
        or section_dict.get("chart_path")
    )

# ---------- main filler ----------

async def fill_template_for_all_sections_new(
    drive, slides,
    results: Dict[str, Any],
    *,
    template_id: str,
    folder_id: Optional[str],
    verbose: bool = False,
):
    if verbose:
        logger.setLevel(logging.DEBUG)

    # 0) build maps
    text_map, sections = build_text_and_image_maps(results)
    logger.info("Renderable sections: %d", len(sections))
    print("Text map is: ", text_map)

    # 1) copy + move
    out_name = f"final_presentation_{int(time.time())}"
    presentation_id = copy_file(drive, template_id, out_name)
    logger.info("Copied template -> %s", presentation_id)
    if folder_id:
        try:
            move_file(drive, presentation_id, folder_id)
            logger.info("Moved to folder %s", folder_id)
        except Exception as e:
            logger.warning(f"Move failed (continuing): {e}")

    # 2) upload images + build image_map
    image_map = {}
    uploads = []
    for sec in sections:
        slug = _slug(sec["title"])
        pretty_name = f"{slug}_{int(time.time())}.png"
        file_id = upload_png(drive, sec["chart_path"], name=pretty_name, parent_folder_id=folder_id)
        try:
            make_file_public(drive, file_id)
        except Exception as e:
            logger.warning(f"make_file_public failed ({file_id}): {e}")

        url = f"https://drive.google.com/uc?export=view&id={file_id}"
        image_map[f"{{{{{slug}_chart}}}}"] = url
        uploads.append({"title": sec["title"], "file_id": file_id, "image_url": url})

    print("image map is: ", image_map)
    logger.info("Uploaded %d chart images", len(uploads))
    logger.debug("First 5 uploads: %s", uploads[:5])

    # 3) replace text
    logger.info("Replacing %d text tokens…", len(text_map))
    logger.debug("Some text tokens: %s", list(text_map.items())[:5])
    # Make all text shapes in presentation normal weight
    make_all_shapes_normal_weight(presentation_id)
    batch_text_replace(slides, presentation_id, text_map)
    
    
    # 4) replace images
    logger.info("Replacing %d image tokens…", len(image_map))
    logger.debug("Some image tokens: %s", list(image_map.items())[:5])
    batch_replace_shapes_with_images_and_resize(
    slides,
    presentation_id,
    image_map,
    resize={"mode": "ABSOLUTE", "scaleX": 120, "scaleY": 120, "unit": "PT", "translateX": 130, "translateY": 250},
        replace_method="CENTER_INSIDE",  # or "CENTER_CROP"
    )


    return {
        "presentation_id": presentation_id,
        "sections_rendered": len(sections),
        "uploaded_images": uploads,
    }
async def create_slides(merchant_token: str, starting_date: str, end_date: str, ctx: Context | None = None) -> dict:
    logger.debug("Starting create_slides function")
    logger.debug(f"Input string: {merchant_token}")
    if ctx:
        await ctx.info("🚀 Starting slide generation")
    
    load_dotenv()

    # Run the query
    results = await mcp_tool_run(
        requests_list=[
            "monthly sales over time",
            "monthly sales by product type over time",
            "monthly orders by user type",
            "AOV",
            "scalapay users demographic in percentages",
            "orders by product type (i.e. pay in 3, pay in 4)",
            "AOV by product type (i.e. pay in 3, pay in 4)"
        ],
        merchant_token=merchant_token,
        starting_date=starting_date,
        end_date=end_date,
        chart_prompt_template=GENERAL_CHART_PROMPT,
    )
    print(f"\n[DEBUG] Raw Results: {results}")


    charts_list = await mcp_matplot_run(
    results,  # This is the results_dict parameter (positional)
    matplot_url="http://localhost:8010/mcp",
    server_id="MatPlotAgent",
    operation="generate_chart_simple",
    model_type="gpt-4o",
    verbose=True,
    transport="http"
)

    print(f"\n[DEBUG] Charts List is: {charts_list}")
    logger.debug(f"[DEBUG] Charts list is: {charts_list}")

    # ✅ pick one chart path to actually use later
    chart_path = charts_list.get("monthly sales over time", {}).get("chart_path")

    # fallback: pick the first available chart_path if the preferred one is missing
    if not chart_path:
        for k, v in charts_list.items():
            if isinstance(v, dict) and v.get("chart_path"):
                chart_path = v["chart_path"]
                break

    if not chart_path:
        raise RuntimeError("No chart_path returned by MatPlotAgent")
    # logger.debug(f"[CHART-ROUTER] normalized_data keys: {list(normalized_data.keys())}")



    
    # ---------- AUTO intent (no chart_request passed) ----------
    _auto_request = f'Compare monthly sales across years. Title: "Monthly Sales {starting_date}–{end_date}"'

    # route & render (the router saves the file and returns its path)
    try:
        """
        print(f"The description of the data is '[{resp.get('paragraph', '')}]'")
        agent_chart_path, spec = generate_chart_from_intent(resp.get("paragraph", ""), normalized_data)
        logger.info(f"[CHART-ROUTER] Chosen spec: {spec}")
        chart_path = agent_chart_path
        print(f"✓ Chart saved via router to: {chart_path}")
        """
    except Exception as e:
        logger.exception(f"Chart router failed, falling back to default plotter: {e}")
        # fallback to your existing plotter
        chart_path = "/tmp/monthly_sales_profit_chart.png"
        # chart_path, width_px, height_px = plot_monthly_sales_chart(normalized_data, output_path=chart_path)

        logger.info(f"Chart saved to: {chart_path}")

    try:
        # 2) Duplicate template and (optionally) move to folder
        presentation_id = "1hDkICKx4D3jHdxky_3_1iJcPFVQFxTkvlH7mVSFCx_o"
        folder_id = "1x03ugPUeGSsLYY2kH-FsNC9_f_M6iLGL"  # e.g. "1x03ugPUeGSsLYY2kH-FsNC9_f_M6iLGL" or None

        # Use charts_list (it already contains chart_path + paragraph per section)
        final = await fill_template_for_all_sections_new(
            drive_service, slides_service,
            charts_list,
            template_id=presentation_id,
            folder_id=folder_id,
        )
        pres_id = final["presentation_id"]
        if ctx:
            await ctx.info("📄 Template duplicated and all tokens replaced")
    except Exception:
        logger.exception("Slides preparation failed")
        if ctx:
            await ctx.error("❌ Slide template preparation failed")
        return {"error": "Slides preparation failed"}

    # 3) Export PDF
    pdf_path = f"/tmp/{pres_id}.pdf"
    try:
        export_presentation_pdf(pres_id, pdf_path)
        if ctx:
            await ctx.info("📥 Slides exported as PDF")
    except Exception:
        logger.exception("PDF export failed")
        if ctx:
            await ctx.warning("⚠️ PDF export failed")
        pdf_path = None

    # 4) Return a tidy summary
    return {
        "presentation_id": pres_id,
        "sections_rendered": final.get("sections_rendered", 0),
        "uploaded_images": final.get("uploaded_images", []),
        "pdf_path": pdf_path,
        # keep these if you still want the raw inputs/outputs around:
        "charts_list_keys": list(charts_list.keys()),
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