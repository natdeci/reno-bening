from langchain_core.documents import Document
from datetime import datetime, timezone, timedelta
import re

def parse_chunk_text(chunk_text: str, default_metadata: dict = None):
    metadata = default_metadata.copy() if default_metadata else {}

    if "---text---" in chunk_text:
        lines = chunk_text.splitlines()
        text_start_index = 0

        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
            if line.strip() == "---text---":
                text_start_index = i
                break
            if line.lower().startswith("file_id:"):
                metadata["file_id"] = line.split(":", 1)[1].strip()
            elif line.lower().startswith("filename:"):
                metadata["filename"] = line.split(":", 1)[1].strip()
            elif line.lower().startswith("document topic:"):
                metadata["topic"] = line.split(":", 1)[1].strip()
            elif line.lower().startswith("chunk index:"):
                metadata["chunk_index"] = line.split(":", 1)[1].strip()

        text_body = "\n".join(lines[text_start_index:])
        parts = [p.strip() for p in text_body.split("---text---") if p.strip()]

        wib = timezone(timedelta(hours=7))
        metadata.setdefault(
            "uploaded_date",
            datetime.now(tz=wib).strftime("%Y-%m-%d %H:%M:%S")
        )

        documents = []
        for i, part in enumerate(parts):
            doc_meta = metadata.copy()
            doc_meta["chunk_index"] = i
            documents.append(Document(page_content=part, metadata=doc_meta))

        return documents  
    text_lines = []
    for line in chunk_text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.lower().startswith("file_id:"):
            metadata["file_id"] = line.split(":", 1)[1].strip()
        elif line.lower().startswith("filename:"):
            metadata["filename"] = line.split(":", 1)[1].strip()
        elif line.lower().startswith("chunk index:"):
            metadata["chunk_index"] = line.split(":", 1)[1].strip()
        else:
            text_lines.append(line)

    main_text = "\n".join(text_lines).strip()
    wib = timezone(timedelta(hours=7))
    metadata.setdefault("uploaded_date", datetime.now(tz=wib).strftime("%Y-%m-%d %H:%M:%S"))

    faq_pattern = r"Q:\s*(.*?)\s*A:\s*(.*?)(?=\s*Q:|\Z)"
    matches = re.findall(faq_pattern, main_text, flags=re.S)

    docs = []
    if matches:
        for i, (q, a) in enumerate(matches):
            q = q.strip()
            a = a.strip()
            faq_meta = metadata.copy()
            faq_meta["chunk_index"] = i
            if a:
                faq_meta["answer"] = a
            docs.append(Document(page_content=q, metadata=faq_meta))
        return docs

    return [Document(page_content=main_text, metadata=metadata)]
