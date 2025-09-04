#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import io
import json
import logging
import os
import time
import unicodedata
import string
from typing import Dict, Any, List, Optional

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
from GoogleApiSupport.slides import Transform
from GoogleApiSupport.slides import execute_batch_update
from GoogleApiSupport.slides import get_all_shapes_placeholders


# ---------------------------
# Logging
# ---------------------------
LOG_FORMAT = "[%(levelname)s] %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
logger = logging.getLogger("slides_test")

# ---------------------------
# Helpers: slug + pickers
# ---------------------------
def _slug(s: str, max_len: int = 40) -> str:
    """
    Convert string to slug format matching your template tokens.
    Uses hyphens instead of underscores to match template format.
    Handles special cases for your specific template tokens.
    """
    s = "".join(c for c in unicodedata.normalize("NFKD", s) if ord(c) < 128)
    s = s.lower().strip()
    
    # Handle specific known mappings first
    if "scalapay users demographic in percentages" in s:
        return "scalapay-users-demographic-in-percentage"  # singular, not plural
    elif "orders by product type i.e. pay in 3, pay in 4" in s:
        return "orders-by-product-type-i-e-pay-in-3-pay-"  # matches template truncation
    elif "aov by product type i.e. pay in 3, pay in 4" in s:
        return "aov-by-product-type-i-e-pay-in-3-pay-in-"  # matches template truncation
    
    # Standard slug processing
    # Allow lowercase letters, digits, and hyphens only
    valid = f"{string.ascii_lowercase}{string.digits}-"
    s = "".join(ch if ch in valid else "-" for ch in s.replace(" ", "-"))
    
    # Clean up multiple consecutive hyphens
    while "--" in s:
        s = s.replace("--", "-")
    
    # Remove leading/trailing hyphens
    s = s.strip("-")
    
    # Handle the length truncation more carefully
    if len(s) > max_len:
        # For long strings, truncate at the limit
        s = s[:max_len].rstrip("-")
    
    return s or "section"


def _pick_paragraph(payload: Dict[str, Any]) -> Optional[str]:
    # 1) slides_struct.paragraph
    p = (payload.get("slides_struct") or {}).get("paragraph")
    if isinstance(p, str) and p.strip():
        return p.strip()

    # 2) payload.paragraph
    p = payload.get("paragraph")
    if isinstance(p, str) and p.strip():
        return p.strip()

    # 3) alfred_raw string -> look for paragraph
    raw = payload.get("alfred_raw")
    if isinstance(raw, str) and raw.strip():
        try:
            # normalize single quotes to JSON
            jsonish = raw.replace("'", '"')
            data = json.loads(jsonish)
            p = data.get("paragraph")
            if isinstance(p, str) and p.strip():
                return p.strip()
        except Exception as e:
            logger.debug(f"_pick_paragraph: failed to parse alfred_raw: {e}")
    return None

def _pick_chart_path(payload: Dict[str, Any]) -> Optional[str]:
    mp = payload.get("matplot_raw") or {}
    cp = mp.get("chart_path")
    if isinstance(cp, str) and cp.strip():
        return cp
    cp = payload.get("chart_path")
    if isinstance(cp, str) and cp.strip():
        return cp
    return None

# ---------------------------
# Google API helpers
# ---------------------------
def build_services(creds_path: str):
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = creds_path
    drive = build("drive", "v3")
    slides = build("slides", "v1")
    return drive, slides

def resolve_shortcut(drive, file_id: str) -> str:
    f = drive.files().get(
        fileId=file_id,
        fields="id,mimeType,shortcutDetails",
        supportsAllDrives=True,
    ).execute()
    if f.get("mimeType") == "application/vnd.google-apps.shortcut":
        return f["shortcutDetails"]["targetId"]
    return file_id

def copy_file(drive, file_id: str, name: str) -> str:
    body = {"name": name}
    f = drive.files().copy(
        fileId=file_id, body=body, fields="id", supportsAllDrives=True
    ).execute()
    return f["id"]

