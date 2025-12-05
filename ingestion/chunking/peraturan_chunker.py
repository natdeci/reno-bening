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

        # Only dots
        if re.fullmatch(r'(\s*\.\s*)+', line):
            continue

        # "6. Pemerintah . ." pattern
        if re.fullmatch(r'(\d+\.\s*\w*\s*(\.\s*)+)', line):
            continue

        words = line.split()
        if len(words) <= max_placeholder_words and re.search(r'(\.\s*){2,}$', line):
            continue

        if re.search(r'(\.\s*){2,}$', line):
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



def split_by_pasal(text, filename=None, max_chunk_size=2000):
    if filename:
        filename = os.path.splitext(filename)[0]

    pasal_pattern = r'(?m)^\s*Pasal\s+\d+[A-Za-z]?\s*$'
    pasal_matches = [m for m in re.finditer(pasal_pattern, text)]

    # Jika tidak ada pasal sama sekali → recursive full
    if not pasal_matches:
        chunks = recursive_chunking(text, chunk_size=max_chunk_size, chunk_overlap=300)
        if filename:
            chunks = [f"{filename}\n\n{c}" for c in chunks]
        return chunks

    final_chunks = []
    last_pos = 0

    first_pasal = pasal_matches[0].start()
    preamble = text[:first_pasal].strip()
    if preamble:
        preamble_chunks = recursive_chunking(preamble, chunk_size=max_chunk_size, chunk_overlap=300)
        for c in preamble_chunks:
            final_chunks.append(f"{filename}\n\n{c}")

    for i, match in enumerate(pasal_matches):

        start = match.start()
        end = pasal_matches[i+1].start() if i + 1 < len(pasal_matches) else len(text)

        pasal_block = text[start:end].strip()

        header_line = match.group().strip()
        m = re.match(r'Pasal\s+(\d+[A-Za-z]?)', header_line, flags=re.IGNORECASE)
        pasal_number = m.group(1)

        content = pasal_block[len(header_line):].strip()

        combined = f"{filename}\nPasal {pasal_number}\n\n{content}"

        if len(combined) > max_chunk_size:
            sub_chunks = recursive_chunking(content, chunk_size=max_chunk_size, chunk_overlap=300)
            for sc in sub_chunks:
                final_chunks.append(f"{filename}\nPasal {pasal_number}\n\n{sc}")
        else:
            final_chunks.append(combined)

    last_pasal_end = pasal_matches[-1].end()
    tail = text[last_pasal_end:].strip()

    if tail:
        tail_chunks = recursive_chunking(tail, chunk_size=max_chunk_size, chunk_overlap=300)
        for c in tail_chunks:
            final_chunks.append(f"{filename}\n\n{c}")

    return final_chunks
