#!/usr/bin/env python3
import os
import sys
import argparse
import logging
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# --- logging ---
logging.basicConfig(
    level=logging.DEBUG,
    format='[%(levelname)s] %(message)s'
)
log = logging.getLogger("make_public_test")

# --- config: service account json path (or rely on env already set) ---
# os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/path/to/your/service_account.json"

# --- helpers ---
def build_drive():
    """
    Builds a Drive v3 service using GOOGLE_APPLICATION_CREDENTIALS.
    """
    try:
        svc = build("drive", "v3")
        return svc
    except Exception as e:
        log.error("Failed to build Drive service: %s", e)
        raise

def clean_id(file_id: str) -> str:
    """
    Strip whitespace and trailing punctuation often introduced by copy/paste.
    """
    return (file_id or "").strip().strip(" .\t\r\n")

def file_exists(drive, file_id: str) -> bool:
    """
    Quick existence check (also confirms access).
    """
    try:
        drive.files().get(
            fileId=file_id,
            fields="id,name,parents,driveId,owners,emailAddress,permissionIds",
            supportsAllDrives=True
        ).execute()
        return True
    except HttpError as e:
        log.debug("file_exists(%s) -> HttpError %s", file_id, e)
        return False

def get_file_meta(drive, file_id: str) -> dict | None:
    try:
        return drive.files().get(
            fileId=file_id,
            fields="id,name,parents,driveId,owners,permissions",
            supportsAllDrives=True
        ).execute()
    except HttpError as e:
        log.debug("get_file_meta(%s) -> HttpError %s", file_id, e)
        return None

def make_file_public(drive, file_id: str) -> None:
    """
    Set 'anyone with the link' -> reader.
    """
    file_id = clean_id(file_id)
    log.debug("Calling permissions.create on %s", file_id)
    drive.permissions().create(
        fileId=file_id,
        body={"type": "anyone", "role": "reader"},
        fields="id"
        # Note: permissions.create does not accept supportsAllDrives
    ).execute()
    log.info("Made public: %s", file_id)

def show_permissions(drive, file_id: str):
    """
    Print a compact view of current permissions.
    """
    try:
        perms_resp = drive.permissions().list(
            fileId=file_id,
            fields="permissions(id,type,role,domain,allowFileDiscovery)"
        ).execute()
        perms = perms_resp.get("permissions", [])
        if not perms:
            print("  (no permissions listed)")
            return
        for p in perms:
            print(f"  - id={p.get('id')} type={p.get('type')} role={p.get('role')} "
                  f"domain={p.get('domain')} discoverable={p.get('allowFileDiscovery')}")
    except HttpError as e:
        print("  (failed to list permissions):", e)

def test_scenario(drive, raw_id: str) -> int:
    """
    Run both tests:
      1) attempt with raw id (possibly bad, e.g., trailing '.')
      2) attempt with cleaned id
    Returns a process exit code (0=success, non-zero=failure)
    """
    exit_code = 0

    print("\n=== 0) Inputs ===")
    print("raw_id:   ", repr(raw_id))
    cleaned = clean_id(raw_id)
    print("cleaned:  ", repr(cleaned))

    print("\n=== 1) Existence check ===")
    exists_raw = file_exists(drive, raw_id)
    print(f"exists(raw_id)   = {exists_raw}")
    exists_clean = file_exists(drive, cleaned)
    print(f"exists(cleaned)  = {exists_clean}")

    print("\n=== 2) Try make public with RAW id ===")
    try:
        make_file_public(drive, raw_id)  # intentionally unclean
        print("RAW id: unexpectedly succeeded")
    except Exception as e:
        print("RAW id: expected failure ->", e)

    print("\n=== 3) Try make public with CLEANED id ===")
    try:
        make_file_public(drive, cleaned)
        print("CLEANED id: success ✅")
    except Exception as e:
        print("CLEANED id: failure ❌ ->", e)
        exit_code = 2

    print("\n=== 4) Verify metadata & permissions (cleaned) ===")
    meta = get_file_meta(drive, cleaned)
    if meta:
        print(f"File: {meta.get('name')}  (id={meta.get('id')})")
        print("Permissions:")
        show_permissions(drive, cleaned)
    else:
        print("Could not fetch file metadata (cleaned).")
        exit_code = max(exit_code, 1)

    return exit_code

def main():
    ap = argparse.ArgumentParser(description="Test make_file_public with raw vs cleaned Drive IDs.")
    ap.add_argument("--id", required=True, help="Drive file ID (you can paste with a trailing dot to test).")
    args = ap.parse_args()

    # Ensure credentials are available
    creds_path = os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "./scalapay/scalapay_mcp_kam/credentials.json"
    if not creds_path:
        log.warning("GOOGLE_APPLICATION_CREDENTIALS is not set. If you rely on ADC, ignore this.")

    print("[*] Building Drive service…")
    drive = build_drive()

    code = test_scenario(drive, args.id)
    sys.exit(code)

if __name__ == "__main__":
    main()
