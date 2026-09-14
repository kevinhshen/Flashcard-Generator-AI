# Decisions

## Rules first

The application keeps a deterministic rules-only mode. It provides a reliable baseline and lets us measure whether a future model actually improves output.

The rules skip vague existence statements, prefer leading named concepts in cloze cards, and invert clear group-identity statements into direct retrieval questions.

## Source provenance

Each flashcard stores its source chunk and generator name. This makes review possible and will help reject unsupported model output later.

## Offline-safe imports

NLTK is optional. The program never downloads tokenizer data automatically and falls back to a standard-library splitter when NLTK or its data is unavailable.

## TSV export

The exporter writes UTF-8 tab-separated front/back fields without a header because that imports cleanly into Anki.
