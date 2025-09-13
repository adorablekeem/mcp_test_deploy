import asyncio
import io
import logging
import os
import string
import time
import unicodedata
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import GoogleApiSupport.drive as Drive
import GoogleApiSupport.slides as Slides
import matplotlib.pyplot as plt
import pandas as pd
from dotenv import load_dotenv
from fastmcp import Context
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
from GoogleApiSupport.slides import Transform, execute_batch_update, get_all_shapes_placeholders
from langchain_openai import ChatOpenAI
from scalapay.scalapay_mcp_kam.agents.agent_alfred import mcp_tool_run
from scalapay.scalapay_mcp_kam.agents.agent_matplot import mcp_matplot_run

# Clean positioning system integration
from scalapay.scalapay_mcp_kam.positioning import configure_positioning, get_positioning_status
from scalapay.scalapay_mcp_kam.positioning import health_check as positioning_health_check
from scalapay.scalapay_mcp_kam.positioning.clean_replacements import fill_template_with_clean_positioning
from scalapay.scalapay_mcp_kam.prompts.charts_prompt import (
    GENERAL_CHART_PROMPT,
    SLIDES_GENERATION_PROMPT,
    STRUCTURED_CHART_SCHEMA_PROMPT,
)
from scalapay.scalapay_mcp_kam.tests.test_fill_template_sections import (
    add_speaker_notes_to_slides,
    batch_replace_shapes_with_images_and_resize,
    batch_text_replace,
    build_text_and_image_maps,
    build_text_and_image_maps_enhanced,
    copy_file,
    make_all_shapes_normal_weight,
    make_file_public,
    move_file,
    upload_png,
)