def move_file(drive, file_id: str, parent_folder_id: str) -> None:
    # Fetch current parents so we can remove them
    meta = drive.files().get(
        fileId=file_id, fields="parents", supportsAllDrives=True
    ).execute()
    prev_parents = ",".join(meta.get("parents", []))
    drive.files().update(
        fileId=file_id,
        addParents=parent_folder_id,
        removeParents=prev_parents,
        fields="id, parents",
        supportsAllDrives=True,
    ).execute()

def upload_png(drive, local_path: str, *, name: str, parent_folder_id: Optional[str]) -> str:
    body = {"name": name if name.endswith(".png") else f"{name}.png", "mimeType": "image/png"}
    if parent_folder_id:
        body["parents"] = [resolve_shortcut(drive, parent_folder_id)]
    media = MediaFileUpload(local_path, mimetype="image/png", resumable=True)
    f = drive.files().create(
        body=body, media_body=media, fields="id", supportsAllDrives=True
    ).execute()
    return f["id"]

def make_file_public(drive, file_id: str) -> None:
    try:
        drive.permissions().create(
            fileId=file_id,
            body={"type": "anyone", "role": "reader"},
            fields="id",
            supportsAllDrives=True,
        ).execute()
    except HttpError as e:
        # Often 403/409 can be ignored (already shared or restricted by admin)
        if getattr(e, "resp", None) and getattr(e.resp, "status", None) in (400, 403, 409):
            logger.warning(f"make_file_public({file_id}) non-fatal: {e}")
        else:
            raise

def export_presentation_pdf(drive, presentation_id: str, out_path: str) -> str:
    req = drive.files().export_media(fileId=presentation_id, mimeType="application/pdf")
    fh = io.FileIO(out_path, "wb")
    downloader = MediaIoBaseDownload(fh, req)
    done = False
    while not done:
        status, done = downloader.next_chunk()
    return out_path

# ---------------------------
# Slides fill core
# ---------------------------
def build_text_and_image_maps(results: Dict[str, Any]) -> (Dict[str, str], List[Dict[str, str]]):
    """Return text_map (token->value), sections list with chart_path."""
    sections = []
    for title, payload in results.items():
        paragraph = _pick_paragraph(payload)
        chart_path = _pick_chart_path(payload)
        if paragraph and chart_path:
            sections.append({"title": title, "paragraph": paragraph, "chart_path": chart_path})
        else:
            logger.debug(f"Skipping section '{title}' (missing paragraph or chart_path)")

    if not sections:
        raise RuntimeError("No renderable sections (need both paragraph and chart_path).")

    text_map = {}
    for sec in sections:
        slug = _slug(sec["title"])
        text_map[f"{{{{{slug}_title}}}}"] = sec["title"]
        text_map[f"{{{{{slug}_paragraph}}}}"] = str(sec["paragraph"])

    return text_map, sections

def set_text_normal_weight(presentation_id: str, shape_id: str, start_index=0, end_index=None):
    """
    Set text to normal weight (remove bold formatting) for a specific shape
    
    Args:
        presentation_id: ID of the presentation
        shape_id: ID of the shape/text box to modify
        start_index: Starting character position (0 for beginning)
        end_index: Ending character position (None for entire text)
    """
    # Build text range - if end_index is None, update all text
    text_range = {
        "type": "FIXED_RANGE" if end_index is not None else "ALL",
        "startIndex": start_index,
    }
    
    if end_index is not None:
        text_range["endIndex"] = end_index
    
    requests = [
        {
            "updateTextStyle": {
                "objectId": shape_id,
                "textRange": text_range,
                "style": {
                    "bold": False,
                    "fontSize": {"magnitude": 22, "unit": "PT"},
                    },
                "fields": "bold",
            }
        }
    ]
    
    return execute_batch_update(requests, presentation_id)


