import os
import re
import requests
import pdfplumber
import docx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional

app = FastAPI()

class FilePathInput(BaseModel):
    file_path: str

def download_from_drive(url: str, save_path: Optional[str] = None) -> str:
    try:
        if "drive.google.com" in url:
            if "id=" in url:
                file_id = url.split("id=")[1]
            elif "/d/" in url:
                file_id = url.split("/d/")[1].split("/")[0]
            else:
                raise ValueError("Invalid Google Drive link format")

            download_url = f"https://drive.google.com/uc?export=download&id={file_id}"
            r = requests.get(download_url, allow_redirects=True)
            
            # Determine extension based on content-type if save_path not provided
            if not save_path:
                content_type = r.headers.get('Content-Type', '')
                if 'pdf' in content_type:
                    save_path = "resume_tmp.pdf"
                elif 'wordprocessingml.document' in content_type:
                    save_path = "resume_tmp.docx"
                else:
                    save_path = "resume_tmp"  # Fallback

            with open(save_path, "wb") as f:
                f.write(r.content)
            return save_path
        else:
            # If not Google Drive, assume it's a local path or direct URL
            if url.startswith("http"):
                r = requests.get(url, allow_redirects=True)
                with open(save_path, "wb") as f:
                    f.write(r.content)
                return save_path
            return url  # Local path
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to download file: {e}")

def extract_text_from_pdf(file_path: str) -> str:
    text_content = ""
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            text_content += page.extract_text() + "\n"
    return text_content

def extract_text_from_docx(file_path: str) -> str:
    doc = docx.Document(file_path)
    return "\n".join([para.text for para in doc.paragraphs])

def extract_resume_text(file_path: str) -> str:
    # Handle download if it's a URL
    local_file = file_path
    extension = ""
    if file_path.startswith("http"):
        # Determine tentative extension
        if "pdf" in file_path.lower():
            extension = ".pdf"
        elif "docx" in file_path.lower():
            extension = ".docx"
        else:
            extension = ""
        local_file = "resume_tmp" + extension
        local_file = download_from_drive(file_path, local_file)
    else:
        # Local file, get extension
        extension = os.path.splitext(file_path)[1].lower()

    if not os.path.exists(local_file):
        raise HTTPException(status_code=404, detail=f"File not found: {local_file}")

    # Extract text based on extension
    if extension == ".pdf":
        text_content = extract_text_from_pdf(local_file)
    elif extension == ".docx":
        text_content = extract_text_from_docx(local_file)
    else:
        raise HTTPException(status_code=400, detail="Unsupported file format. Please use PDF or DOCX.")

    # Clean up temp file if downloaded
    if file_path.startswith("http") and os.path.exists(local_file):
        os.remove(local_file)

    return text_content

@app.post("/extract")
def extract_endpoint(input_data: FilePathInput):
    try:
        text = extract_resume_text(input_data.file_path)
        return {"extracted_content": text}
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error extracting resume: {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)