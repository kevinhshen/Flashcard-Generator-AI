"""Validation and deduplication for cards from any generator backend."""

from __future__ import annotations

from dataclasses import replace

from .models import Flashcard


def _normalize(value: str) -> str:
    return " ".join(value.split())


def validate_and_deduplicate(cards: list[Flashcard]) -> tuple[list[Flashcard], list[tuple[Flashcard, str]]]:
    accepted: list[Flashcard] = []
    rejected: list[tuple[Flashcard, str]] = []
    seen: set[tuple[str, str]] = set()

    for card in cards:
        normalized = replace(card, front=_normalize(card.front), back=_normalize(card.back))
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