def update_text_style_advanced(presentation_id: str, shape_id: str, 
                              bold=None, italic=None, font_family=None, 
                              font_size=None, color=None, link_url=None,
                              start_index=0, end_index=None):
    """
    Advanced text styling function based on Google's official documentation
    
    Args:
        presentation_id: ID of the presentation
        shape_id: ID of the shape/text box to modify
        bold: True/False for bold formatting
        italic: True/False for italic formatting
        font_family: Font family name (e.g., "Times New Roman", "Arial")
        font_size: Font size in points (e.g., 12, 14, 16)
        color: RGB color dict {'red': 0.0-1.0, 'green': 0.0-1.0, 'blue': 0.0-1.0}
        link_url: URL to create hyperlink
        start_index: Starting character position
        end_index: Ending character position (None for entire text)
    """
    # Build style object
    style = {}
    fields = []
    
    if bold is not None:
        style["bold"] = bold
        fields.append("bold")
    
    if italic is not None:
        style["italic"] = italic
        fields.append("italic")
    
    if font_family:
        style["fontFamily"] = font_family
        fields.append("fontFamily")
    
    if font_size:
        style["fontSize"] = {"magnitude": font_size, "unit": "PT"}
        fields.append("fontSize")
    
    if color:
        style["foregroundColor"] = {
            "opaqueColor": {
                "rgbColor": color
            }
        }
        fields.append("foregroundColor")
    
    if link_url:
        style["link"] = {"url": link_url}
        fields.append("link")
    
    # Build text range
    text_range = {
        "type": "FIXED_RANGE" if end_index is not None else "ALL",
        "startIndex": start_index,
    }
    
    if end_index is not None:
        text_range["endIndex"] = end_index
    
    requests = [
        {
            "updateTextStyle": {
                "objectId": shape_id,
                "textRange": text_range,
                "style": style,
                "fields": ",".join(fields),
            }
        }
    ]
    
    return execute_batch_update(requests, presentation_id)


def make_all_shapes_normal_weight(presentation_id: str):
    """
    Make all text shapes in the presentation normal weight (remove bold)
    Excludes shapes where the text content contains "_title"
    """
    shapes = get_all_shapes_placeholders(presentation_id)
    requests = []
    
    for shape_id, shape_info in shapes.items():
        if shape_info:  # Shape has text content
            # Check if "_title" is in the inner text content
            inner_text = shape_info.get('inner_text', '')
            print("inner text is: ", inner_text)
            if "_paragraph" in inner_text:
                requests.append({
                    "updateTextStyle": {
                        "objectId": shape_id,
                        "textRange": {"type": "ALL"},
                        "style": {
                            "bold": False,
                            "fontSize": {"magnitude": 22, "unit": "PT"},
                        },
                        "fields": "bold,fontSize"
                    }
                })
    
    if requests:
        return execute_batch_update(requests, presentation_id)
    return None


# Usage examples:
def example_usage():
    presentation_id = "your_presentation_id"
    shape_id = "your_shape_id"
    
    # Make text normal weight (not bold)
    set_text_normal_weight(presentation_id, shape_id)
    
    # Make first 10 characters normal weight
    set_text_normal_weight(presentation_id, shape_id, start_index=0, end_index=10)
    
    # Advanced styling: normal weight, Arial font, 12pt
    update_text_style_advanced(
        presentation_id, 
        shape_id,
        bold=False,
        font_family="Arial", 
        font_size=12
    )
    
    # Make all text shapes in presentation normal weight
    make_all_shapes_normal_weight(presentation_id)

def batch_text_replace(slides, presentation_id: str, text_map: Dict[str, str]):
    requests = []
    for token, value in text_map.items():
        print(token)

        requests.append({
            "replaceAllText": {
                "containsText": {"text": token, "matchCase": False},
                "replaceText": value,
            }
        })
    if not requests:
        return
    slides.presentations().batchUpdate(
        presentationId=presentation_id,
        body={"requests": requests},
    ).execute()

def find_element_ids_for_tokens(slides, presentation_id, tokens):
    """
    Return { token: [objectId, ...], ... } for shapes whose text contains token (case-insensitive).
    """
    pres = slides.presentations().get(presentationId=presentation_id).execute()
    token_ids = {t: [] for t in tokens}
    print(f"all the tokens are: {tokens}")
    for page in pres.get("slides", []):
        for pe in page.get("pageElements", []):
            shape = pe.get("shape")
            if not shape:
                continue
            text_content = []
            te = shape.get("text", {}).get("textElements", [])
            for el in te:
                run = el.get("textRun", {})
                if "content" in run:
                    text_content.append(run["content"])
            text = "".join(text_content).lower()
                        
            # Debug: print all text content found
            if text.strip():
                print(f"Found text in shape {pe['objectId']}: '{text.strip()}'")
            
            for t in tokens:
                if t.lower() in text:
                    token_ids[t].append(pe["objectId"])
                    print(f"✅ MATCH: Token '{t}' found in shape {pe['objectId']}")
    return token_ids

