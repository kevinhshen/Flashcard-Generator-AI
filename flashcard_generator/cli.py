"""Command-line interface for local rule-based and FLAN-T5 generation."""

from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path
from typing import Callable

from .exporter import export_anki_tsv
from .generation import run_generation
from .models import Flashcard
from .parser import segment_chunks
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
    parser.add_argument(
        "--engine",
        choices=("rules", "hybrid", "flan"),
        default="rules",
        help="rules is offline; hybrid uses FLAN only for uncertain facts; flan evaluates every fact",
    )
    parser.add_argument("--model-id", default="google/flan-t5-base", help="Hugging Face model ID for AI modes")
    parser.add_argument("--device", choices=("auto", "cpu", "cuda", "mps"), default="auto", help="Device for AI modes")
    parser.add_argument("--offline", action="store_true", help="Use only a previously downloaded model")
    parser.add_argument("--review", action="store_true", help="Review AI-generated or AI-improved cards before export")
    parser.add_argument("--review-all", action="store_true", help="Review every card before export")
    parser.add_argument(
        "--polish",
        choices=("off", "auto", "all"),
        default="auto",
        help="AI quality pass in hybrid mode: auto fixes fragments, all checks every rule card",
    )
    return parser


def _review_cards(
    cards: list[Flashcard],
    review_all: bool,
    regenerate: Callable[[Flashcard], tuple[Flashcard | None, str | None]] | None,
) -> list[Flashcard]:
    """Review only AI cards by default, with editing and source-based regeneration."""
    reviewed: list[Flashcard] = []
    for number, card in enumerate(cards, start=1):
        if not review_all and card.generator != "flan":
            reviewed.append(card)
            continue

        while True:
            print(
                f"\n{number}. Q: {card.front}\n   A: {card.back}\n"
                f"   Source: {card.source_text}\n"
                "   [Enter] keep  [e] edit  [r] regenerate  [d] discard  [q] keep remaining"
            )
            try:
                choice = input("   Choice: ").strip().lower()
            except EOFError:
                print("\nReview input ended; keeping the remaining cards unchanged.")
                reviewed.extend(cards[number - 1 :])
                return reviewed
            if choice == "q":
                reviewed.extend(cards[number - 1 :])
                return reviewed
            if choice == "d":
                break
            if choice == "r":
                if card.generator != "flan" or regenerate is None:
                    print("   Regeneration is available only for AI-generated or AI-improved cards.")
                    continue
                replacement, reason = regenerate(card)
                if replacement is None:
                    print(f"   Could not regenerate this card: {reason}")
                    continue
                card = replacement
                print("   Regenerated from the displayed source. Review the replacement below.")
                continue
            if choice == "e":
                try:
                    front = input("   New question (blank keeps current): ").strip()
                    back = input("   New answer (blank keeps current): ").strip()
                except EOFError:
                    print("\nReview input ended; keeping this card unchanged.")
                    reviewed.append(card)
                    reviewed.extend(cards[number:])
                    return reviewed
                card = replace(card, front=front or card.front, back=back or card.back)
            reviewed.append(card)
            break
    return reviewed


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

    chunks = segment_chunks(notes)
    model = None
    try:
        if args.engine == "rules":
            report = run_generation(chunks, "rules")
        else:
            from .flan_t5 import FlanT5Generator, FlanT5UnavailableError

            model = FlanT5Generator(
                model_id=args.model_id,
                device=args.device,
                offline=args.offline,
            )
            report = run_generation(chunks, args.engine, model, polish=args.polish)
    except FlanT5UnavailableError as error:
        parser.error(str(error))

    cards, rejected = validate_and_deduplicate(report.cards)
    if (args.review or args.review_all) and cards:
        regenerate = model.regenerate_card if model is not None else None
        cards, edited_rejections = validate_and_deduplicate(
            _review_cards(cards, review_all=args.review_all, regenerate=regenerate)
        )
        rejected.extend(edited_rejections)
    if not cards:
        print("No valid flashcards were found. Try notes with definitions, facts, or Q/A pairs.")
        return 1

    for number, card in enumerate(cards, start=1):
        print(f"\n{number}. Q: {card.front}\n   A: {card.back}")

    if rejected:
        print(f"\nSkipped {len(rejected)} invalid or duplicate card(s).")
    if report.skipped_sources:
        print(f"Skipped {len(report.skipped_sources)} source chunk(s) that the model could not safely turn into cards.")
    if args.no_export:
        return 0

    output_path = export_anki_tsv(cards, args.output)
    print(f"\nExported {len(cards)} card(s) to {output_path}.")
    return 0