# Set up logging
logging.basicConfig(level=logging.DEBUG, format="[%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Set credentials
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/Users/keem.adorable@scalapay.com/scalapay/scalapay_mcp_kam/scalapay/scalapay_mcp_kam/credentials.json"
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
    f = (
        drive_service.files()
        .get(
            fileId=file_id,
            fields="id,mimeType,shortcutDetails",
            supportsAllDrives=True,
        )
        .execute()
    )
    if f.get("mimeType") == "application/vnd.google-apps.shortcut":
        return f["shortcutDetails"]["targetId"]
    return file_id


def upload_chart_png(local_path: str, *, name: str, parent_folder_id: str) -> str:
    parent = resolve_shortcut(parent_folder_id) if parent_folder_id else None
    media = MediaFileUpload(local_path, mimetype="image/png", resumable=True)
    body = {"name": name if name.endswith(".png") else f"{name}.png", "mimeType": "image/png"}
    if parent:
        body["parents"] = [parent]
    f = drive_service.files().create(body=body, media_body=media, fields="id", supportsAllDrives=True).execute()
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
        requests.append(
            {
                "replaceAllText": {
                    "containsText": {"text": toks["title_token"], "matchCase": False},
                    "replaceText": sec["title"],
                }
            }
        )

        # Replace paragraph
        requests.append(
            {
                "replaceAllText": {
                    "containsText": {"text": toks["paragraph_token"], "matchCase": False},
                    "replaceText": sec["paragraph"],
                }
            }
        )

        # Replace shape containing image token with the actual image
        requests.append(
            {
                "replaceAllShapesWithImage": {
                    "containsText": {"text": toks["image_token"], "matchCase": False},
                    "imageUrl": img_url,
                    "replaceMethod": "CENTER_INSIDE",  # or "STRETCH"
                }
            }
        )

    return requests, uploads


# ---------- slide export (pdf) ----------
def export_presentation_pdf(presentation_id: str, out_path: str) -> str:
    """
    Export a Google Slides presentation as PDF.

    Args:
        presentation_id: The ID of the presentation to export
        out_path: Path where to save the PDF file

    Returns:
        Path to the saved PDF file

    Raises:
        Exception: If the presentation doesn't exist or export fails
    """
    try:
        logger.info(f"Exporting presentation {presentation_id} to PDF: {out_path}")

        # Check if presentation exists first
        try:
            drive_service.files().get(fileId=presentation_id, fields="id,name").execute()
        except HttpError as e:
            if e.resp.status == 404:
                raise Exception(f"Presentation not found: {presentation_id}")
            else:
                raise Exception(f"Error accessing presentation {presentation_id}: {e}")

        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)

        # Export the presentation as PDF
        req = drive_service.files().export_media(fileId=presentation_id, mimeType="application/pdf")
        fh = io.FileIO(out_path, "wb")
        downloader = MediaIoBaseDownload(fh, req)
        done = False

        while not done:
            status, done = downloader.next_chunk()
            if status:
                logger.debug(f"PDF export progress: {int(status.progress() * 100)}%")

        fh.close()

        # Verify the file was created and has content
        if not os.path.exists(out_path):
            raise Exception(f"PDF file was not created: {out_path}")

        file_size = os.path.getsize(out_path)
        if file_size == 0:
            raise Exception(f"PDF file is empty: {out_path}")

        logger.info(f"PDF exported successfully: {out_path} ({file_size} bytes)")
        return out_path

    except Exception as e:
        logger.error(f"PDF export failed for presentation {presentation_id}: {e}")

        # Clean up partial file if it exists
        if os.path.exists(out_path):
            try:
                os.remove(out_path)
                logger.debug(f"Cleaned up partial PDF file: {out_path}")
            except:
                pass

        raise


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
    para_id = f"para_{slide_id}"
    img_id = f"img_{slide_id}"

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
        {
            "createShape": {
                "objectId": title_id,
                "shapeType": "TEXT_BOX",
                "elementProperties": {
                    "pageObjectId": slide_id,
                    "size": {"width": {"magnitude": 896, "unit": "PT"}, "height": {"magnitude": 48, "unit": "PT"}},
                    "transform": {"scaleX": 1, "scaleY": 1, "translateX": 32, "translateY": 32, "unit": "PT"},
                },
            }
        },
        {"insertText": {"objectId": title_id, "text": title}},
        {
            "updateTextStyle": {
                "objectId": title_id,
                "style": {"bold": True, "fontSize": {"magnitude": 24, "unit": "PT"}},
                "fields": "bold,fontSize",
            }
        },
        {
            "createShape": {
                "objectId": para_id,
                "shapeType": "TEXT_BOX",
                "elementProperties": {
                    "pageObjectId": slide_id,
                    "size": {"width": {"magnitude": 416, "unit": "PT"}, "height": {"magnitude": 360, "unit": "PT"}},
                    "transform": {"scaleX": 1, "scaleY": 1, "translateX": 32, "translateY": 96, "unit": "PT"},
                },
            }
        },
        {"insertText": {"objectId": para_id, "text": paragraph}},
        {
            "updateTextStyle": {
                "objectId": para_id,
                "style": {"fontSize": {"magnitude": 12, "unit": "PT"}},
                "fields": "fontSize",
            }
        },
        {
            "createImage": {
                "objectId": img_id,
                "url": image_url,
                "elementProperties": {
                    "pageObjectId": slide_id,
                    "size": {"width": {"magnitude": 480, "unit": "PT"}, "height": {"magnitude": 360, "unit": "PT"}},
                    "transform": {"scaleX": 1, "scaleY": 1, "translateX": 512, "translateY": 96, "unit": "PT"},
                },
            }
        },
    ]

    slides_service.presentations().batchUpdate(presentationId=presentation_id, body={"requests": requests}).execute()
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
                val.get("slides_struct", {}).get("paragraph") or val.get("paragraph") or val.get("alfred_raw", "")
            )
            # Prefer agent-generated chart path, else your precomputed chart_path
            chart_path = val.get("matplot_raw", {}).get("chart_path") or val.get("chart_path")
            # Only include sections with an image path and some text
            if chart_path and isinstance(paragraph, str) and paragraph.strip():
                sections.append(
                    {
                        "key": key,
                        "title": title,
                        "paragraph": paragraph.strip(),
                        "chart_path": chart_path,
                    }
                )
        except Exception:
            continue
    return sections


import logging
import string
import time
import unicodedata

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
    return section_dict.get("matplot_raw", {}).get("chart_path") or section_dict.get("chart_path")


# ---------- main filler ----------


