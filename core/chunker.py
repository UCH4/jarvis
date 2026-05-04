import re
from typing import List, Dict

def markdown_aware_chunks(text: str, title: str = "", chunk_size: int = 1600, overlap: int = 300) -> List[Dict[str, str]]:
    """Split markdown text into chunks aware of headings.

    Each chunk is a dict with keys:
        - "content": the text content of the chunk
        - "section": the most recent heading (e.g., "## Section")
        - "title": the document title (passed in)
    The algorithm:
        1. Find all headings using regex for lines starting with '#'.
        2. Build a list of (section_name, start_idx, end_idx) ranges.
        3. For each section, split its body into sized chunks with overlap.
        4. If no headings are found, fallback to simple chunking with a dummy section.
    """
    headings = []
    for match in re.finditer(r'^(#{1,6})\s+(.*)', text, re.MULTILINE):
        level = len(match.group(1))
        heading = match.group(2).strip()
        headings.append((level, heading, match.start()))
    # Append sentinel for end of text
    headings.append((0, "", len(text)))

    chunks: List[Dict[str, str]] = []
    if len(headings) <= 1:
        # No headings – simple split
        start = 0
        while start < len(text):
            end = min(start + chunk_size, len(text))
            chunk_text = text[start:end].strip()
            if chunk_text:
                chunks.append({"content": chunk_text, "section": "", "title": title})
            start += chunk_size - overlap
        return chunks

    # Process each heading region
    for i in range(len(headings) - 1):
        level, heading, start_idx = headings[i]
        _, _, end_idx = headings[i + 1]
        section_body = text[start_idx:end_idx]
        # Remove the heading line itself from body
        heading_line_match = re.match(r'^(#{1,6})\s+.*\n?', section_body)
        if heading_line_match:
            body = section_body[heading_line_match.end():]
        else:
            body = section_body
        # Chunk the body
        pos = 0
        while pos < len(body):
            chunk_end = min(pos + chunk_size, len(body))
            chunk_text = body[pos:chunk_end].strip()
            if chunk_text:
                chunks.append({
                    "content": chunk_text,
                    "section": heading,
                    "title": title,
                })
            pos += chunk_size - overlap
    return chunks
