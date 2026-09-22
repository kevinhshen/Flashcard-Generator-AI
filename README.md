# Recall — local AI flashcard generator

Recall turns notes into editable flashcards and exports CSV for Anki, Quizlet, or a spreadsheet. Its default
AI pipeline runs locally through Ollama: it inventories source facts, audits omissions, drafts cards, reviews
them, and reports unresolved coverage. No API key or cloud model is required.

## What it does

- Imports pasted text, UTF-8 text, Markdown, and text-based PDFs up to 10 MB / 200 pages.
- Runs reviewed AI generation locally through Ollama, with `qwen3:8b` as the default model.
- Provides a separate deterministic rules mode that never invokes a language model.
- Grounds cards in source excerpts and rejects unknown fact IDs, tautologies, and conflicting answers.
- Reports identified, covered, unresolved, rejected, and excluded material.
- Runs generation in a background job with progress, cancellation, refresh reconnection, and duplicate-job
  protection.
- Lets you edit, add, remove, preview, and export cards.
- Keeps notes in browser local storage; the Python server does not write them to disk.

## Quick start

### 1. Install Ollama and a model

Install [Ollama for Windows](https://ollama.com/download/windows). Ollama runs in the background and serves its
local API at `http://127.0.0.1:11434`.

Pull the default model:

```powershell
ollama pull qwen3:8b
```

`qwen3:8b` is about 5.2 GB and is a sensible default for an 8 GB GPU. If memory or speed is a problem, use the
smaller model:

```powershell
ollama pull qwen3:4b
```

Then set `OLLAMA_MODEL=qwen3:4b` in `.env`.

### 2. Install Recall

Python 3.10 or newer is required.

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
```

If PowerShell blocks activation, run this once in the current terminal and activate again:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

### 3. Configure and start

The defaults work with a standard local Ollama installation. Copy `.env.example` to `.env` only if you want to
change the model, endpoint, timeout, port, or model keep-alive period.

```powershell
Copy-Item .env.example .env
python run.py
```

The app opens `http://127.0.0.1:5000`. The legacy `python FlashcardGenerator.py` launcher also works.

## Configuration

```dotenv
OLLAMA_URL=http://127.0.0.1:11434
OLLAMA_MODEL=qwen3:8b
OLLAMA_TIMEOUT=300
OLLAMA_KEEP_ALIVE=10m
HOST=127.0.0.1
PORT=5000
```

Recall sends prompts only to `OLLAMA_URL`. With the default loopback address, notes stay on this computer. If
you deliberately point `OLLAMA_URL` at another machine, your notes are transmitted to that server.

## Using the app

1. Paste notes or import a supported file.
2. Leave the card limit blank to cover the source, or choose a cap from 1–500.
3. Keep **Ollama · local reviewed AI** selected, or choose **Local rules** for fast deterministic parsing.
4. Generate, follow progress, and inspect both the cards and coverage report.
5. Correct cards as needed and export CSV.

The CSV has `Front`, `Back`, and `Type` columns. Map `Front` and `Back` to the corresponding Anki fields.

## How AI generation works

1. Losslessly split the source into sections of at most 6,000 characters.
2. Inventory independently testable facts, then run a separate omission audit.
3. Draft cards in batches of at most 12 facts.
4. Review each batch for unsupported claims, answer leakage, vague subjects, and missing qualifiers.
5. Run one bounded repair pass for uncovered fact IDs.
6. Validate provenance, merge exact duplicates, remove conflicting answers, then apply the optional card cap.

Ollama's structured-output API receives a Pydantic JSON schema for every pass. Recall validates the returned
JSON again before using it. Source matching confirms that an evidence excerpt exists in the notes; it does not
prove the model interpreted that excerpt correctly. Review generated cards before relying on them.

The pipeline makes at least four local model calls for one source section and may make more for extra sections,
batches, or repairs. A small model is faster but may miss facts or produce weaker cards. A larger model can be
more accurate but needs more VRAM/RAM and time.

## Local rules mode

Rules mode recognizes labelled sections, explicit question/answer pairs, common definition patterns, and
numerical quantities with units. It is fast and deterministic, but it does not perform the AI coverage audit.
Every rules-mode answer is copied from the source.

## Development

```powershell
python -m pip install -e ".[dev]"
ruff check .
pytest --cov=flashcard_generator --cov-report=term-missing
npm ci
npm test
```

Automated tests use scripted model responses and a fake Ollama transport. They validate orchestration, failure
handling, grounding, and the UI; they do not claim live-model factual quality.

Project layout:

```text
src/flashcard_generator/
├── ai.py             # Ollama transport and coverage-first AI pipeline
├── generator.py      # Deterministic rules generator
├── importers.py      # TXT, Markdown, and PDF extraction
├── jobs.py           # Background progress and cancellation
├── web.py            # Flask routes and launcher
├── templates/        # Interface markup
└── static/           # Interface CSS and JavaScript
```

## API

`POST /api/generate` accepts:

```json
{"notes": "Velocity: rate of change of displacement.", "max_cards": null, "use_ai": true}
```

For AI generation, prefer `POST /api/jobs`, then poll `GET /api/jobs/<job_id>`. Cancel with
`POST /api/jobs/<job_id>/cancel`. `GET /api/status` reports whether Ollama is reachable and whether the
configured model is installed without sending any notes.

## Troubleshooting

**Could not reach Ollama:** Start the Ollama desktop app. Check `http://127.0.0.1:11434/api/tags` and confirm
`OLLAMA_URL` if you changed it.

**Model is not installed:** Run `ollama pull qwen3:8b`, or pull another model and set `OLLAMA_MODEL` to its exact
name.

**Generation is slow or times out:** Keep Ollama running, try a smaller source, increase `OLLAMA_TIMEOUT`, or
switch to `qwen3:4b`. The first request also loads the model into memory.

**Ollama returns invalid structured output:** Update Ollama and retry. If the problem persists, use a stronger
instruction-following model.

**Port 5000 is occupied:** Set `PORT=5050` in `.env` and restart Recall.

**PDF content is missing:** Scanned pages, images, diagrams, handwriting, and complex mathematical layout need
OCR and are not supported. Review the extracted text before generating.

## Limits

- AI coverage counts only model-identified facts; two model passes can still miss the same material.
- A manual card cap can intentionally leave objectives uncovered.
- Jobs live in one Python process and disappear when the server restarts.
- Cancellation takes effect after the current Ollama request returns.
- The app is intended for one local user and has no accounts or shared decks.
