"""Export accepted cards in a format Anki can import directly."""

from __future__ import annotations

import csv
from pathlib import Path

from .models import Flashcard


def export_anki_tsv(cards: list[Flashcard], output_path: Path) -> Path:
    """Write UTF-8 tab-separated front/back fields without a header row."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as output_file:
        writer = csv.writer(output_file, delimiter="\t", lineterminator="\n")
        writer.writerows((card.front, card.back) for card in cards)
    return output_path
