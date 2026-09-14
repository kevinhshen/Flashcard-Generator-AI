"""Pure note normalization, segmentation, and sentence splitting."""

from __future__ import annotations

import re

from .models import ChunkKind, SourceChunk


LABEL_PATTERN = re.compile(r"^(?P<label>[A-Za-z0-9][^:\n]{0,59}):\s*(?P<content>.*)$")
FALLBACK_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9])")


def clean_text(text: str) -> str:
    """Normalize spacing without destroying meaningful paragraph breaks."""
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [re.sub(r"[^\S\n]+", " ", line).strip() for line in normalized.split("\n")]
    normalized = "\n".join(lines)
    return re.sub(r"\n{3,}", "\n\n", normalized).strip()


def _is_uppercase_heading(line: str) -> bool:
    letters = "".join(character for character in line if character.isalpha())
    return bool(letters) and letters.isupper() and len(line) <= 80 and not line.endswith((".", "?", "!"))


def _next_nonempty_line(lines: list[str], index: int) -> str | None:
    for following_line in lines[index + 1 :]:
        if following_line:
            return following_line
    return None


def _is_title_like(line: str) -> bool:
    """Identify short, punctuation-free text that is formatted like a heading."""
    return bool(line) and len(line) <= 80 and line[0].isupper() and not line.endswith((".", "?", "!", ":"))


def _is_structural_heading(line: str, index: int, lines: list[str]) -> bool:
    """Recognize headings from their formatting and their relationship to the next block."""
    if _is_uppercase_heading(line):
        return True

    next_line = _next_nonempty_line(lines, index)
    if not next_line or not _is_title_like(line):
        return False

    return _is_uppercase_heading(next_line) or bool(LABEL_PATTERN.match(next_line))


def segment_chunks(text: str) -> list[SourceChunk]:
    """Split notes into labelled and paragraph chunks without cross-contamination."""
    lines = clean_text(text).split("\n")
    chunks: list[SourceChunk] = []
    paragraph_lines: list[str] = []

    def append_chunk(kind: ChunkKind, content: str, label: str | None = None) -> None:
        content = " ".join(content.split())
        if content:
            chunks.append(
                SourceChunk(
                    source_id=f"chunk-{len(chunks) + 1}",
                    text=content,
                    kind=kind,
                    label=label,
                )
            )

    def flush_paragraph() -> None:
        nonlocal paragraph_lines
        append_chunk("paragraph", " ".join(paragraph_lines))
        paragraph_lines = []

    index = 0
    while index < len(lines):
        line = lines[index]
        if not line:
            flush_paragraph()
            index += 1
            continue

        label_match = LABEL_PATTERN.match(line)
        if not label_match:
            if _is_structural_heading(line, index, lines):
                flush_paragraph()
                index += 1
                continue
            paragraph_lines.append(line)
            index += 1
            continue

        flush_paragraph()
        label = label_match.group("label").strip()
        content_lines = [label_match.group("content").strip()]
        index += 1

        while index < len(lines):
            next_line = lines[index]
            if not next_line or LABEL_PATTERN.match(next_line):
                break
            content_lines.append(next_line)
            index += 1

        append_chunk("labeled", " ".join(content_lines), label=label)

    flush_paragraph()
    return chunks


def split_sentences(text: str) -> list[str]:
    """Use NLTK when available, with a deterministic offline fallback."""
    normalized = " ".join(text.split())
    if not normalized:
        return []

    try:
        from nltk.tokenize import sent_tokenize

        sentences = sent_tokenize(normalized)
    except (ImportError, LookupError):
        sentences = FALLBACK_SENTENCE_BOUNDARY.split(normalized)

    return [sentence.strip() for sentence in sentences if sentence.strip()]
