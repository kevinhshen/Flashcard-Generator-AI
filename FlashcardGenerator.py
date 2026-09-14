"""Backward-compatible entry point for the flashcard generator."""

from flashcard_generator.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
