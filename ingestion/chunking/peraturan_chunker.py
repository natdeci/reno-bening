import re
import os
from langchain_text_splitters import RecursiveCharacterTextSplitter
DEBUG = True

def debug_log(title, content=None):
    if not DEBUG:
        return
    print(f"\n[DEBUG] {title}")
    if content is not None:
        print(content)



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

    pasal_pattern = re.compile(r'(?m)^\s*Pasal\s+(\d+)\s*$', flags=re.IGNORECASE)

    pasal_pattern_sub = re.compile(r'(?m)^\s*Pasal\s+(\d+[a-z])\s*$', flags=re.IGNORECASE)

    perubahan_start_pattern = re.compile(
        r'(?m)^\s*Pasal\s+(\d+[a-z]?)\s*\n\s*Beberapa\s+ketentuan\s+dalam',
        flags=re.IGNORECASE
    )

    pasal_matches = list(pasal_pattern.finditer(text))
    debug_log(
        "PASAL HEADER TERDETEKSI",
        "\n".join(
            f"idx={i} | pos={m.start()} | '{m.group().strip()}'"
            for i, m in enumerate(pasal_matches)
        )
    )

    if not pasal_matches:
        return _handle_no_pasal(text, filename, max_chunk_size)

    final_chunks = []

    final_chunks.extend(_split_preamble(text, pasal_matches[0].start(), filename, max_chunk_size))

    n = len(pasal_matches)
    i = 0

    while i < n:
       
        match = pasal_matches[i]
        curr_start = match.start()
        curr_header = match.group().strip()
        curr_num_raw = match.group(1)

        debug_log(
            f"PROSES PASAL INDEX {i}",
            f"header='{curr_header}' | raw_num='{curr_num_raw}' | start={curr_start}"
        )


        if pasal_pattern_sub.match(curr_header):
            i += 1
            continue

        curr_num_match = re.search(r'\d+', curr_num_raw)
        curr_pasal_num = int(curr_num_match.group(0)) if curr_num_match else None

        default_next_start = pasal_matches[i + 1].start() if (i + 1) < n else len(text)

        look_region_end = min(len(text), match.end() + 8000)
        after_header_segment = text[match.end():look_region_end]
        is_perubahan = bool(re.match(r'^\s*Beberapa\s+ketentuan\s+dalam', after_header_segment, flags=re.IGNORECASE))

        if not is_perubahan:

            pasal_block = text[curr_start:default_next_start].strip()
            debug_log(
                f"ISI PASAL {curr_num_raw} (300 char awal)",
                pasal_block[:300]
            )


            header_tag = f"{filename}\nPasal {curr_num_raw}\n\n" if filename else f"Pasal {curr_num_raw}\n\n"
            content = pasal_block[len(curr_header):]
            combined = header_tag + content

            if len(combined) > max_chunk_size:
                debug_log(
                    f"SUB-CHUNKING PASAL {curr_num_raw}",
                    f"panjang={len(combined)}"
                )

                sub_chunks = recursive_chunking(content, chunk_size=max_chunk_size, chunk_overlap=300)

                for idx, sc in enumerate(sub_chunks):
                    debug_log(
                        f"SUB-CHUNK {idx} PASAL {curr_num_raw}",
                        sc[:200]
                    )

                    if idx == 0:
                        final_chunks.append(header_tag + sc)
                    else:
                        continued_header = header_tag.strip() + "\n\n"
                        final_chunks.append(continued_header + sc.lstrip())
            else:
                final_chunks.append(combined)

            i += 1
            continue
        next_perubahan = perubahan_start_pattern.search(text, match.end())
        candidate_end = next_perubahan.start() if next_perubahan else len(text)

        modified_set = set()
        for m in re.finditer(r'(?i)Ketentuan\s+Pasal\s+(\d+)', text[match.end():candidate_end]):
            try:
                modified_set.add(int(m.group(1)))
            except:
                continue

        inner_pasals = list(pasal_pattern.finditer(text, match.end(), candidate_end))
        block_end = candidate_end

        if modified_set:
            for p in inner_pasals:
                pn_match = re.search(r'\d+', p.group(1))
                if not pn_match:
                    continue

                pn = int(pn_match.group(0))

                if pn not in modified_set:
                    block_end = p.start()
                    break
        else:
            for p in inner_pasals:
                pn_match = re.search(r'\d+', p.group(1))
                if not pn_match:
                    continue

                pn = int(pn_match.group(0))

                if curr_pasal_num is not None and pn > curr_pasal_num:
                    block_end = p.start()
                    break

        pasal_block = text[curr_start:block_end].strip()
        header_tag = f"{filename}\n{curr_header}\n\n" if filename else f"{curr_header}\n\n"
        content = pasal_block[len(curr_header):]
        combined = header_tag + content

        if len(combined) > max_chunk_size:
            sub_chunks = recursive_chunking(content, chunk_size=max_chunk_size, chunk_overlap=300)
            for idx, sc in enumerate(sub_chunks):
                if idx == 0:
                    final_chunks.append(header_tag + sc)
                else:
                    final_chunks.append(header_tag + sc)
        else:
            final_chunks.append(combined)

        i += 1

        while i < n and pasal_matches[i].start() < block_end:
            i += 1

    last_end = 0
    for m in pasal_matches:
        if m.end() > last_end and m.end() <= len(text):
            last_end = m.end()

    final_chunks.extend(_split_tail(text, last_end, filename, max_chunk_size))
    debug_log("TOTAL FINAL CHUNK", len(final_chunks))

    for idx, c in enumerate(final_chunks, 1):
        debug_log(
            f"FINAL CHUNK {idx} HEADER",
            c[:200]
        )

    return final_chunks