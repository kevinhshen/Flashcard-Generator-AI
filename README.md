# Recall — AI Flashcard Generator

Recall turns class notes into editable flashcards and exports them as a CSV that can be imported into Anki,
Quizlet, or a spreadsheet. Gemini AI is selected by default and builds a source fact inventory, checks for
omissions, drafts questions, and reviews their answers. Offline pattern matching is available separately.

The app runs on your computer. Starting it opens the interface automatically in your default browser.

## Features

- Paste notes or import UTF-8 text, Markdown, or a text-based PDF (up to 10 MB / 200 pages).
- Generate cards locally with no account, API key, or internet connection.
- AI generation includes separate fact extraction, omission audit, drafting, review, and coverage repair.
- See progress, cancel long jobs, and reconnect after a page refresh.
- Edit, add, delete, and preview cards before export.
- Export UTF-8 CSV with `Front`, `Back`, and `Type` columns.
- Explicit Local rules / Gemini modes; AI errors never silently switch generators.
- Independent review scrolling, focused top-insert for new cards, and source excerpts.
- Leave the card limit blank for automatic source coverage (up to 1,000 AI cards), or set a cap of 1–500.
- Inspect a coverage report listing unresolved facts, unverifiable evidence, and excluded material.
- Preserve unfinished notes in browser local storage.
- Validate and deduplicate generated cards.
- Run automated tests and lint checks in GitHub Actions.

## Quick start

### 1. Install Python

Install Python 3.10 or newer. Verify the installation:

```bash
python --version
```

On Windows, use `py` instead of `python` in the commands below if that is how Python is installed.

### 2. Create and activate a virtual environment

Windows PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

macOS or Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install the application

```bash
python -m pip install --upgrade pip
python -m pip install -e .
```

### 4. Start Recall

```bash
python run.py
```

Your browser should open to `http://127.0.0.1:5000`. If it does not, open that address manually. Stop the server
with `Ctrl+C` in the terminal.

The original launcher still works for compatibility:

```bash
python FlashcardGenerator.py
```

## Gemini setup (default generator)

The default **Gemini · reviewed AI** generator requires a key. To configure it:

