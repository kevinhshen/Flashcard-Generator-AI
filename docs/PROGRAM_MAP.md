# Program Map

## Flow

`notes -> parser -> selected generator -> validation/deduplication -> optional review -> Anki TSV`

1. `cli.py` reads a text file or pasted notes.
2. `parser.py` normalizes whitespace and creates source-preserving chunks.
3. `generation.py` selects one engine:
   - `rules`: exports deterministic high- and low-confidence rule cards.
   - `hybrid`: exports high-confidence rule cards and sends only uncertain/unresolved facts to FLAN-T5.
   - `flan`: sends every independent fact to FLAN-T5 for evaluation.
4. `flan_t5.py`, when selected, loads locally and returns only strict, source-linked Q/A pairs or safe skips.
5. `validation.py` normalizes, rejects invalid/unsupported cards, and removes duplicates.
6. In hybrid mode, `generation.py` sends clearly fragmentary rule cards to FLAN for an optional guarded rewrite. FLAN may return `KEEP`; the original card stays unchanged.
7. `cli.py --review` lets the user inspect only AI-created/improved cards, keep, edit, regenerate from source, or discard them. `--review-all` shows every card.
8. `exporter.py` writes accepted front/back pairs to TSV.

Every card preserves its source text and source ID through the whole flow.
