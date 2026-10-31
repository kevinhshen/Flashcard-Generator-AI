# Recall

Paste in your class notes, get flashcards out. Edit them in the browser, then export a CSV you can import into
Anki, Quizlet, or a spreadsheet.

Recall runs on your own machine. There are two ways to generate cards:

- **Gemini (default):** an AI pipeline that pulls out the facts in your notes, drafts questions, and checks
  its own answers. It needs a Gemini API key and an internet connection.
- **Local rules:** simple pattern matching (definitions, `Term: explanation` lines, question/answer pairs).
  It works offline and needs no key, but it is much less selective.

## Run it

You need Python 3.10 or newer.

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .\.venv\Scripts\Activate.ps1
python -m pip install -e .
python run.py
```

The app opens at http://127.0.0.1:5000.

## Gemini key

Create a key in [Google AI Studio](https://aistudio.google.com/app/apikey) and paste it into the app's
**Gemini API key** field. It gets saved to a local `.env` file, which Git ignores. You can also copy
`.env.example` to `.env` and fill it in yourself. `GEMINI_MODEL`, `HOST`, and `PORT` can be changed there too.

Your notes are sent to Google when you use Gemini mode, and a long set of notes makes many model calls, so it
can take a few minutes and use quota. If Gemini fails, Recall shows the error. It never quietly falls back to
local rules.

## Using it

1. Paste notes or import a `.txt`, `.md`, or text-based PDF (up to 10 MB or 200 pages).
2. Leave the card limit empty to cover everything, or set a cap.
3. Generate (`Ctrl/⌘ + Enter`). You can watch progress or cancel.
4. Review the cards, fix or delete any, and check the coverage report for facts that didn't make it in.
5. Export CSV (`Ctrl/⌘ + S`). Columns are `Front`, `Back`, `Type`.

## How Gemini mode works

Notes are split into sections of up to 6,000 characters. For each section, Recall extracts testable facts with
the exact source excerpt, runs a separate pass to catch what was missed, drafts cards in batches, and has the
model review every batch. Cards with unsupported answers, duplicates, or conflicting answers get dropped. See
[docs/architecture.md](docs/architecture.md) for details.

"Coverage" here means facts the AI found that ended up on a card. It doesn't prove the AI found everything,
so skim the cards against your notes before you rely on them.

## Limitations

- Scanned or image-only PDFs aren't supported (no OCR).
- Automatic mode stops at 1,000 AI cards (500 in local mode). Split very large notes.
- Finished jobs are kept in memory for 30 minutes, so export decks you want to keep.
- It's a single-user local app. There are no accounts and nothing is shared.

## Development

```bash
python -m pip install -e ".[dev]"
ruff check .
pytest --cov=flashcard_generator
npm ci && npm test              # UI tests, needs Node 20+
```

The tests use scripted model responses, so they check the pipeline's behavior, not real-model accuracy.

## Troubleshooting

- **`ModuleNotFoundError: flashcard_generator`:** activate the virtual environment and rerun
  `python -m pip install -e .`.
- **Port 5000 is taken:** set `PORT=5050` in `.env` and restart.
- **PowerShell won't activate the venv:** run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`
  first (it only affects that window).
