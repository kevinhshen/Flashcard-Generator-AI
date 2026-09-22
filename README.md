# Recall

Recall is a local-first web application that converts notes into editable flashcards. It combines deterministic
text parsing with a small Hugging Face T5 model, keeps generated answers grounded in the supplied notes, and
exports reviewed cards as CSV.

The application does not require an API key, Ollama, Docker, or a separate model server.

## What it does

- Accepts pasted notes and imports UTF-8 text, Markdown, and text-based PDFs.
- Runs `mrm8488/t5-base-finetuned-question-generation-ap` inside the Python process.
- Downloads and caches the model automatically on the first AI generation.
- Selects card answers from exact source excerpts before asking the model to write questions.
- Includes a deterministic rules mode that does not load a model.
- Reports source units that failed validation instead of silently hiding them.
- Supports background progress, cooperative cancellation, refresh reconnection, editing, study preview, and CSV
  export.

## Quick start

Python 3.10 or newer is required.

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
python run.py
```

Recall opens `http://127.0.0.1:5000`. The first AI run downloads roughly 900 MB of model files into the normal
Hugging Face cache. Later runs reuse the cached files and can start without internet access.

If PowerShell blocks virtual-environment activation:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

## Basic workflow

1. Paste notes or import a supported file.
2. Choose **T5 question model** or **Local rules**.
3. Leave the card limit blank for source-unit coverage, or set a limit from 1 to 500.
4. Generate the deck and inspect rejected units and source excerpts.
5. Edit the cards, use the study preview, and export CSV.

The exported columns are `Front`, `Back`, and `Type`.

## How the AI path stays grounded

Recall does not ask the model to invent complete cards. It first parses the notes into bounded source units and
selects a literal answer span using labels, explicit question/answer pairs, definitions, stated facts, and
quantities. The model receives that answer plus its source context and generates only a question.

The application then rejects malformed output, non-questions, vague questions, tautologies, and duplicates. A
source excerpt remains attached to every accepted card for human review.

This limits answer hallucination, but it does not prove that every generated question is pedagogically strong or
that every fact was identified. The coverage report measures validated source units, not complete semantic fact
coverage.

## Configuration

The defaults need no `.env` file. Copy `.env.example` to `.env` only when overriding them:

```dotenv
HF_MODEL_ID=mrm8488/t5-base-finetuned-question-generation-ap
HF_DEVICE=auto
HOST=127.0.0.1
PORT=5000
```

`HF_DEVICE=auto` prefers CUDA, then Apple MPS, then CPU. A replacement `HF_MODEL_ID` must support the T5
`answer: ... context: ...` question-generation format.

## Project map

| Path | Responsibility |
|---|---|
| `run.py` | Primary launcher |
| `FlashcardGenerator.py` | Compatibility launcher for earlier shortcuts |
| `src/flashcard_generator/web.py` | Flask application, validation, and HTTP routes |
| `src/flashcard_generator/ai.py` | Source units, answer selection, model lifecycle, and AI validation |
| `src/flashcard_generator/generator.py` | Deterministic rules generator and shared parsing helpers |
| `src/flashcard_generator/importers.py` | Bounded TXT, Markdown, and PDF extraction |
| `src/flashcard_generator/jobs.py` | In-memory background job lifecycle |
| `src/flashcard_generator/templates/` | HTML structure |
| `src/flashcard_generator/static/` | Browser behavior and styling |
| `tests/` | Python and browser regressions |

For implementation details, read [Architecture](docs/architecture.md). For a complete project walkthrough and
interview questions, read [Interview guide](docs/interview-guide.md).

## Development

```powershell
python -m pip install -e ".[dev]"
ruff format --check .
ruff check .
pytest --cov=flashcard_generator --cov-report=term-missing
npm ci
npm test
```

The automated tests use a scripted provider, so CI does not download model weights. Live-model quality is
checked separately with a smoke test.

## Limits

- First-time AI setup needs internet access and sufficient disk space.
- CPU inference speed depends on note length and hardware.
- Scanned PDFs, handwriting, diagrams, and complex visual layouts require OCR and are not interpreted.
- Jobs live in one Python process and disappear when the server restarts.
- Cancellation takes effect between inference passes, not in the middle of a PyTorch operation.
- The current architecture is intended for one local user, not a multi-user deployment.

## Troubleshooting

**First generation is slow:** the model is downloading or loading. Keep the application open; later runs reuse
the cache and the loaded runtime.

**Model setup fails:** confirm internet access and free disk space. Campus or corporate networks may block
Hugging Face downloads.

**CUDA runs out of memory:** set `HF_DEVICE=cpu`, restart Recall, and use a smaller input.

**Port 5000 is occupied:** set another `PORT` in `.env`, such as `5050`.

**PDF text is missing:** the PDF likely contains scanned images instead of embedded text. Run OCR before import.
