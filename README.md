# Recall — self-contained local AI flashcard generator

Recall turns notes into editable flashcards and exports CSV for Anki, Quizlet, or a spreadsheet. Its default AI
backend is `mrm8488/t5-base-finetuned-question-generation-ap`, loaded directly in Python through Hugging Face
Transformers. Users do not need an API key, Ollama, Docker, or a separate model server.

## Features

- Imports pasted text, UTF-8 text, Markdown, and text-based PDFs up to 10 MB / 200 pages.
- Downloads and caches the question-generation T5 model automatically the first time AI generation is used.
- Uses an NVIDIA GPU automatically when PyTorch detects CUDA, with CPU and Apple MPS fallbacks.
- Selects answers deterministically from exact source excerpts; the model writes only the questions.
- Reports which bounded source units produced cards and why other units were rejected.
- Provides a separate deterministic rules mode with no model download or inference.
- Runs AI generation in a background job with progress, cancellation, and refresh reconnection.
- Lets users edit, add, remove, preview, and export cards.
- Stores draft notes in browser local storage; the Python server does not write notes to disk.

## Quick start

Python 3.10 or newer is required.

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
python run.py
```

The browser opens to `http://127.0.0.1:5000`. The original `python FlashcardGenerator.py` launcher also works.

That is the complete setup. The Python installation includes PyTorch, Transformers, and SentencePiece. On the
first AI generation, Transformers downloads the default checkpoint from Hugging Face and stores it in the normal
Hugging Face cache. It is about 900 MB; later runs reuse those files. The initial download can take several
minutes depending on the connection, and progress remains visible in the app.

If PowerShell blocks virtual-environment activation, run this once in the current terminal and activate again:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

## Optional configuration

The defaults need no `.env` file. Copy `.env.example` to `.env` only to override them:

```dotenv
HF_MODEL_ID=mrm8488/t5-base-finetuned-question-generation-ap
HF_DEVICE=auto
HOST=127.0.0.1
PORT=5000
```

`HF_DEVICE` accepts `auto`, `cpu`, `cuda`, or `mps`. `auto` prefers CUDA, then Apple MPS, then CPU. `HF_MODEL_ID`
is an advanced override: replacements must support the T5 `answer: ... context: ...` question-generation format.

## Using Recall

1. Paste notes or import a supported file.
2. Leave the card limit blank to process every bounded source unit, or choose a cap from 1–500.
3. Keep **T5 question model · local AI** selected, or choose **Local rules** for fast deterministic parsing.
4. Generate and leave the app open while the first-use model download and inference finish.
5. Inspect rejected units and source excerpts, edit cards, and export CSV.

The CSV has `Front`, `Back`, and `Type` columns. Map `Front` and `Back` to the corresponding Anki fields.

## How local AI generation works

1. Parse labelled blocks, normal sentences, and explicit question/answer pairs.
2. Split long material into source units of at most 420 characters to stay inside T5's bounded context.
3. Select a literal answer span using question/answer, label, definition, and quantity structure.
4. Ask the fine-tuned T5 model to write one question for that answer and context.
5. Reject malformed output, non-questions, tautologies, vague questions, and duplicates.
6. Apply the optional card cap only after every source unit has been attempted.

This is deliberately different from a large chat-model pipeline. Live testing showed that general-purpose
FLAN-T5 Base often ignored the requested card format or generated the wrong question. The default checkpoint is
similar in size but fine-tuned for answer-aware question generation. Keeping answers outside the model prevents
invented back sides while short prompts and deterministic validation fit the model's actual capabilities.

Source-unit coverage is not fact coverage. A sentence can contain several facts, the parser can choose an
imperfect boundary, and a small model can generate a weak question even when the answer is a valid quote. Review
the deck before relying on it for high-stakes material.

## Local rules mode

Rules mode recognizes labelled sections, explicit question/answer pairs, common definitions, and numerical
quantities with units. It is fast and deterministic, but it does not use T5. Every answer is copied from
the source.

## Development

```powershell
python -m pip install -e ".[dev]"
ruff check .
pytest --cov=flashcard_generator --cov-report=term-missing
npm ci
npm test
```

Unit tests inject a scripted model provider, so CI does not download model weights. They validate source
partitioning, grounding, failure handling, cancellation, API behavior, and the interface. A separate live smoke
test is needed to assess actual model quality.

Project layout:

```text
src/flashcard_generator/
├── ai.py             # Lazy T5 loading, answer selection, question generation, and validation
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
`POST /api/jobs/<job_id>/cancel`. `GET /api/status` reports dependency, model-cache, and in-memory load status
without initiating a download.

## Troubleshooting

**First generation appears slow:** The model is downloading and loading. Keep the app open. Later runs reuse the
cache and the loaded process memory.

**Model setup failed:** Confirm internet access and adequate free disk space, then retry. Corporate or campus
networks may block Hugging Face downloads.

**CUDA out of memory:** Set `HF_DEVICE=cpu`, restart Recall, and try fewer or shorter notes.

**Generation is slow on CPU:** Reduce the input or keep the app process running so the model does not need to
reload. Each bounded source unit requires one inference pass.

**Port 5000 is occupied:** Set `PORT=5050` in `.env` and restart Recall.

**PDF content is missing:** Scanned pages, diagrams, handwriting, and complex mathematical layout need OCR and
are not supported. Review extracted text before generating.

## Limits

- The first AI run requires internet access to download model files.
- Local inference speed depends on CPU/GPU and note length.
- Generated questions still require human review.
- Jobs live in one Python process and disappear when the server restarts.
- Cancellation takes effect after the current model pass returns.
- The app is intended for one local user and has no accounts or shared decks.
