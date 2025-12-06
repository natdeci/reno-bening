from langchain_core.documents import Document
from datetime import datetime, timezone, timedelta
import re

def parse_metadata_line(line: str, metadata: dict):
    key_map = {
        "file_id:": "file_id",
        "filename:": "filename",
        "document topic:": "topic",
        "chunk index:": "chunk_index",
    }
    low = line.lower()
    for prefix, key in key_map.items():
        if low.startswith(prefix):
            metadata[key] = line.split(":", 1)[1].strip()
            return True
    return False


def extract_metadata_and_text(lines):
    metadata = {}
    text_start_index = 0

    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue
        if line.strip() == "---text---":
            text_start_index = i
            break

        parse_metadata_line(line, metadata)

    return metadata, text_start_index


def build_documents(parts, base_metadata):
    docs = []
    for i, part in enumerate(parts):
        meta = base_metadata.copy()
        meta["chunk_index"] = i
        docs.append(Document(page_content=part.strip(), metadata=meta))
    return docs


def parse_faq(main_text, metadata):
    lines = main_text.splitlines()
    docs = []

    current_q, current_a, in_answer = None, [], False

    for line in lines:
        line = line.strip()
        if not line:
            continue

        if line.startswith("Q:"):
            save_previous_faq(current_q, current_a, docs, metadata)
            current_q, current_a, in_answer = line[2:].strip(), [], False
            continue

        if line.startswith("A:"):
            in_answer = True
            current_a.append(line[2:].strip())
            continue

        if in_answer:
            current_a.append(line)
        elif current_q is not None:
            current_q += " " + line

    save_previous_faq(current_q, current_a, docs, metadata)
    return docs or None


def save_previous_faq(current_q, current_a, docs, metadata):
    if current_q is None:
        return

    a_text = "\n".join(current_a).strip()
    meta = metadata.copy()
    meta["chunk_index"] = len(docs)
    if a_text:
        meta["answer"] = a_text
    docs.append(Document(page_content=current_q, metadata=meta))


def parse_chunk_text(chunk_text: str, default_metadata: dict = None):
    metadata = default_metadata.copy() if default_metadata else {}

    wib = timezone(timedelta(hours=7))
    metadata.setdefault(
        "uploaded_date",
        datetime.now(tz=wib).strftime("%Y-%m-%d %H:%M:%S")
    )

    if "---text---" in chunk_text:
        lines = chunk_text.splitlines()
        meta2, text_idx = extract_metadata_and_text(lines)
        metadata.update(meta2)

        text_body = "\n".join(lines[text_idx:])
        parts = [p.strip() for p in text_body.split("---text---") if p.strip()]
        return build_documents(parts, metadata)

    text_lines = []
    for line in chunk_text.splitlines():
        line = line.strip()
        if not line:
            continue
        if not parse_metadata_line(line, metadata):
            text_lines.append(line)

    main_text = "\n".join(text_lines).strip()

    faq_docs = parse_faq(main_text, metadata)
    if faq_docs:
        return faq_docs

    return [Document(page_content=main_text, metadata=metadata)]