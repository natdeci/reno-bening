import os
import base64
import fitz
import pdfplumber
import httpx
import requests
from dotenv import load_dotenv
from extraction.prompts.extract_prompt import ExtractPDFPrompts
from fastapi import UploadFile

load_dotenv()

MIN_TEXT_THRESHOLD = 100
IMAGE_DPI = 200

VLM_BASE_URL = os.getenv("OLLAMA_BASE_URL")
VLM_MODEL = os.getenv("VLM_MODEL")
VLM_TEMPERATURE = float(os.getenv("VLM_TEMPERATURE"))

class PDFExtractorHandler:
    def __init__(self):
        self.base_url = VLM_BASE_URL
        self.model = VLM_MODEL
        self.temperature = VLM_TEMPERATURE
        print("PDFExtractor handler initialized")

    def _analyze_page(self, fitz_page):
        text = fitz_page.get_text()
        if len(text) < MIN_TEXT_THRESHOLD:
            return True
        if len(fitz_page.get_drawings()) > 0:
            return True
        if len(fitz_page.get_images()) > 0:
            return True
        return False

    async def _call_vlm(self, image_bytes: bytes) -> str:
        try:
            image_b64 = base64.b64encode(image_bytes).decode("utf-8")
        except Exception as e:
            return f"[ERROR: Base64 encode failed - {e}]"

        payload = {
            "model": self.model,
            "stream": False,
            "messages": [
                {"role": "system", "content": ExtractPDFPrompts.SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": "Analyze the image.",
                    "images": [image_b64]
                }
            ]
        }

        try:
            async with httpx.AsyncClient(timeout=600.0) as client:
                resp = await client.post(
                    f"{self.base_url.rstrip('/')}/api/chat",
                    json=payload
                )
                resp.raise_for_status()
                data = resp.json()
                return data["message"]["content"]
        except requests.exceptions.RequestException as e:
            return f"[ERROR calling VLM: {e}]"

    async def extract_text(self, file: UploadFile, category: str) -> str:
        try:
            content = await file.read()
            all_pages = []
            if category == "panduan":
                with pdfplumber.open(file.file) as plumber_doc:
                    for plumber_page in plumber_doc.pages:
                        page_text = plumber_page.extract_text(x_tolerance=0.5)
                        if page_text is None:
                            page_text = ""
                        all_pages.append(page_text.strip())
                return "\n\n".join(all_pages)
            
            file.file.seek(0)

            with fitz.open(stream=content, filetype="pdf") as fitz_doc, \
                 pdfplumber.open(file.file) as plumber_doc: 
                for i in range(len(fitz_doc)):
                    fitz_page = fitz_doc.load_page(i)
                    plumber_page = plumber_doc.pages[i]

                    if self._analyze_page(fitz_page):
                        pix = fitz_page.get_pixmap(dpi=IMAGE_DPI)
                        page_text = await self._call_vlm(pix.tobytes("jpg"))
                    else:
                        page_text = plumber_page.extract_text(x_tolerance=0.5) or ""

                    all_pages.append(page_text.strip())

            return "\n\n".join(all_pages)

        except Exception as e:
            return f"[ERROR processing uploaded file {file.filename}: {e}]"
