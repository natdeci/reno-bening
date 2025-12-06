import re
import os
from langchain_text_splitters import RecursiveCharacterTextSplitter


def remove_unwanted_lines(text, max_placeholder_words=3):
    patterns = [
        r'SK\s*No\s*\d+\s*[A-Z]*\s*\n*',
        r'PRESIDEN\s*\n*',
        r'REPUBLIK\s+INDONESIA\s*\n*',
        r'REPUBLIC\s+INDONESIA\s*\n*',
        r'-\s*\d+\s*-'
    ]
    
    cleaned_text = text
    for pattern in patterns:
        cleaned_text = re.sub(pattern, '', cleaned_text, flags=re.IGNORECASE)
    
    lines = [line.strip() for line in cleaned_text.splitlines() if line.strip()]
    
    filtered_lines = []
    for line in lines:
        if re.fullmatch(r'[.\s]+', line):  
            continue

        if re.fullmatch(r'\d+\.\s*(?:\.\s){2,}\.', line):
            continue

        if re.search(r'(?:\.\s){2,}\.\s*$', line):
            continue

        words = line.split()
        if len(words) <= max_placeholder_words and re.search(r'(?:\.\s){2,}\.\s*$', line):
            continue


        filtered_lines.append(line)
    
    return "\n".join(filtered_lines)


def recursive_chunking(text, chunk_size=2000, chunk_overlap=300):
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ".", "!", "?", " ", ""]
    )
    return splitter.split_text(text)

def _extract_filename(filename):
    return os.path.splitext(filename)[0] if filename else None


def _handle_no_pasal(text, filename, max_chunk_size):
    chunks = recursive_chunking(text, chunk_size=max_chunk_size, chunk_overlap=300)
    return [f"{filename}\n\n{c}" for c in chunks] if filename else chunks


def _split_preamble(text, first_pasal_index, filename, max_chunk_size):
    preamble = text[:first_pasal_index].strip()
    if not preamble:
        return []

    chunks = recursive_chunking(preamble, chunk_size=max_chunk_size, chunk_overlap=300)
    return [f"{filename}\n\n{c}" for c in chunks]


def _process_single_pasal(match, next_start, text, filename, max_chunk_size):
    start = match.start()
    end = next_start if next_start else len(text)

    pasal_block = text[start:end].strip()
    header = match.group().strip()

    m = re.match(r'Pasal\s+(\d+[a-z]?)', header, flags=re.IGNORECASE)
    pasal_number = m.group(1)

    content = pasal_block[len(header):].strip()

    header_tag = f"{filename}\nPasal {pasal_number}\n\n"
    combined = header_tag + content

    if len(combined) > max_chunk_size:
        sub_chunks = recursive_chunking(content, chunk_size=max_chunk_size, chunk_overlap=300)
        return [header_tag + sc for sc in sub_chunks]

    return [combined]


def _split_tail(text, end_index, filename, max_chunk_size):
    tail = text[end_index:].strip()
    if not tail:
        return []

    chunks = recursive_chunking(tail, chunk_size=max_chunk_size, chunk_overlap=300)
    return [f"{filename}\n\n{c}" for c in chunks]


def split_by_pasal(text, filename=None, max_chunk_size=2000):
    filename = _extract_filename(filename)

    pasal_pattern = r'(?m)^\s*Pasal\s+\d+[a-z]?\s*$'
    pasal_matches = list(re.finditer(pasal_pattern, text))

    if not pasal_matches:
        return _handle_no_pasal(text, filename, max_chunk_size)

    final_chunks = []

    final_chunks.extend(
        _split_preamble(text, pasal_matches[0].start(), filename, max_chunk_size)
    )

    for i, match in enumerate(pasal_matches):
        next_start = pasal_matches[i + 1].start() if i + 1 < len(pasal_matches) else None
        final_chunks.extend(
            _process_single_pasal(match, next_start, text, filename, max_chunk_size)
        )

    final_chunks.extend(
        _split_tail(text, pasal_matches[-1].end(), filename, max_chunk_size)
    )

    return final_chunks
