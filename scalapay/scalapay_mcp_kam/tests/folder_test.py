#!/usr/bin/env python3
import argparse
import base64
import io
import os
import time

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "./scalapay/scalapay_mcp_kam/credentials.json"


# ---------- helpers ----------
def build_services():
    drive = build("drive", "v3")
    slides = build("slides", "v1")
    return drive, slides


def resolve_shortcut(drive, file_id: str) -> str:
    f = (
        drive.files()
        .get(fileId=file_id, fields="id,name,mimeType,shortcutDetails,driveId", supportsAllDrives=True)
        .execute()
    )
    if f.get("mimeType") == "application/vnd.google-apps.shortcut":
        return f["shortcutDetails"]["targetId"]
    return file_id


def probe_folder(drive, folder_id: str):
    info = (
        drive.files().get(fileId=folder_id, fields="id,name,mimeType,parents,driveId", supportsAllDrives=True).execute()
    )
    if info["mimeType"] != "application/vnd.google-apps.folder":
        raise RuntimeError(f"ID {folder_id} is not a folder (mimeType={info['mimeType']})")
    return info


def upload_png(drive, local_path: str, name: str, parent_folder_id: str | None):
    # Resolve shortcut
    if parent_folder_id:
        parent_folder_id = resolve_shortcut(drive, parent_folder_id)

    media = MediaFileUpload(local_path, mimetype="image/png", resumable=True)
    body = {"name": name, "mimeType": "image/png"}
    if parent_folder_id:
        body["parents"] = [parent_folder_id]

    try:
        f = drive.files().create(body=body, media_body=media, fields="id,parents", supportsAllDrives=True).execute()
        return f["id"]
    except HttpError as e:
        # Fallback: create in root then move to target folder
        if parent_folder_id and e.resp.status in (400, 404):
            f = (
                drive.files()
                .create(
                    body={"name": name, "mimeType": "image/png"},
                    media_body=media,
                    fields="id,parents",
                    supportsAllDrives=True,
                )
                .execute()
            )
            file_id = f["id"]
            old_parents = ",".join(f.get("parents", []))
            drive.files().update(
                fileId=file_id,
                addParents=parent_folder_id,
                removeParents=old_parents,
                fields="id,parents",
                supportsAllDrives=True,
            ).execute()
            return file_id
        raise


def make_public(drive, file_id: str):
    try:
        drive.permissions().create(fileId=file_id, body={"type": "anyone", "role": "reader"}, fields="id").execute()
    except HttpError as e:
        if e.resp.status not in (400, 403, 409):
            raise


def drive_direct_view_url(file_id: str) -> str:
    return f"https://drive.google.com/uc?export=view&id={file_id}"


def copy_template_to_folder(drive, template_id: str, new_name: str, folder_id: str | None) -> str:
    copy_body = {"name": new_name}
    if folder_id:
        folder_id = resolve_shortcut(drive, folder_id)
        copy_body["parents"] = [folder_id]
    pres = drive.files().copy(fileId=template_id, body=copy_body, fields="id,parents", supportsAllDrives=True).execute()
    return pres["id"]


def insert_simple_slide_with_image(slides, presentation_id: str, image_url: str):
    slide_id = f"slide_test_{int(time.time())}"
    title_id = f"title_{slide_id}"
    img_id = f"img_{slide_id}"

    # Use a real layout from your list. Good choices:
    # p84 = "LATERAL BOX (For Charts) - Blue"
    LAYOUT_ID = "p86"

    requests = [
        {"createSlide": {"objectId": slide_id, "insertionIndex": 1}},
        # Title
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
        {"insertText": {"objectId": title_id, "text": "Test Image Upload"}},
        {
            "updateTextStyle": {
                "objectId": title_id,
                "style": {"bold": True, "fontSize": {"magnitude": 24, "unit": "PT"}},
                "fields": "bold,fontSize",
            }
        },
        # Image
        {
            "createImage": {
                "objectId": img_id,
                "url": image_url,
                "elementProperties": {
                    "pageObjectId": slide_id,
                    "size": {"width": {"magnitude": 640, "unit": "PT"}, "height": {"magnitude": 360, "unit": "PT"}},
                    "transform": {"scaleX": 1, "scaleY": 1, "translateX": 160, "translateY": 120, "unit": "PT"},
                },
            }
        },
    ]
    slides.presentations().batchUpdate(presentationId=presentation_id, body={"requests": requests}).execute()
    return slide_id


def export_pdf(drive, file_id: str, out_path: str):
    req = drive.files().export_media(fileId=file_id, mimeType="application/pdf")
    fh = io.FileIO(out_path, "wb")
    downloader = MediaIoBaseDownload(fh, req)
    done = False
    while not done:
        status, done = downloader.next_chunk()
        if status:
            print(f"PDF progress: {int(status.progress() * 100)}%")
    return out_path


# ---------- main ----------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--folder", required=False, help="Target folderId (can be Shared Drive).")
    ap.add_argument("--template", required=True, help="Template presentation fileId.")
    ap.add_argument("--file", required=False, help="Local PNG to upload. If missing, a tiny 1x1 PNG is created.")
    args = ap.parse_args()

    print("[1] Building services…")
    drive, slides = build_services()

    folder_id = args.folder
    if folder_id:
        print(f"[2] Probing folder {folder_id}…")
        try:
            resolved = resolve_shortcut(drive, folder_id)
            info = probe_folder(drive, resolved)
            print(f"    → OK: name='{info['name']}', driveId='{info.get('driveId','')}'")
            folder_id = resolved
        except Exception as e:
            print(f"    ✗ Folder probe failed: {e}")
            return

    print("[3] Preparing PNG…")
    png_path = "/Users/keem.adorable@scalapay.com/scalapay/scalapay_mcp_kam/plots/AOV_by_product_type_i_e_pay_in_3_pay_in_4__977e844e.png"

    print("[4] Uploading PNG…")
    file_id = upload_png(drive, png_path, "test_upload.png", folder_id)
    print(f"    → File ID: {file_id}")

    print("[5] Making PNG public (anyone with link)…")
    make_public(drive, file_id)
    image_url = drive_direct_view_url(file_id)
    print(f"    → Image URL: {image_url}")

    print("[6] Copying template to target folder…")
    pres_id = copy_template_to_folder(drive, args.template, "Test Deck (auto)", folder_id)
    print(f"    → New presentation ID: {pres_id}")

    print("[7] Inserting a slide with that image…")
    slide_id = insert_simple_slide_with_image(slides, pres_id, image_url)
    print(f"    → Slide created: {slide_id}")

    print("[8] Exporting PDF…")
    pdf_path = f"/tmp/{pres_id}.pdf"
    export_pdf(drive, pres_id, pdf_path)
    print(f"    → PDF saved at: {pdf_path}")

    print("\n✅ All done.")


from googleapiclient.discovery import build

slides = build("slides", "v1")


def print_layouts(presentation_id: str):
    pres = slides.presentations().get(presentationId=presentation_id).execute()
    for l in pres.get("layouts", []):
        props = l.get("layoutProperties", {})
        print(f"- id={l['objectId']}  name={props.get('name')}  displayName={props.get('displayName')}")


if __name__ == "__main__":
    # Requires GOOGLE_APPLICATION_CREDENTIALS to point to your service account JSON.
    # Ensure the service account has access to the folder / Shared Drive.
    main()
