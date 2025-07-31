import os
import time
import asyncio
import pandas as pd
import matplotlib.pyplot as plt

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

import GoogleApiSupport.slides as slides
import GoogleApiSupport.drive as drive

# Set credentials
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = "scalapay/scalapay_mcp_kam/credentials.json"

SERVICE_ACCOUNT_FILE = 'credentials.json'
SCOPES = ['https://www.googleapis.com/auth/drive', 'https://www.googleapis.com/auth/presentations']
drive_service = build('drive', 'v3')


async def create_slides(string: str) -> dict:
    print("[DEBUG] Starting create_slides function")
    print(f"[DEBUG] Input string: {string}")
    
    # 1. Static Data
    data = {
        "Month": ["Jan", "Feb", "Mar", "Apr", "May", "Jun"],
        "Sales": [4174, 4507, 1860, 2294, 2130, 3468],
        "Profit": [1244, 321, 666, 1438, 530, 892]
    }
    df = pd.DataFrame(data)
    print("[DEBUG] DataFrame created successfully")

    # 2. Create PNG chart
    chart_path = "/tmp/monthly_sales_profit_chart.png"
    try:
        plt.figure(figsize=(8, 5))
        plt.plot(df["Month"], df["Sales"], marker='o', label='Sales')
        plt.plot(df["Month"], df["Profit"], marker='o', label='Profit')
        plt.title("Monthly Sales and Profit", fontsize=16)
        plt.xlabel("Month", fontsize=12)
        plt.ylabel("Amount", fontsize=12)
        plt.legend()
        plt.savefig(chart_path, dpi=300)
        plt.close()
        print(f"[✓] Chart saved to: {chart_path}")
        
        # Verify local file exists
        if os.path.exists(chart_path):
            file_size = os.path.getsize(chart_path)
            print(f"[DEBUG] Local file confirmed - Size: {file_size} bytes")
        else:
            print(f"[✗] Local file not found at {chart_path}")
            
    except Exception as e:
        print(f"[✗] Chart creation failed: {e}")
        print(f"[DEBUG] Error type: {type(e).__name__}")
        return {"error": "Chart creation failed"}

    # 3. Prepare Google Slides
    PRESENTATION_ID = '1hDkICKx4D3jHdxky_3_1iJcPFVQFxTkvlH7mVSFCx_o'
    folder_id = '1x03ugPUeGSsLYY2kH-FsNC9_f_M6iLGL'
    
    print(f"[DEBUG] Template presentation ID: {PRESENTATION_ID}")
    print(f"[DEBUG] Target folder ID: {folder_id}")

    try:
        output_file_id = drive.copy_file(PRESENTATION_ID, 'final_presentation')
        print(f"[DEBUG] File copied successfully, new ID: {output_file_id}")
        
        drive.move_file(output_file_id, folder_id)
        print(f"[✓] Copied presentation to ID: {output_file_id} and moved to folder: {folder_id}")
        
        slides.batch_text_replace({'bot': string}, output_file_id)
        print(f"[DEBUG] Text replacement completed")
        
    except Exception as e:
        print(f"[✗] Slides preparation failed: {e}")
        print(f"[DEBUG] Error type: {type(e).__name__}")
        return {"error": "Slides preparation failed"}

    # 4. Upload chart image to Google Drive
    print(f"[→] Uploading chart image to Drive...")
    print(f"[DEBUG] Local file path: {chart_path}")
    print(f"[DEBUG] Target folder ID: {folder_id}")
    
    try:
        upload_result = drive.upload_file(
            file_name="monthly_sales_profit_chart.png",
            parent_folder_id=[folder_id],
            local_file_path=chart_path
        )
        print(f"[DEBUG] Upload result: {upload_result}")
        
        chart_file_id = upload_result.get('file_id')
        print(f"[✓] Uploaded chart, file ID: {chart_file_id}")
        
        if not chart_file_id:
            print(f"[✗] No file ID returned from upload!")
            return {"error": "Upload failed - no file ID"}
            
    except Exception as e:
        print(f"[✗] Upload failed: {e}")
        print(f"[DEBUG] Error type: {type(e).__name__}")
        print(f"[DEBUG] Error details: {str(e)}")
        return {"error": "Upload failed"}

    # Debug: Wait longer and then check the file exists
    print("[DEBUG] Waiting 5 seconds for file to be fully processed...")
    time.sleep(5)
    
    # Method 1: Direct file get
    try:
        meta = drive_service.files().get(fileId=chart_file_id, fields="id, name, parents, size, mimeType").execute()
        print(f"[✓] File exists via direct get: {meta}")
    except HttpError as e:
        print(f"[✗] HttpError during file get: {e}")
        print(f"[DEBUG] Error status: {e.resp.status}")
        print(f"[DEBUG] Error reason: {e.resp.reason}")
        print(f"[DEBUG] Error content: {e.content}")
    except Exception as e:
        print(f"[✗] File not found after upload: {e}")
        print(f"[DEBUG] Error type: {type(e).__name__}")
        print(f"[DEBUG] Error details: {str(e)}")

    # Method 2: List files in folder to verify upload
    try:
        print("[DEBUG] Listing files in target folder...")
        results = drive_service.files().list(
            q=f"'{folder_id}' in parents and name='monthly_sales_profit_chart.png'",
            fields="files(id, name, size, parents, mimeType)"
        ).execute()
        files = results.get('files', [])
        print(f"[DEBUG] Files found in folder: {files}")
        
        if files:
            found_file = files[0]
            if found_file['id'] == chart_file_id:
                print(f"[✓] File ID matches: {chart_file_id}")
            else:
                print(f"[!] File ID mismatch! Expected: {chart_file_id}, Found: {found_file['id']}")
        else:
            print(f"[✗] No files found with that name in folder {folder_id}")
            
    except Exception as e:
        print(f"[✗] Error listing files in folder: {e}")
        print(f"[DEBUG] Error type: {type(e).__name__}")

    # Method 3: List all permissions on the file
    try:
        print("[DEBUG] Checking current file permissions...")
        perms = drive_service.permissions().list(fileId=chart_file_id).execute()
        print(f"[DEBUG] Current permissions before making public: {perms.get('permissions')}")
    except Exception as e:
        print(f"[✗] Failed to list initial permissions: {e}")
        print(f"[DEBUG] Error type: {type(e).__name__}")

    # 5. Make file publicly accessible
    print("[DEBUG] Making file publicly accessible...")
    try:
        permission_body = {'type': 'anyone', 'role': 'reader'}
        permission_response = drive_service.permissions().create(
            fileId=chart_file_id,
            body=permission_body,
            fields='id'
        ).execute()
        print(f"[✓] Made image public, permission ID: {permission_response['id']}")
        
        # Wait a bit for permission to propagate
        print("[DEBUG] Waiting 3 seconds for permissions to propagate...")
        time.sleep(3)
        
    except HttpError as e:
        print(f"[✗] HttpError setting public permissions: {e}")
        print(f"[DEBUG] Error status: {e.resp.status}")
        print(f"[DEBUG] Error reason: {e.resp.reason}")
    except Exception as e:
        print(f"[✗] Failed to set public permissions: {e}")
        print(f"[DEBUG] Error type: {type(e).__name__}")

    # 6. Get direct URL
    direct_url = f"https://drive.google.com/uc?export=view&id={chart_file_id}"
    
    print(f"[DEBUG] Primary URL: {direct_url}")

    try:
        slides.batch_replace_shape_with_image(
            {'image1': direct_url, 'image2': direct_url},
            output_file_id
        )
        print(f"[✓] Image inserted successfully using: {direct_url}")
        image_success = True
    except Exception as e:
        print(f"[DEBUG] Error type: {type(e).__name__}")
        print(f"[DEBUG] Error details: {str(e)}")

    if not image_success:
        print("[✗] All image URLs failed — presentation will not include chart image.")

    # 8. Final PDF export
    print("[DEBUG] Starting PDF export...")
    try:
        info = slides.get_presentation_info(output_file_id)
        # print(f"[DEBUG] Presentation info: {info}")
        
        pdf_path = f"/tmp/{output_file_id}.pdf"
        slides.download_presentation_as_pdf(drive_service, output_file_id, pdf_path)
        print(f"[✓] Presentation PDF saved to {pdf_path}")
        
        # Verify PDF was created
        if os.path.exists(pdf_path):
            pdf_size = os.path.getsize(pdf_path)
            print(f"[DEBUG] PDF file confirmed - Size: {pdf_size} bytes")
        else:
            print(f"[✗] PDF file not found at {pdf_path}")
            
    except Exception as e:
        print(f"[✗] PDF export failed: {e}")
        print(f"[DEBUG] Error type: {type(e).__name__}")
        pdf_path = None

    print("[DEBUG] Function completing...")
    return {
        "pdf_path": pdf_path,
        "chart_file_id": chart_file_id,
        "chart_image_url": direct_url,
        "image_insertion_success": image_success,
        "presentation_id": output_file_id
    }


# 🔧 ENTRY POINT
"""
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