1. Create an API key in [Google AI Studio](https://aistudio.google.com/app/apikey).
2. Copy `.env.example` to a new file named `.env`.
3. Put the key after `GEMINI_API_KEY=` in `.env`.
4. Restart the app.

Example `.env`:

```dotenv
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=gemini-2.5-flash
HOST=127.0.0.1
PORT=5000
```

Never commit `.env`. It is ignored by Git. The key stays on the Python server and is not sent to browser
JavaScript. AI mode sends the pasted notes to the Gemini API; local mode does not.

For offline use without a key, explicitly select **Local rules**. That mode is deterministic pattern matching,
not a locally deployed language model. No Hugging Face model is bundled. The app running on localhost does not
make Gemini local: its inference happens on Google's servers.

Generation makes multiple model calls and may consume paid quota. Roughly two calls read/audit each source
section and two draft/review each batch of up to 12 facts, plus one repair call per batch with missing coverage.
Transient server errors may retry once. Long notes can take several minutes; progress shows the current step.

## Using the app

1. Paste notes or choose **Import file**.
2. Leave **Card limit** blank to cover the source, or set a deliberate cap.
3. Keep Gemini selected for AI review, or explicitly choose Local rules for offline pattern matching.
4. Choose **Generate** or press `Ctrl/⌘ + Enter`. Follow progress; use **Cancel** to stop between model calls.
5. Inspect the coverage report and source excerpts, then correct or refine cards in the review panel.
6. Use the preview to check whether each question is answerable without seeing the back.
7. Choose **Export CSV**. `Ctrl/⌘ + S` also exports while a deck exists.

Headings formatted as `Term: explanation` produce reliable definition cards in local mode. Complete sentences and
explicit question/answer pairs also work well.

## CSV import

The exported file contains a header row:

```csv
Front,Back,Type
```

When importing into Anki, map `Front` to the front field and `Back` to the back field. The `Type` column records
whether Recall produced a `basic` or `cloze` card; it can be ignored if your target app does not use it.

## How generation works

### Local mode

The local generator groups labelled sections and paragraphs, pairs questions with following answers, recognizes
common definition patterns, and makes cloze cards only for recognized numerical quantities with units.
It skips uncertain prose instead of blanking arbitrary words. It does not call
an external service, and every answer is copied from the notes.

### Gemini mode

1. Partition the entire source into sections of at most 6,000 characters without dropping any characters.
   Adjacent context helps resolve headings; evidence must occur in the section being processed.
2. Extract independently testable facts with exact source excerpts. A separate audit checks for missed
   definitions, formulas, units, conditions, exceptions, comparisons, processes, and worked examples.
3. Draft focused question/answer cards in batches of at most 12 facts. Each card identifies the facts it tests.
4. Review every batch for unsupported claims, logical errors, answer leakage, vague subjects, missing qualifiers,
   and questions whose answers do not match. Request a targeted repair for uncovered facts.
5. Validate source excerpts and fact IDs, reject empty/tautological cards, merge exact duplicates, and reject
   conflicting answers to identical questions. Apply any card limit only after processing all source sections.
6. Report covered and uncovered objectives, unverifiable excerpts, and reasons for exclusions.

Coverage means **AI-identified facts represented by accepted cards**, not proof that all important source
information was found or correctly understood. Source matching verifies an excerpt's presence, not logical
entailment. The same model performs extraction and review, so correlated errors are possible. Compare the cards
with your notes. Coverage becomes marked stale after you edit, add, or delete cards.

The default model remains configurable through `GEMINI_MODEL`. No live model-quality benchmark is claimed:
automated tests use scripted model responses to verify pipeline behavior, not real-model factual accuracy.

The UI polls a background job rather than holding a connection open for the entire generation. A provider
request has a 90-second timeout and up to one retry for transient server errors. Cancellation takes effect
after the in-flight call/retry returns. API failures are classified (key, quota, model, timeout, invalid output)
and never silently switch to local generation. Old cards remain visible after errors/empty results, with a
notice that they may belong to earlier notes. Completed jobs are retained in server memory for up to 30 minutes
(at most ten completed jobs); restarting the server loses them. Export decks you want to keep.

### PDF import

PDF text is extracted locally with pypdf and placed in the editable notes field before generation.
Image-only/scanned PDFs require OCR and are not supported yet. Mixed PDFs show a warning for pages without
extractable text. Diagrams, handwriting, mathematical layout, and reading order are not reliably recovered.
Password-protected, malformed, oversized, and empty files show errors without replacing your notes.

See [docs/architecture.md](docs/architecture.md) for the data flow and failure behavior.

## Project structure

```text
.
├── run.py                         # Recommended launcher
├── FlashcardGenerator.py          # Backward-compatible launcher
├── src/flashcard_generator/
│   ├── generator.py               # Offline parsing and card generation
│   ├── ai.py                      # Fact inventory, review, and coverage pipeline
│   ├── jobs.py                    # Background progress and cancellation
│   ├── importers.py               # Local text/Markdown/PDF extraction
│   ├── web.py                     # Flask routes and browser launcher
│   ├── templates/index.html       # Accessible interface markup
│   └── static/                    # UI styles and interactions
├── tests/                         # Generator and API tests
├── examples/                      # Sample source notes
├── docs/architecture.md           # Design notes and data flow
├── pyproject.toml                 # Package, tool, and dependency config
└── .github/workflows/ci.yml       # Continuous integration
```

## Development

Install development tools:

```bash
python -m pip install -e ".[dev]"
```

Run the checks used in CI:

```bash
ruff check .
pytest --cov=flashcard_generator --cov-report=term-missing
```

Frontend regression tests (Node.js 20+ is needed only for development):

```bash
npm ci
npm test
```

These exercise DOM state, AI defaults, coverage, add-card focus, storage failures, repeated submissions,
and error recovery. Python regressions cover omission repair, later source sections, conflicting answers,
source provenance, limits, and job cancellation. They do not replace live-model or pixel-level browser QA.

The web API can also be tested directly:

```bash
curl -X POST http://127.0.0.1:5000/api/generate \
  -H "Content-Type: application/json" \
  -d '{"notes":"Velocity: The rate of change of displacement.","max_cards":10,"use_ai":false}'
```

For asynchronous AI generation, `POST /api/jobs` accepts the same JSON (`use_ai` defaults to `true`,
`max_cards` defaults to `null`) and returns `202` with `job_id`. Poll `GET /api/jobs/<job_id>` for
`queued`, `running`, `completed`, `failed`, or `cancelled`. Completed responses contain `result.cards`
and `result.coverage`. To cancel, `POST /api/jobs/<job_id>/cancel`. The single-user server permits one
background generation at a time; concurrent submissions return `409`.

## Troubleshooting

**The browser did not open:**
Open `http://127.0.0.1:5000` manually and confirm the terminal says Flask is running.

**`ModuleNotFoundError: flashcard_generator`:**
Activate the virtual environment and rerun `python -m pip install -e .` from the repository root.

**Gemini says it is not configured:**
Confirm the file is named exactly `.env`, the key is assigned to `GEMINI_API_KEY`, and the app was restarted.

**Gemini fails:**
The error now distinguishes authentication/permission, quota/rate limits, unavailable model, timeouts, and
malformed model output. Check the relevant key, AI Studio usage, or `GEMINI_MODEL` setting. For timeouts or
truncated output, retry with smaller source sections. A failed run does not generate replacement local cards.

**Generation is taking longer than before:**
Separate extraction and review calls trade speed and quota for additional checks. Follow progress or cancel;
refreshing reconnects to the same session in that tab rather than starting another paid generation.

**The report shows missing facts:**
Remove a manually set card cap, inspect the listed source excerpts, correct broken PDF extraction, or generate
from a smaller relevant section. Do not interpret a partial deck as complete coverage.

**Port 5000 is already in use:**
Set another port in `.env`, for example `PORT=5050`, then restart.

**PowerShell blocks virtual-environment activation:**
Run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`, then activate `.venv` again. This changes policy
for the current PowerShell process only.

## Current limitations

- Local mode uses linguistic heuristics and is less selective than AI mode.
- Text-based PDF import is supported; scanned PDF/image OCR is not included.
- Gemini requires an API key, internet access, and available quota.
- Automatic AI decks have a safety ceiling of 1,000 cards; more than 2,000 detected objectives requires splitting
  the source. Manual caps can reduce coverage and are reported explicitly. Local auto mode caps at 500 cards.
- The app is intended for local use and has no user accounts or shared cloud decks.
- Generated cards should be reviewed before relying on them for high-stakes material.
