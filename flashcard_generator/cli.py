"""Command-line interface for the rules-only flashcard generator."""

from __future__ import annotations

import argparse
from pathlib import Path

from .exporter import export_anki_tsv
from .parser import segment_chunks
from .rules import generate_rule_cards
from .validation import validate_and_deduplicate


def _read_pasted_notes() -> str:
    print("Paste your notes. Type END on its own line when you are finished.")
    lines: list[str] = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if line == "END":
            break
        lines.append(line)
    return "\n".join(lines)


def _build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create local flashcards from notes.")
    parser.add_argument("--input", type=Path, help="UTF-8 text file containing notes")
    parser.add_argument("--output", type=Path, default=Path("flashcards.tsv"), help="Anki TSV output path")
    parser.add_argument("--no-export", action="store_true", help="Preview cards without writing a file")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_argument_parser()
    args = parser.parse_args(argv)

    if args.input:
        try:
            notes = args.input.read_text(encoding="utf-8")
        except OSError as error:
            parser.error(f"could not read {args.input}: {error}")
    else:
        notes = _read_pasted_notes()

    cards, rejected = validate_and_deduplicate(generate_rule_cards(segment_chunks(notes)))
    if not cards:
        print("No valid flashcards were found. Try notes with definitions, facts, or Q/A pairs.")
        return 1

    for number, card in enumerate(cards, start=1):
        print(f"\n{number}. Q: {card.front}\n   A: {card.back}")

    if rejected:
        print(f"\nSkipped {len(rejected)} invalid or duplicate card(s).")
    if args.no_export:
        return 0

    output_path = export_anki_tsv(cards, args.output)
    print(f"\nExported {len(cards)} card(s) to {output_path}.")
    return 0