EMU_PER_PT = 12700

def _pt_to_unit(val_pt: float, unit: str) -> float:
    return val_pt * EMU_PER_PT if unit == "EMU" else val_pt

def _get_obj_transform(slides, presentation_id, obj_id):
    pres = slides.presentations().get(presentationId=presentation_id).execute()
    for page in pres.get("slides", []):
        for pe in page.get("pageElements", []):
            if pe.get("objectId") == obj_id:
                tf = pe.get("transform", {}) or {}
                # Slides may omit unit here; default to PT
                unit = tf.get("unit", "PT")
                return {
                    "tx": float(tf.get("translateX", 0.0)),
                    "ty": float(tf.get("translateY", 0.0)),
                    "unit": unit,
                }
    return None

def move_tokens_by_delta_abs(slides, presentation_id, tokens, dx_pt=0.0, dy_pt=0.0):
    ids_map = find_element_ids_for_tokens(slides, presentation_id, tokens)
    reqs = []
    for ids in ids_map.values():
        for obj_id in ids:
            geom = _get_obj_transform(slides, presentation_id, obj_id)
            if not geom:
                continue
            unit = geom["unit"]
            new_tx = geom["tx"] + _pt_to_unit(dx_pt, unit)
            new_ty = geom["ty"] + _pt_to_unit(dy_pt, unit)

            t = Transform(translate_x=new_tx, translate_y=new_ty, unit=unit).json
            # prune scale/shear so we don't touch size
            t.pop("scaleX", None); t.pop("scaleY", None); t.pop("shearX", None); t.pop("shearY", None)

            reqs.append({
                "updatePageElementTransform": {
                    "objectId": obj_id,
                    "applyMode": "ABSOLUTE",
                    "transform": t
                }
            })
    if reqs:
        slides.presentations().batchUpdate(
            presentationId=presentation_id, body={"requests": reqs}
        ).execute()


def batch_replace_shapes_with_images_and_resize(
    slides,
    presentation_id,
    image_map,
    *,
    resize=None,
    replace_method="CENTER_INSIDE"
):
    """
    image_map: { token: public_image_url }
    resize (optional):
      {
        "mode": "RELATIVE" | "ABSOLUTE",
        "scaleX": float,
        "scaleY": float,
        "translateX": float,
        "translateY": float,
        "shearX": float,
        "shearY": float,
        "unit": "PT" | "EMU"
      }
    """
    tokens = list(image_map.keys())
    token_to_ids = find_element_ids_for_tokens(slides, presentation_id, tokens)

    # Phase 1: replace all shapes with images
    replace_reqs = []
    for token, url in image_map.items():
        replace_reqs.append({
            "replaceAllShapesWithImage": {
                "containsText": {"text": token, "matchCase": False},
                "imageUrl": url,
                "replaceMethod": replace_method,
            }
        })

    if replace_reqs:
        slides.presentations().batchUpdate(
            presentationId=presentation_id,
            body={"requests": replace_reqs},
        ).execute()

    if not resize:
        return

    # Phase 2: transform elements
    mode = (resize.get("mode") or "RELATIVE").upper()
    unit = resize.get("unit", "EMU")  # Changed default to EMU

    # Extract values, keeping None when not provided
    sx = resize.get("scaleX")
    sy = resize.get("scaleY") 
    tx = resize.get("translateX")
    ty = resize.get("translateY")
    shx = resize.get("shearX")
    shy = resize.get("shearY")

    # Guardrails
    if mode == "ABSOLUTE":
        if (sx is not None and sx > 3.0) or (sy is not None and sy > 3.0):
            logging.warning("ABSOLUTE scale >3.0 may push images off slide")

    transform_reqs = []

    for _, ids in token_to_ids.items():
        if not ids:
            continue

        for obj_id in ids:
            # Only build transform dict with explicitly provided values
            transform_dict = {"unit": unit}
            
            if sx is not None:
                transform_dict["scaleX"] = float(sx)
            if sy is not None:
                transform_dict["scaleY"] = float(sy)
            if tx is not None:
                transform_dict["translateX"] = float(tx)
            if ty is not None:
                transform_dict["translateY"] = float(ty)
            if shx is not None:
                transform_dict["shearX"] = float(shx)
            if shy is not None:
                transform_dict["shearY"] = float(shy)

            # Skip if only unit is specified
            if len(transform_dict) == 1:  # only "unit"
                continue

            transform_reqs.append({
                "updatePageElementTransform": {
                    "objectId": obj_id,
                    "applyMode": mode,
                    "transform": transform_dict
                }
            })

    if transform_reqs:
        slides.presentations().batchUpdate(
            presentationId=presentation_id,
            body={"requests": transform_reqs},
        ).execute()