async def fill_template_for_all_sections_new(
    drive,
    slides,
    results: Dict[str, Any],
    *,
    template_id: str,
    folder_id: Optional[str],
    resize: dict | None = None,
    resize_map: dict[str, dict] | None = None,
):

    # 0) build maps with slug validation
    logger.info("Input results structure: %s", str(results)[:1000] + "..." if len(str(results)) > 1000 else str(results))
    text_map, sections = build_text_and_image_maps(results, template_id)
    logger.info("Renderable sections: %d", len(sections))
    print("Text map is: ", text_map)

    # Debug slug mapping validation
    from scalapay.scalapay_mcp_kam.utils.slug_validation import debug_slug_mapping

    validation_report = debug_slug_mapping(results, template_id)
    logger.info(f"Slug validation success rate: {validation_report['success_rate']:.1%}")

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

    # 2) upload images + build image_map with validated slugs
    from scalapay.scalapay_mcp_kam.utils.slug_validation import SlugMapper

    slug_mapper = SlugMapper(template_id)

    image_map = {}
    uploads = []
    for sec in sections:
        slug = slug_mapper.get_slug(sec["title"])
        pretty_name = f"{slug}_{int(time.time())}.png"
        file_id = upload_png(drive, sec["chart_path"], name=pretty_name, parent_folder_id=folder_id)
        try:
            make_file_public(drive, file_id)
        except Exception as e:
            logger.warning(f"make_file_public failed ({file_id}): {e}")

        url = f"https://drive.google.com/uc?export=view&id={file_id}"
        image_map["{{" + f"{slug}_chart" + "}}"] = url
        uploads.append({"title": sec["title"], "file_id": file_id, "image_url": url, "slug": slug})

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
        replace_method="CENTER_INSIDE",  # or CENTER_CROP, etc.
        resize=resize,           # global fallback
        resize_map=resize_map,     # per-token overrides
    )


    return {
        "presentation_id": presentation_id,
        "sections_rendered": len(sections),
        "uploaded_images": uploads,
        "validation_report": validation_report,
    }


# Enhanced version with LLM processing and speaker notes
async def fill_template_for_all_sections_new_enhanced(
    drive,
    slides,
    results: Dict[str, Any],
    *,
    template_id: str,
    folder_id: Optional[str],
    llm_processor,
    verbose: bool = False,
    enable_speaker_notes: bool = True,
):
    """Enhanced template processing with LLM paragraph optimization and notes integration."""
    if verbose:
        logger.setLevel(logging.DEBUG)

    # Phase 1: Enhanced data mapping with LLM processing and slug validation
    logger.info("Starting enhanced paragraph processing...")
    text_map, sections, notes_map = await build_text_and_image_maps_enhanced(
        results, llm_processor, template_id=template_id
    )
    logger.info("Enhanced processing complete. Renderable sections: %d", len(sections))

    if verbose:
        print(
            "Optimized text map preview:",
            {k: v[:100] + "..." if len(str(v)) > 100 else v for k, v in list(text_map.items())[:3]},
        )
        print(
            "Notes map preview:",
            {k: v[:100] + "..." if len(str(v)) > 100 else v for k, v in list(notes_map.items())[:3]},
        )

    # Phase 2: Template duplication and organization (existing logic)
    out_name = f"final_presentation_{int(time.time())}"
    presentation_id = copy_file(drive, template_id, out_name)
    logger.info("Copied template -> %s", presentation_id)
    if folder_id:
        try:
            move_file(drive, presentation_id, folder_id)
            logger.info("Moved to folder %s", folder_id)
        except Exception as e:
            logger.warning(f"Move failed (continuing): {e}")

    # Phase 3: Image processing (existing logic)
    image_map = {}
    uploads = []
    for sec in sections:
        slug = sec["slug"]
        pretty_name = f"{slug}_{int(time.time())}.png"
        file_id = upload_png(drive, sec["chart_path"], name=pretty_name, parent_folder_id=folder_id)
        try:
            make_file_public(drive, file_id)
        except Exception as e:
            logger.warning(f"make_file_public failed ({file_id}): {e}")

        url = f"https://drive.google.com/uc?export=view&id={file_id}"
        image_map["{{" + f"{slug}_chart" + "}}"] = url
        uploads.append(
            {
                "title": sec["title"],
                "file_id": file_id,
                "image_url": url,
                "slide_paragraph": sec.get("slide_paragraph", ""),
                "key_insights": sec.get("key_insights", []),
            }
        )

    logger.info("Uploaded %d chart images", len(uploads))

    # Phase 4: Enhanced text replacement (slide-optimized content)
    logger.info("Replacing %d optimized text tokens…", len(text_map))
    make_all_shapes_normal_weight(presentation_id)
    batch_text_replace(slides, presentation_id, text_map)

    # Phase 5: Image replacement (existing logic)
    logger.info("Replacing %d image tokens…", len(image_map))
    batch_replace_shapes_with_images_and_resize(
        slides,
        presentation_id,
        image_map,
        resize={"mode": "ABSOLUTE", "scaleX": 400, "scaleY": 400, "unit": "PT", "translateX": 130, "translateY": 250},
        replace_method="CENTER_INSIDE",
    )

    # Phase 6: NEW - Speaker notes integration
    notes_result = {"notes_added": 0}
    if enable_speaker_notes:
        try:
            logger.info("Adding speaker notes to slides...")
            notes_result = await add_speaker_notes_to_slides(slides, presentation_id, sections)
            logger.info(f"Speaker notes added to {notes_result.get('notes_added', 0)} slides")
        except Exception as e:
            logger.warning(f"Speaker notes addition failed: {e}")
            notes_result = {"error": str(e), "notes_added": 0}

    # 6) Debug validation and verification
    from scalapay.scalapay_mcp_kam.utils.slug_validation import debug_slug_mapping, verify_chart_imports

    validation_report = debug_slug_mapping(results, template_id)
    expected_chart_files = [upload["file_id"] for upload in uploads]
    verification_result = verify_chart_imports(presentation_id, expected_chart_files)
    logger.info(f"Enhanced processing validation: {validation_report['success_rate']:.1%}")
    logger.info(f"Chart import verification: {verification_result['success_rate']:.1%}")

    return {
        "presentation_id": presentation_id,
        "sections_rendered": len(sections),
        "uploaded_images": uploads,
        "notes_added": notes_result.get("notes_added", 0),
        "llm_processing_enabled": True,
        "speaker_notes_enabled": enable_speaker_notes,
        "validation_report": validation_report,
        "chart_verification": verification_result,
    }


