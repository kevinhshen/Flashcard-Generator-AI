# Recall — AI Flashcard Generator

Recall turns class notes into editable flashcards and exports them as a CSV that can be imported into Anki,
Quizlet, or a spreadsheet. It includes a private, deterministic local mode and an optional Gemini mode for more
selective question writing.

The app runs on your computer. Starting it opens the interface automatically in your default browser.

## Features

- Paste notes or import a `.txt`/`.md` file.
- Generate cards locally with no account, API key, or internet connection.
- Optionally use Gemini structured output for stronger, more atomic questions.
- Edit, add, delete, and preview cards before export.
- Export UTF-8 CSV with `Front`, `Back`, and `Type` columns.
- Fall back to local generation if the Gemini request fails.
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

## Optional Gemini setup

Local mode works immediately. To enable **Improve with Gemini**:

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

## Using the app

1. Paste notes or choose **Import file**.
2. Select a maximum number of cards.
3. Leave Gemini off for private, instant local generation, or enable it for higher-quality question selection.
4. Choose **Generate flashcards** or press `Ctrl/⌘ + Enter`.
5. Correct or refine any card in the review panel.
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
common definition patterns, and makes source-grounded cloze cards from other factual sentences. It does not call
an external service, and every answer is copied from the notes.

### Gemini mode

The Gemini prompt requests atomic active-recall questions and forbids outside facts. A Pydantic schema constrains
the response to flashcard objects. The app then validates fields, normalizes card types, removes duplicates, and
enforces the requested limit. Structured output improves formatting reliability, but AI-generated cards should
still be reviewed for factual accuracy.

See [docs/architecture.md](docs/architecture.md) for the data flow and failure behavior.

## Project structure

```text
.
├── run.py                         # Recommended launcher
├── FlashcardGenerator.py          # Backward-compatible launcher
├── src/flashcard_generator/
│   ├── generator.py               # Offline parsing and card generation
│   ├── ai.py                      # Gemini request and validation
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

The web API can also be tested directly:

```bash
curl -X POST http://127.0.0.1:5000/api/generate \
  -H "Content-Type: application/json" \
  -d '{"notes":"Velocity: The rate of change of displacement.","max_cards":10,"use_ai":false}'
```

## Troubleshooting

**The browser did not open:**
Open `http://127.0.0.1:5000` manually and confirm the terminal says Flask is running.

**`ModuleNotFoundError: flashcard_generator`:**
Activate the virtual environment and rerun `python -m pip install -e .` from the repository root.

**Gemini is disabled:**
Confirm the file is named exactly `.env`, the key is assigned to `GEMINI_API_KEY`, and the app was restarted.

**Port 5000 is already in use:**
Set another port in `.env`, for example `PORT=5050`, then restart.

**PowerShell blocks virtual-environment activation:**
Run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`, then activate `.venv` again. This changes policy
for the current PowerShell process only.

## Current limitations

- Local mode uses linguistic heuristics and is less selective than AI mode.
- Only text and Markdown files are imported; PDF and image OCR are not included.
- Gemini requires an API key, internet access, and available quota.
- The app is intended for local use and has no user accounts or shared cloud decks.
- Generated cards should be reviewed before relying on them for high-stakes material.
