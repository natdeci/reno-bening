from fastapi import APIRouter, UploadFile, File, Form, Depends
from typing import List
import re
import json
from .services.extractor import PDFExtractorHandler
from ingestion.chunking.document_processor import DocumentProcessor
from ingestion.ingest import parse_chunk_text
from ingestion.embedding import upsert_documents
from middleware.auth import verify_api_key
from .repository import ExtractRepository
import fitz
import time
from datetime import datetime
from zoneinfo import ZoneInfo


class PDFRoutes:
    def __init__(self):
        self.router = APIRouter()
        self.handler = PDFExtractorHandler()
        self.processor = DocumentProcessor()
        self.repository = ExtractRepository()
        self.timezone = "Asia/Jakarta"
        self.setup_routes()
        print("PDFExtractor routes initialized")

    def setup_routes(self):
        @self.router.post("/pdf")
        async def extract_pdf(
            id: str = Form(...),
            category: str = Form(...),
            filename: str = Form(...),
            file: UploadFile = File(...),
            key_checked: str = Depends(verify_api_key)
        ):
            print("Processing PDF")

            extract_start = datetime.now(ZoneInfo(self.timezone)).strftime("%Y-%m-%d %H:%M:%S")
            await self.repository.update_document_status("processing", int(id))

            try:
                text = await self.handler.extract_text(file, category)
                extract_end = time.time()
                
                # proses ingestion
                processed_chunks = await self.processor.process_text(
                    text,
                    doc_metadata={"file_id": id, "category": category, "filename": filename}
                )

                all_docs = []
                for chunk_data in processed_chunks:
                    chunk_meta = chunk_data.copy()
                    chunk_meta.pop("text", None)
                    docs = parse_chunk_text(chunk_data["text"], default_metadata=chunk_meta)
                    all_docs.extend(docs)

                upsert_documents(all_docs)

                extract_end = datetime.now(ZoneInfo(self.timezone)).strftime("%Y-%m-%d %H:%M:%S")

                print(f"[INFO] File ID: {id}, Filename: {filename}, Category: {category}, Start time: {extract_start}, End time: {extract_end}")

                await self.repository.update_document_status("finished", int(id))

                return {
                    "data": {
                        "id": id,
                        "category": category,
                        "filename": filename,
                        "chunks_upserted": len(all_docs)
                    }
                }
            except Exception as e:
                await self.repository.update_document_status("failed", int(id))
                return {
                    "data": {
                        "id": id,
                        "category": category,
                        "filename": filename,
                        "error": str(e)
                    }
                }
            finally:
                print("extract pdf completed (success or error)")

        @self.router.post("/txt")
        async def extract_txt(
            id: str = Form(...),
            category: str = Form(...),
            filename: str = Form(...),
            file: UploadFile = File(...),
            key_checked: str = Depends(verify_api_key)
        ):
            print("Processing TXT...")
            extract_start = datetime.now(ZoneInfo(self.timezone)).strftime("%Y-%m-%d %H:%M:%S")

            if not id.startswith("faq-"):
                await self.repository.update_document_status("processing", int(id))

            try:
                content = await file.read()
                text = content.decode("utf-8").strip()

                base_metadata = {
                    "file_id": id,
                    "category": category,
                    "filename": filename
                }

                has_delimiter = "---text---" in text
                has_faq_pattern = bool(re.search(r"(?mi)^\s*q\s*[:\-]", text))

                all_docs = []

            
                if has_delimiter or has_faq_pattern:
                    docs = parse_chunk_text(text, default_metadata=base_metadata)
                    all_docs.extend(docs)
                else:
                    processed_chunks = await self.processor.process_text(
                        text,
                        doc_metadata=base_metadata
                    )

                    for chunk_data in processed_chunks:
                        chunk_meta = chunk_data.copy()
                        chunk_meta.pop("text", None)
                        docs = parse_chunk_text(chunk_data["text"], default_metadata=chunk_meta)
                        all_docs.extend(docs)

                upsert_documents(all_docs)

                extract_end = datetime.now(ZoneInfo(self.timezone)).strftime("%Y-%m-%d %H:%M:%S")

                print(f"[INFO] File ID: {id}, Filename: {filename}, Category: {category}, Start time: {extract_start}, End time: {extract_end}")

                if not id.startswith("faq-"):
                    await self.repository.update_document_status("finished", int(id))

                return {
                    "data": {
                        "id": id,
                        "category": category,
                        "filename": filename,
                        "chunks_upserted": len(all_docs)
                    }
                }
            except Exception as e:
                if not id.startswith("faq-"):
                    await self.repository.update_document_status("failed", int(id))
                return {
                    "data": {
                        "id": id,
                        "category": category,
                        "filename": filename,
                        "error": str(e)
                    }
                }
            finally:
                print("extract txt completed (success or error)")