async def create_slides(merchant_token: str, starting_date: str, end_date: str, ctx: Context | None = None) -> dict:
    logger.debug("Starting create_slides function")
    logger.debug(f"Input string: {merchant_token}")
    if ctx:
        await ctx.info("🚀 Starting slide generation")

    load_dotenv()

    # Run the query with configurable concurrent processing
    results = await mcp_tool_run(
        requests_list=[
            "monthly sales year over year",
            "total variations in percentages of sales year over year",
            "orders by user type: Scalapay Network, Returning, New",
            "monthly orders by product type (pay in 3, pay in 4)over the last two years",
            "distribution of orders by product type (pay in 3, pay in 4) in percentages",
            "monthly orders by user type",
            "AOV over the last 3 months",
            "Age distribution (counts users with age bands 20–29 years, 30–39 years, 40–49 years, 50–59 years, 60–69 years, 70–79 years, 80–89 years and then compute in percentages)",
            "Gender distribution (counts users by gender and then compute in percentages)",
            "Cart type distribution (counts orders by cart type, (credit, prepaid, debit), and then compute in percentages)",
            "orders by product type (i.e. pay in 3, pay in 4)",
            "AOV by product type (i.e. pay in 3, pay in 4)",
        ],
        merchant_token=merchant_token,
        starting_date=starting_date,
        end_date=end_date,
        chart_prompt_template=GENERAL_CHART_PROMPT
    )
    print(f"\n[DEBUG] Raw Results: {results}")

    # Configure debug folder for chart output (if specified)


    if ctx:
        await ctx.info("🔄 Starting chart generation with MatPlot MCP server...")
    
    try:
        charts_list = await asyncio.wait_for(
            mcp_matplot_run(
                results,  # This is the results_dict parameter (positional)
                matplot_url="http://localhost:8010/mcp",
                server_id="MatPlotAgent",
                operation="generate_chart_simple",
                model_type="gpt-4o",
                verbose=True,  # Force enable for debugging
                transport="http",  # Pass debug folder configuration
                ctx=ctx  # Pass context for progress reporting
            ),
            timeout=300  # 5 minute timeout
        )
    except asyncio.TimeoutError:
        if ctx:
            await ctx.error("❌ Chart generation timed out after 5 minutes")
        logger.error("Chart generation timed out")
        charts_list = results  # fallback to original results
    except Exception as e:
        if ctx:
            await ctx.error(f"❌ Chart generation failed: {str(e)}")
        logger.error(f"Chart generation failed: {e}")
        charts_list = results  # fallback to original results

    print(f"\n[DEBUG] Charts List is: {charts_list}")
    logger.debug(f"[DEBUG] Charts list is: {charts_list}")
    
    # Debug chart paths
    for key, value in charts_list.items():
        if isinstance(value, dict):
            chart_path = value.get("chart_path")
            errors = value.get("errors", [])
            print(f"[DEBUG] {key}: chart_path={chart_path}, errors={errors}")
            if ctx:
                if chart_path:
                    await ctx.info(f"✅ {key}: Chart saved to {chart_path}")
                else:
                    await ctx.warning(f"⚠️ {key}: No chart path found. Errors: {errors}")
                    
    if ctx:
        await ctx.info("📊 Chart generation phase completed")

    # ✅ pick one chart path to actually use later - improved logic for concurrent version
    chart_path = None

    # Try common chart types first
    preferred_charts = ["monthly sales over time", "monthly sales year over year", "AOV", "monthly orders by user type"]

    for preferred_chart in preferred_charts:
        if preferred_chart in charts_list:
            entry = charts_list[preferred_chart]
            if isinstance(entry, dict) and entry.get("chart_path"):
                chart_path = entry["chart_path"]
                logger.info(f"[CHART-SELECTION] Using preferred chart: {preferred_chart} -> {chart_path}")
                break

    # fallback: pick the first available chart_path if preferred ones are missing
    if not chart_path:
        for k, v in charts_list.items():
            if isinstance(v, dict) and v.get("chart_path"):
                chart_path = v["chart_path"]
                logger.info(f"[CHART-SELECTION] Using fallback chart: {k} -> {chart_path}")
                break

    # Debug: Log all available chart paths for troubleshooting
    available_charts = []
    for k, v in charts_list.items():
        if isinstance(v, dict):
            if v.get("chart_path"):
                available_charts.append(f"{k}: {v['chart_path']}")
            elif v.get("errors"):
                available_charts.append(f"{k}: ERROR - {v['errors']}")
            else:
                available_charts.append(f"{k}: NO CHART_PATH")

    logger.info(f"[CHART-SELECTION] Available charts: {available_charts}")


    try:

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
        logger.info("🎯 Using NORMAL POSITIONING with template processing")
        if ctx:
            await ctx.info("🎯 Using next-generation positioning system")

        # Use clean positioning system with template processing
        from scalapay.scalapay_mcp_kam.configs.resize_configs import RESIZE_DEFAULT, PER_CHART_RESIZE
        final = await fill_template_for_all_sections_new(
            drive_service,
            slides_service,
            charts_list,
            template_id=output_file_id,
            folder_id=folder_id,
            resize=RESIZE_DEFAULT,
            resize_map=PER_CHART_RESIZE,
        )
        pres_id = final["presentation_id"]
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

    # Append presentation info to output
    try:
        info = Slides.get_presentation_info(pres_id)
    except Exception:
        logger.exception("Failed to retrieve presentation info")
        info = {}

    # 4) Return a tidy summary with enhanced information
    response = {
        "presentation_id": pres_id,
        "sections_rendered": final.get("sections_rendered", 0),
        "uploaded_images": final.get("uploaded_images", []),
        "pdf_path": pdf_path,
        "charts_list_keys": list(charts_list.keys()),
        # Enhanced feature information
        "info": info,
        "llm_processing_enabled": final.get("llm_processing_enabled", False),
        "speaker_notes_enabled": final.get("speaker_notes_enabled", False),
        "notes_added": final.get("notes_added", 0),
        # Concurrent processing information
        "concurrent_processing_enabled": final.get("concurrent_processing_enabled", False),
        "processing_time": final.get("processing_time", 0.0),
        "concurrent_operations": final.get("concurrent_operations", 0),
        "validation_report": final.get("validation_report", {}),
        "chart_verification": final.get("chart_verification", {}),
        # NEW: Clean positioning system information
        "clean_positioning_enabled": final.get("clean_positioning_enabled", False),
        "positioning_performance": final.get("positioning_performance", {}),
        "upload_performance": final.get("upload_performance", {}),
        "text_performance": final.get("text_performance", {}),
    }

    # Log final processing summary
    logger.info(
        f"Slide generation complete: {response['sections_rendered']} sections, "
        f"LLM processing: {response['llm_processing_enabled']}, "
        f"Concurrent processing: {response['concurrent_processing_enabled']}, "
        f"Speaker notes: {response['notes_added']} added, "
        f"Processing time: {response['processing_time']:.2f}s"
    )

    return response


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
