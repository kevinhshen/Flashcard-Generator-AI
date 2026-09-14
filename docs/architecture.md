# Architecture

## Package boundaries

- `models.py`: immutable `SourceChunk` and `Flashcard` data models
- `parser.py`: text cleanup, chunk segmentation, and sentence splitting
- `rules.py`: deterministic labelled, definition, Q/A, and cloze candidates with confidence levels
- `generation.py`: selects the rules, hybrid, or FLAN pipeline without importing AI dependencies
- `flan_t5.py`: lazy local FLAN-T5 Base backend, input chunking, strict response parsing, and source checks
- `validation.py`: card normalization, grounding checks for model cards, and duplicate rejection
- `exporter.py`: Anki-compatible TSV export
- `cli.py`: command-line input, preview, and output coordination

`FlashcardGenerator.py` remains a small entry point so existing run commands keep working.

## Invariants

- Every card retains its original `source_text` and `source_id`.
- Parsing one source chunk cannot create cards from another chunk.
- Structural headings are kept out of card source content.
- No module downloads data or loads an AI model during import.
- Export receives only validated cards.

## Local-model boundary

`FlanT5Generator` loads PyTorch and Transformers only after the user selects `--engine hybrid` or `--engine flan`. It processes one source sentence or bounded source part at a time, never a whole document. It asks the model for either exactly one `Q:`/`A:` pair or `SKIP`.

`hybrid` exports high-confidence rules (labels, clear definitions, explicit Q/A pairs, group identities), replaces uncertain clozes plus unresolved sentences with model attempts, and gives only clearly fragmentary rule answers an optional quality pass. That pass can return `KEEP`, leaving the original untouched. `flan` evaluates every independent source chunk and is useful for comparisons, not normal production use.

Malformed model output, empty cards, duplicates, oversize cards, and model answers that introduce a number or all-caps acronym absent from the source are rejected before export. `--review` shows only AI-created or AI-improved cards, with edit, discard, and source-based regeneration actions; `--review-all` includes deterministic cards. These are guardrails, not factual proof.
