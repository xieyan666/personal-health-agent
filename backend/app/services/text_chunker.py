"""Paragraph-aware document chunking.

Prefer semantic boundaries (headings and blank-line separated paragraphs)
over hard character cuts.  Character size remains only a constraint:
CHUNK_SIZE caps a chunk, CHUNK_OVERLAP keeps a short tail of the previous
chunk so context is not lost across boundaries.
"""

from __future__ import annotations

import re

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200

_TITLE_RE = re.compile(r"^(?:#{1,6}\s+.*|第[一二三四五六七八九十百千0-9]+[章节部分篇卷].*)$")


def _paragraphs(text: str) -> list[str]:
    """Split on blank lines, keeping heading lines attached to their content."""
    lines = text.splitlines()
    blocks: list[list[str]] = []
    current: list[str] = []
    for line in lines:
        if line.strip():
            current.append(line)
            continue
        if current:
            blocks.append(current)
            current = []
    if current:
        blocks.append(current)
    return ["\n".join(block).strip() for block in blocks if "\n".join(block).strip()]


def split_text(text: str) -> list[str]:
    if not text or not text.strip():
        return []
    chunks: list[str] = []
    buffer = ""
    for paragraph in _paragraphs(text):
        if len(paragraph) >= CHUNK_SIZE:
            # A single oversized paragraph (no blank lines) still needs hard
            # cuts; carry a small overlap for continuity.
            if buffer:
                chunks.append(buffer)
                buffer = ""
            start = 0
            while start < len(paragraph):
                chunks.append(paragraph[start : start + CHUNK_SIZE])
                if start + CHUNK_SIZE >= len(paragraph):
                    break
                start += CHUNK_SIZE - CHUNK_OVERLAP
            continue
        if buffer and len(buffer) + 1 + len(paragraph) > CHUNK_SIZE:
            chunks.append(buffer)
            tail = buffer[-CHUNK_OVERLAP:] if len(buffer) > CHUNK_OVERLAP else buffer
            buffer = tail
        buffer = f"{buffer}\n{paragraph}" if buffer else paragraph
    if buffer:
        chunks.append(buffer)
    return chunks
