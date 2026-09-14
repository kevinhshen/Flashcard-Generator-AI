# Decisions

## Rules first

The application keeps a deterministic rules-only mode. It provides a reliable baseline and lets us measure whether a future model actually improves output.

The rules skip vague existence statements, prefer leading named concepts in cloze cards, and invert clear group-identity statements into direct retrieval questions.

## Hybrid model policy

FLAN-T5 Base is optional and local. `hybrid` is the recommended engine because the rules are more reliable for structured notes, while the model handles only facts the rules cannot phrase safely. `flan` exists for evaluation.

The backend loads lazily, uses deterministic decoding, has a 384-token prompt budget, and asks for exactly one card or `SKIP`. Its quality prompt allows `KEEP`, so a clear rule card remains untouched. It does not silently truncate long notes: it splits them by sentence, then by words only when a sentence exceeds the budget.

## Source provenance and review

Each flashcard stores its source chunk and generator name. The model backend rejects malformed output and answers that introduce a number or all-caps acronym absent from source. The terminal review step shows only AI cards by default and allows edits, regeneration from source, or discards before export. `--review-all` includes deterministic cards.

## Offline-safe imports

NLTK is optional. The program never downloads tokenizer data automatically and falls back to a standard-library splitter when NLTK or its data is unavailable.

## TSV export

The exporter writes UTF-8 tab-separated front/back fields without a header because that imports cleanly into Anki.
