# Plan

## Done
- [x] Local rules generator
- [x] Gemini multi-stage pipeline (inventory, audit, draft, review, repair)
- [x] Token usage display and model selection
- [x] Save every run to SQLite (`runs`, `stage_usage`, `cards`, `facts`)
- [x] Excel and CSV export
- [x] History page placeholder (`/history`, nav link)

## Next: History view
1. `storage.list_past_runs()`: all runs, newest first (in progress)
2. `/history` route passes the runs to `history.html`; table with empty and error states
3. `storage.get_run_detail(run_id)`: the run plus its stage usage, cards and facts
4. `/history/<run_id>` route (404 if unknown) and `run_detail.html`: summary, stage usage, facts, cards
5. Tests: list order, detail page, unknown id, failed run with no cards

Notes: show missing values as "—" (old runs have empty columns); load cards and facts only on the detail page.

## Later
- Graph script (`analysis/make_figures.py`): tokens per stage by model, coverage vs. tokens

## Ideas (not committed)
- Track every source passage: each quote ends as a card or an exclusion with a reason
- Auto-search YouTube videos for related topics

## Reference: local rules pipeline
1. Clean up the text
2. Labeled block: definition card
3. Paragraph: split into sentences; question + next sentence gives a Q/A card, definition gives a definition card, fact gives a cloze card or is skipped
