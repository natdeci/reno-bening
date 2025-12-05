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
    TZ_JAKARTA = ZoneInfo("Asia/Jakarta") 
    def __init__(self):
        self.router = APIRouter()
        self.handler = PDFExtractorHandler()
        self.processor = DocumentProcessor()
        self.repository = ExtractRepository()
        self.setup_routes()
        print("PDFExtractor routes initialized")

    async def _update_status(self, status: str, doc_id: str):
        """Updates document status unless it is an FAQ document."""
        if not doc_id.startswith("faq-"):
            await self.repository.update_document_status(status, int(doc_id))

    async def _process_chunks(self, text: str, base_metadata: dict):
        """Handles chunking logic for both PDF + TXT."""
        processed_chunks = await self.processor.process_text(text, doc_metadata=base_metadata)

        all_docs = []
        for chunk_data in processed_chunks:
            chunk_meta = chunk_data.copy()
            chunk_meta.pop("text", None)
            docs = parse_chunk_text(chunk_data["text"], default_metadata=chunk_meta)
            all_docs.extend(docs)
        return all_docs

    def _log_info(self, id, filename, category, start, end):
        print(
            f"[INFO] File ID: {id}, Filename: {filename}, "
            f"Category: {category}, Start time: {start}, End time: {end}"
        )

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

            start = datetime.now(self.TZ_JAKARTA).strftime("%Y-%m-%d %H:%M:%S")
            await self._update_status("processing", id)

            try:
                text = await self.handler.extract_text(file, category)

                # proses ingestion
                metadata={"file_id": id, "category": category, "filename": filename}
                processed_chunks = await self._process_chunks(text, metadata)

                upsert_documents(processed_chunks)

                end = datetime.now(self.TZ_JAKARTA).strftime("%Y-%m-%d %H:%M:%S")

                self._log_info(id, filename, category, start, end)

                await self._update_status("finished", id)

                return {
                    "data": {
                        "id": id,
                        "category": category,
                        "filename": filename,
                        "chunks_upserted": len(processed_chunks)
                    }
                }
            except Exception as e:
                await self._update_status("failed", id)
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
            start = datetime.now(self.TZ_JAKARTA).strftime("%Y-%m-%d %H:%M:%S")

            await self._update_status("processing", id)

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
        
                if has_delimiter or has_faq_pattern:
                    all_chunks = parse_chunk_text(text, default_metadata=base_metadata)
                else:
                    all_chunks = await self._process_chunks(text, base_metadata)

                upsert_documents(all_chunks)

                end = datetime.now(self.TZ_JAKARTA).strftime("%Y-%m-%d %H:%M:%S")

                self._log_info(id, filename, category, start, end)

                await self._update_status("finished", id)

                return {
                    "data": {
                        "id": id,
                        "category": category,
                        "filename": filename,
                        "chunks_upserted": len(all_chunks)
                    }
                }
            except Exception as e:
                if not id.startswith("faq-"):
                    await self._update_status("failed", id)
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
