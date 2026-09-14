# Architecture

## Package boundaries

- `models.py`: immutable `SourceChunk` and `Flashcard` data models
- `parser.py`: text cleanup, chunk segmentation, and sentence splitting
- `rules.py`: deterministic labelled, definition, Q/A, and cloze generation
- `validation.py`: card normalization and duplicate rejection
- `exporter.py`: Anki-compatible TSV export
- `cli.py`: command-line input, preview, and output coordination

`FlashcardGenerator.py` remains a small entry point so existing run commands keep working.

## Invariants

- Every card retains its original `source_text` and `source_id`.
- Parsing one source chunk cannot create cards from another chunk.
- Structural headings are kept out of card source content.
- No module downloads data or loads an AI model during import.
- Export receives only validated cards.

## Planned local-model boundary

Add a `flan_t5.py` backend later with a `generate(chunk) -> Flashcard | None` interface. It should load lazily, use bounded chunks, return a strict Q/A or `SKIP` format, and send every result through `validation.py` before export.
