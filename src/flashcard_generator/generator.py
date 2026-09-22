"""Deterministic, offline flashcard generation.

The local generator is deliberately conservative: every answer is copied from
the supplied notes, so it remains useful when Ollama is unavailable and cannot
invent facts that were not in the source material.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import asdict, dataclass


@dataclass(frozen=True, slots=True)
class Flashcard:
    front: str
    back: str
    card_type: str = "basic"
    source: str = ""

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


_LABEL_RE = re.compile(r"^([A-Za-z][^:\n]{0,79}):\s*(.*)$")
_DEFINITION_PATTERNS = (
    re.compile(r"^(.+?)\s+(?:is|are)\s+((?:a|an|the)\s+.+)$", re.IGNORECASE),
    re.compile(r"^(.+?)\s+(?:refers to|is defined as|means)\s+(.+)$", re.IGNORECASE),
)
_QUESTION_STARTERS = (
    "what",
    "who",
    "where",
    "when",
    "why",
    "how",
    "which",
    "define",
    "explain",
    "describe",
    "list",
)
_ABBREVIATIONS = ("e.g.", "i.e.", "Dr.", "Mr.", "Mrs.", "Ms.", "vs.")


def clean_text(text: str) -> str:
    """Normalize whitespace while preserving paragraph and line boundaries."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [re.sub(r"[\t ]+", " ", line).strip() for line in text.split("\n")]
    normalized = "\n".join(lines)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    normalized = re.sub(r"[\t ]+([,.;!?])", r"\1", normalized)
    return normalized.strip()


def split_sentences(text: str) -> list[str]:
    """Split prose without requiring a runtime tokenizer download."""
    protected = text.replace("\n", " ")
    for abbreviation in _ABBREVIATIONS:
        protected = protected.replace(abbreviation, abbreviation.replace(".", "<DOT>"))
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", protected)
    return [part.replace("<DOT>", ".").strip() for part in parts if len(part.strip()) > 3]


def _is_label(line: str) -> re.Match[str] | None:
    match = _LABEL_RE.match(line)
    if not match:
        return None
    label = match.group(1).strip()
    if "//" in line or re.fullmatch(r"\d{1,2}", label) or len(label.split()) > 8:
        return None
    return match


def parse_blocks(text: str) -> list[dict[str, str]]:
    """Group labelled notes and ordinary paragraphs without mixing their text."""
    lines = clean_text(text).split("\n")
    blocks: list[dict[str, str]] = []
    paragraph: list[str] = []
    current_label: str | None = None
    current_content: list[str] = []

    def flush_paragraph() -> None:
        if paragraph:
            blocks.append({"type": "paragraph", "content": " ".join(paragraph).strip()})
            paragraph.clear()

    def flush_label() -> None:
        nonlocal current_label
        if current_label is not None:
            blocks.append(
                {
                    "type": "labeled",
                    "label": current_label,
                    "content": " ".join(current_content).strip(),
                }
            )
            current_label = None
            current_content.clear()

    for line in lines + [""]:
        if not line:
            flush_label()
            flush_paragraph()
            continue
        match = _is_label(line)
        if match:
            flush_label()
            flush_paragraph()
            current_label = match.group(1).strip()
            inline_content = match.group(2).strip()
            if inline_content:
                current_content.append(inline_content)
        elif current_label is not None:
            current_content.append(line)
        else:
            paragraph.append(line)

    return blocks


def _is_question(sentence: str) -> bool:
    stripped = sentence.strip()
    first_word = stripped.lower().split(maxsplit=1)[0] if stripped else ""
    return stripped.endswith("?") or first_word in _QUESTION_STARTERS


def _definition_card(sentence: str) -> Flashcard | None:
    candidate = sentence.strip().rstrip(".")
    for pattern in _DEFINITION_PATTERNS:
        match = pattern.fullmatch(candidate)
        if match:
            subject, definition = (part.strip() for part in match.groups())
            if 1 <= len(subject.split()) <= 12 and definition:
                if subject.lower() in {"it", "this", "that", "these", "they", "there"}:
                    return None
                return Flashcard(front=f"Define {subject}.", back=definition, source=sentence)
    return None


def _cloze_card(sentence: str) -> Flashcard | None:
    """Create a source-grounded cloze card from a factual sentence."""
    sentence = sentence.strip()
    if len(sentence.split()) < 5:
        return None

    # Do not blank an arbitrary long word. Only a numeric quantity with an
    # explicit, recognized unit is conservative enough for rule-based cloze.
    quantity = re.search(
        r"(?<![\w.])[-+]?\d+(?:\.\d+)?\s*"
        r"(?:degrees(?:\s+[CF]| Celsius| Fahrenheit)?|°[CF]|%|m/s(?:²|2)?|"
        r"kg|mg|km|cm|mm|Hz|kHz|MHz|GHz|ms|seconds|minutes|hours|m|s|N|V|A|W|J|K)"
        r"(?!\w)",
        sentence,
    )
    if not quantity:
        return None
    answer = quantity.group(0)
    front = sentence[: quantity.start()] + "_____" + sentence[quantity.end() :]
    return Flashcard(front=f"Complete: {front}", back=answer, card_type="cloze", source=sentence)


def deduplicate(cards: Iterable[Flashcard]) -> list[Flashcard]:
    seen: set[tuple[str, str]] = set()
    unique: list[Flashcard] = []
    for card in cards:
        key = (
            re.sub(r"\s+", " ", card.front).casefold(),
            re.sub(r"\s+", " ", card.back).casefold(),
        )
        if key not in seen and card.front.strip() and card.back.strip():
            seen.add(key)
            unique.append(card)
    return unique


def generate_local(notes: str, max_cards: int = 20) -> list[Flashcard]:
    """Generate up to ``max_cards`` deterministic cards from ``notes``."""
    if not notes or not notes.strip():
        return []
    max_cards = max(1, min(int(max_cards), 500))
    cards: list[Flashcard] = []

    for block in parse_blocks(notes):
        if block["type"] == "labeled":
            if 2 <= len(block["content"].split()) <= 60:
                cards.append(
                    Flashcard(
                        front=f"What is {block['label']}?",
                        back=block["content"],
                        source=f"{block['label']}: {block['content']}",
                    )
                )
            continue

        sentences = split_sentences(block["content"])
        index = 0
        while index < len(sentences):
            sentence = sentences[index]
            has_following_answer = (
                _is_question(sentence)
                and index + 1 < len(sentences)
                and not _is_question(sentences[index + 1])
            )
            if has_following_answer:
                cards.append(
                    Flashcard(
                        front=sentence,
                        back=sentences[index + 1].rstrip("."),
                        source=sentence + " " + sentences[index + 1],
                    )
                )
                index += 2
                continue
            if not _is_question(sentence):
                card = _definition_card(sentence) or _cloze_card(sentence)
                if card:
                    cards.append(card)
            index += 1

    return deduplicate(cards)[:max_cards]
