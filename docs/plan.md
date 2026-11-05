# Plan

## Status
- [x] Local rules generator
- [x] Gemini multi-stage pipeline (inventory, audit, draft, review, repair)
- [x] Token usage display
- [x] Model selection in web app
- [ ] Metrics: record, measure and visualise time, tokens, cost, accuracy

## Next: research metrics (4 steps)
1. **Save every run** (`storage.py`, SQLite)
   - Tables: `runs` (one row per generation), `cards` (one row per card)
   - `runs`: timestamp, model, mode, total tokens, coverage, duration, notes hash (never the note text)
   - Call from `perform()` in `web.py`; a storage error must never break generation
2. **Record more per call** (`ai.py`)
   - Keep input tokens, output tokens and seconds per call (today: total tokens only)
   - Store in a third table, `stage_usage`
3. **Excel export**
   - New route builds an `.xlsx` (one sheet per table) with `openpyxl`
   - Button on the Export page
4. **Graph script** (`analysis/make_figures.py`)
   - Reads the database, saves PNG charts
   - Start with: tokens per stage by model, coverage vs. tokens

Guard-rails: never change old rows, add `data/` and `figures/` to `.gitignore`, record the git commit with each run, add tests (insert and read back a run; export opens).

## To learn
| Topic | Why | Java comparison |
|---|---|---|
| `sqlite3` | Create tables, insert, query | JDBC, built in |
| SQL `INSERT` / `SELECT` / `GROUP BY` | Save runs, average per model | Same SQL |
| `openpyxl` | Write Excel from Python | Apache POI |
| `pandas` DataFrame | Load a table, compute averages | List of records with `groupBy` |
| `matplotlib` | Bar and scatter plots | JFreeChart |
| `hashlib.sha256` | Detect identical inputs | `MessageDigest` |

## Ideas (not committed)
- **Track every source passage:** each quote or sentence of the notes ends as a card or an exclusion with a recorded reason. Passages can be partly used, so track quotes or sentences, not whole chunks.
- Auto-search YouTube videos for related topics (Gemini is already used).

## Reference: local rules pipeline
1. Accept bulk input, clean up the text
2. Pass it to `extract_flashcard`
   - Labeled block: make a definition card directly
   - Paragraph block: split into sentences, then classify each:
     - question + next sentence: question/answer card
     - definition sentence: definition card
     - fact sentence: cloze card or skip