def batch_replace_shapes_with_images(slides, presentation_id: str, image_map: Dict[str, str]):
    """
    image_map: token -> public imageUrl
    Uses CENTER_INSIDE by default.
    """
    requests = []
    for token, url in image_map.items():
        print(token)
        requests.append({
            "replaceAllShapesWithImage": {
                "containsText": {"text": token, "matchCase": False},
                "imageUrl": url,
                "replaceMethod": "CENTER_INSIDE",
            }
        })
        requests.append({
            "updatePageElementTransform": {
                "objectId": "<ELEMENT_ID>",
                "applyMode": "ABSOLUTE",
                "transform": {
                    "scaleX": 2.0,   # make it twice as wide
                    "scaleY": 2.0,   # make it twice as tall
                    "translateX": 2.0,  # move right
                    "translateY": 2.0,   # move down
                    "unit": "PT"
                }
            }
        })
    if not requests:
        return
    slides.presentations().batchUpdate(
        presentationId=presentation_id,
        body={"requests": requests},
    ).execute()

def fill_template_for_all_sections(
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
    print("Image tokens being searched for:", list(image_map.keys()))
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

# ---------------------------
# CLI
# ---------------------------
def main():
    ap = argparse.ArgumentParser(description="Test filling Slides template with multiple sections.")
    ap.add_argument("--template", required=True, help="Slides template file ID")
    ap.add_argument("--folder", required=False, default=None, help="Drive folder ID to move the copy into")
    ap.add_argument("--creds", required=True, help="Path to service account credentials JSON")
    ap.add_argument("--results", required=False, default=None, help="Path to JSON file with results object")
    ap.add_argument("--export-pdf", action="store_true", help="Export the final presentation as PDF")
    ap.add_argument("--verbose", action="store_true", help="Debug logging")
    args = ap.parse_args()

    drive, slides = build_services(args.creds)

    # Load results
    if args.results:
        with open(args.results, "r", encoding="utf-8") as f:
            results = json.load(f)
    else:
        # Minimal inline sample (replace with your full object or pass --results)
        results = {
            "monthly sales over time": {
                "slides_struct": {
                    "paragraph": "Example paragraph.",
                    "structured_data": {"Jan": {"2024": 1, "2025": 2}},
                },
                # IMPORTANT: point to a real PNG on your disk to test upload
                "chart_path": "./plots/monthly_sales_over_time_example.png",
                "matplot_raw": {"chart_path": "./plots/monthly_sales_over_time_example.png"},
            }
        }

    # Run
    final = fill_template_for_all_sections(
        drive, slides,
        results,
        template_id=args.template,
        folder_id=args.folder,
        verbose=args.verbose,
    )
    pres_id = final["presentation_id"]
    logger.info("Slides updated and moved: %s", pres_id)

    # Export PDF if requested
    if args.export_pdf:
        out_pdf = f"/tmp/{pres_id}.pdf"
        try:
            export_presentation_pdf(drive, pres_id, out_pdf)
            logger.info("Exported PDF: %s", out_pdf)
        except Exception as e:
            logger.warning(f"PDF export failed: {e}")

    # Print a concise summary at the end (useful in CI logs)
    print("\n=== RESULT ===")
    print(json.dumps(final, indent=2))

if __name__ == "__main__":
    main()
