"""Validation and deduplication for cards from any generator backend."""

from __future__ import annotations

from dataclasses import replace
import re

from .models import Flashcard


def _normalize(value: str) -> str:
    return " ".join(value.split())


def validate_model_grounding(card: Flashcard) -> str | None:
    """Reject model answers that introduce exact numbers or acronyms not in source."""
    source = card.source_text.casefold()
    markers = re.findall(r"\b(?:[A-Z]{2,}|\d[\d,./%:-]*)\b", card.back)
    for marker in markers:
        if marker.casefold() not in source:
            return f"model answer introduces '{marker}', which is absent from the source"
    return None


def validate_and_deduplicate(cards: list[Flashcard]) -> tuple[list[Flashcard], list[tuple[Flashcard, str]]]:
    accepted: list[Flashcard] = []
    rejected: list[tuple[Flashcard, str]] = []
    seen: set[tuple[str, str]] = set()

    for card in cards:
        normalized = replace(card, front=_normalize(card.front), back=_normalize(card.back))
        if normalized.generator == "flan":
            grounding_error = validate_model_grounding(normalized)
            if grounding_error:
                rejected.append((card, grounding_error))
                continue
        if len(normalized.front) < 3 or len(normalized.back) < 1:
            rejected.append((card, "front or back is empty"))
            continue
        if len(normalized.front) > 250 or len(normalized.back) > 2_000:
            rejected.append((card, "card is too long"))
            continue
        key = (normalized.front.casefold(), normalized.back.casefold())
        if key in seen:
            rejected.append((card, "duplicate card"))
            continue
        seen.add(key)
        accepted.append(normalized)

    return accepted, rejected
