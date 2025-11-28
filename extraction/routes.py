from fastapi import APIRouter, UploadFile, File, Form, Depends
from typing import List
import re
import json
from .services.excel_extractor import ExcelExtractorHandler  
from .services.extractor import PDFExtractorHandler
from ingestion.chunking.document_processor import DocumentProcessor
from ingestion.ingest import parse_chunk_text
from ingestion.embedding import upsert_documents
from middleware.auth import verify_api_key
from .repository import ExtractRepository

class PDFRoutes:
    def __init__(self):
        self.router = APIRouter()
        self.handler = PDFExtractorHandler()
        self.excel_handler = ExcelExtractorHandler()
        self.processor = DocumentProcessor()
        self.repository = ExtractRepository()
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
            print("Processing...")
            await self.repository.update_document_status("processing", int(id))

            try:
                text = await self.handler.extract_text(file, category)
                
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
                
                # qdrant
                upsert_documents(all_docs)

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
        
        @self.router.post("/excel")
        async def extract_excel(
            id: str = Form(...),
            category: str = Form(None),
            file: UploadFile = File(...),
            key_checked: str = Depends(verify_api_key)
        ):
            text = await self.excel_handler.extract_text(file, category)

            # proses ingestion
            processed_chunks = await self.processor.process_text(
                text,
                doc_metadata={"file_id": id, "category": category, "filename": file.filename}
            )

            all_docs = []
            for chunk_data in processed_chunks:
                chunk_meta = chunk_data.copy()
                chunk_meta.pop("text", None)
                chunk_meta.pop("description", None)

                chunk_text = (
                    f"Document Title: {chunk_data.get('filename','')}\n"
                    f"Document Topic: {chunk_data.get('topic','')}\n"
                    f"Chunk_Description: {chunk_data.get('description','')}\n"
                    f"{chunk_data.get('text','')}"
                )
                docs = parse_chunk_text(chunk_text, default_metadata=chunk_meta)
                all_docs.extend(docs)

            upsert_documents(all_docs)

            return {
                "data": {
                    "id": id,
                    "category": category,
                    "filename": file.filename,
                    "chunks_upserted": len(all_docs)
                }
            }

        @self.router.post("/txt")
        async def extract_txt(
            id: str = Form(...),
            category: str = Form(...),
            filename: str = Form(...),
            file: UploadFile = File(...),
            key_checked: str = Depends(verify_api_key)
        ):
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

                # --- Upsert ke Qdrant ---
                upsert_documents(all_docs)

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
                print("extract txt completed (success or error)")
