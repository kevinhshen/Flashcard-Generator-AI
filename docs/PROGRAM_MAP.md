# Program map

Recall has two generation paths behind one Flask API.

```mermaid
flowchart TD
    A[Notes] --> B{Generator}
    B -->|Local rules| C[Parse blocks and sentences]
    B -->|Ollama AI| D[Inventory and audit facts]
    D --> E[Draft and review cards]
    C --> F[Validate and deduplicate]
    E --> F
    F --> G[Editable review UI]
    G --> H[CSV export]
```

| File | Responsibility |
|---|---|
| `src/flashcard_generator/generator.py` | Deterministic parsing, card creation, and deduplication |
| `src/flashcard_generator/ai.py` | Ollama client, schemas, coverage pipeline, and source-grounding checks |
| `src/flashcard_generator/jobs.py` | One bounded background worker with progress and cancellation |
| `src/flashcard_generator/importers.py` | TXT, Markdown, and text-based PDF extraction |
| `src/flashcard_generator/web.py` | Flask pages and JSON endpoints |
| `src/flashcard_generator/templates/index.html` | UI structure |
| `src/flashcard_generator/static/app.js` | UI state, polling, editing, and CSV export |
| `tests/` | Python pipeline/API and JavaScript interface regressions |

The Ollama path uses `POST /api/generate` on the configured local Ollama server and sends a JSON schema with
every request. The app never needs a Gemini key or cloud SDK.
