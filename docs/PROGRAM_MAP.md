# Program Map

## Flow

`notes -> parser -> rule generator -> validation/deduplication -> preview -> Anki TSV`

1. `cli.py` reads a text file or pasted notes.
2. `parser.py` normalizes whitespace and creates source-preserving chunks.
3. `rules.py` creates deterministic candidate cards for each chunk.
4. `validation.py` normalizes, rejects invalid cards, and removes duplicates.
5. `exporter.py` writes accepted front/back pairs to TSV.

The future FLAN-T5 backend belongs between parsing and validation. It must return cards with the same source metadata as rule-generated cards.
