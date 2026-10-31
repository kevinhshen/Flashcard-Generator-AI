# Recall interview guide

This guide is designed to help you explain the project accurately, defend its design decisions, and discuss its
limitations without overstating what it does.

## Thirty-second explanation

Recall is a local-first Flask application that converts notes into editable flashcards. I separated deterministic
text processing from language-model inference. Local code splits the notes into bounded source units and selects
an exact answer span. A small Hugging Face T5 model generates only the question, and the application validates
the result before showing it with its source excerpt. Generation runs as a background job so the UI stays
responsive, and users can review, edit, study, and export the deck without an API key or separate model server.

## The problem I was solving

Simple rule-based flashcard generators are reliable but miss unstructured prose. General chat models cover more
prose but can invent facts, require external services, and introduce cost or setup friction.

The project therefore uses a hybrid responsibility split:

- Deterministic code owns parsing, answer selection, validation, limits, and reporting.
- The language model handles the narrow task that benefits most from language understanding: phrasing a question
  for a known answer in a known context.
- The user remains the final reviewer through editable cards and visible evidence.

## High-level architecture

The application has six cooperating parts:

1. The browser collects notes and manages the editable deck.
2. Flask validates requests and selects the generation path.
3. The importer extracts bounded text from supported files.
4. The rules engine handles high-confidence structures without AI.
5. The AI engine selects source-grounded answers and generates questions locally.
6. The job manager runs expensive inference outside the request-response thread.

The data flow is:

**Notes → parsing → source units → answer selection → question generation → validation → review → CSV**

## Walk through the code in an interview

### Entry and web layer

`run.py` calls `flashcard_generator.web.run()`. That function creates the Flask app, opens the browser, and starts
the local server.

`web.py` is the coordination layer. It validates that notes are present, enforces the 200,000-character request
limit, validates the optional card limit, and dispatches to either `generate_local()` or `generate_deck()`.

The frontend normally uses `/api/jobs` for AI generation because model loading and inference can take longer than
a normal HTTP request. It polls `/api/jobs/<id>` until the job completes.

### Import layer

`importers.py` accepts TXT, Markdown, and text-based PDF files. It rejects oversized, binary, encrypted, damaged,
or unsupported input. PDF text extraction uses `pypdf`; the application does not pretend it can read diagrams or
scanned images.

### Deterministic generation

`generator.py` contains shared parsing plus the rules-only engine. It normalizes whitespace, recognizes labelled
blocks, splits prose into sentences, pairs explicit questions with their answers, identifies common definitions,
and creates limited numerical cloze cards.

This path is predictable and fast, but deliberately skips material it cannot interpret confidently.

### AI generation

`ai.py` creates source units of at most 420 characters. Each unit receives a literal answer span before the model
runs. The default checkpoint is `mrm8488/t5-base-finetuned-question-generation-ap`, which was specifically
fine-tuned to generate a question from an answer and context.

For example, given:

```text
An address identifies one byte.
```

The local selector chooses:

```text
one byte
```

The model prompt becomes:

```text
answer: one byte context: An address identifies one byte. </s>
```

A valid model response is:

```text
How many bytes does an address identify?
```

The accepted card is therefore:

- Front: `How many bytes does an address identify?`
- Back: `one byte`
- Source: `An address identifies one byte.`

The answer is not copied from model output. That is the central grounding mechanism.

### Validation and coverage

The validator rejects output that is multiline, empty, not a question, vague, or tautological. It also verifies
that the selected answer still appears in the source. Duplicate question-answer pairs are removed.

The application reports how many bounded source units produced accepted cards and lists the failures. You should
call this **source-unit coverage**, not fact coverage. A long sentence can contain several facts, so `10/10 units`
does not prove that every concept was converted into a card.

### Background jobs

`jobs.py` uses a one-worker `ThreadPoolExecutor`. Only one AI generation job can run at once, which avoids two
large inference tasks competing for RAM or GPU memory. Jobs exist only in memory and expire after 30 minutes.

Cancellation is cooperative. A cancellation flag is checked between inference passes, but a running PyTorch
operation is allowed to finish safely.

### Browser layer

`app.js` owns the visible deck. It submits requests, polls jobs, renders source evidence, tracks edits, provides a
study view, and creates the CSV entirely in the browser. Draft notes use browser `localStorage`; generated decks
are not stored on the server.

## Why this model instead of the first alternatives

### Why not Gemini?

The original cloud API path introduced key management, network dependence, quotas, and an external failure mode.
It also meant user notes could leave the machine. A local model better matches the project's privacy and
zero-recurring-cost goals.

Do not claim that a local model is always better. A strong cloud model would usually produce better questions
and handle more complex notes. The choice favors privacy, predictable availability after setup, and project
ownership over maximum model quality.

### Why not Ollama?

Ollama offers good local model serving, but every user must install and start another application, download a
model with separate commands, and keep its server available. That caused the `127.0.0.1:11434` connection error.

Running Transformers inside Recall removes the separate daemon. Python package installation provides the
runtime, and `from_pretrained()` handles the checkpoint download and cache automatically.

### Why not general-purpose FLAN-T5 Base?

FLAN-T5 Base was tested, but it frequently ignored the requested two-line card format or produced a question that
did not match the desired answer. Prompt engineering could not make that reliable enough.

The selected checkpoint is similar in scale but fine-tuned specifically for answer-aware question generation.
Narrowing the model's job produced more consistent output than asking a general instruction model to parse,
reason, format, and ground a complete card at once.

## Important design decisions

### Answers are deterministic; questions are generative

This reduces the most damaging failure: a plausible but unsupported card back. It does not completely eliminate
model error because the question can still misrepresent the answer or focus on the wrong relationship.

### The model loads lazily

Rules mode and the initial page do not pay the model startup cost. The first AI request downloads missing files
and loads weights. A runtime cache keeps the model in memory for later generations in the same process.

### Cached launches work offline

The application checks that configuration, tokenizer, and weight files exist locally. When the cache is complete,
it loads with `local_files_only=True`, preventing unnecessary network checks.

### AI failures do not silently fall back

Returning rules-generated cards after an AI failure could make users believe the complete AI pipeline succeeded.
Instead, the old visible deck remains unchanged and the failure is explicit. Users can deliberately select rules
mode if they want it.

### Coverage is reported after processing, not promised beforehand

The application attempts every bounded source unit before applying the optional card limit. This makes omissions
visible. The report still avoids claiming semantic completeness.

## Questions an interviewer may ask

### How do you prevent hallucinations?

I do not claim to prevent all hallucinations. I specifically prevent model-generated answers by selecting every
answer from the source before inference. I also attach the evidence excerpt and reject malformed or vague model
output. The remaining risk is question quality, which still requires human review.

### How is the model installed automatically?

PyTorch, Transformers, SentencePiece, and Protobuf are declared in `pyproject.toml`. When AI mode is used,
`AutoTokenizer.from_pretrained()` and `AutoModelForSeq2SeqLM.from_pretrained()` download the default checkpoint if
it is missing. Hugging Face stores it in its standard user cache, and later runs reuse it.

### Why use a sequence-to-sequence model?

Question generation is naturally a text-to-text transformation: answer plus context goes in, and a question
comes out. T5 is designed around this interface and is much smaller than a general chat model, making local CPU
execution realistic.

### Why is each source unit limited to 420 characters?

The model has a bounded input context, and short focused contexts reduce truncation, latency, and topic mixing.
The value is a practical character-level guard rather than a perfect tokenizer-aware limit. A future version
could chunk by tokens instead.

### Why use one model call per source unit?

It creates simple provenance: one context, one answer, one question, one validation decision. Batching could be
faster, but it complicates mapping output back to evidence and makes malformed output harder to isolate.

### Why use a thread instead of Celery or a task queue?

This is a single-user local application. A one-worker thread keeps the interface responsive without adding Redis,
a broker, worker deployment, or cross-process state. For a hosted multi-user product, I would move jobs to a
durable queue and store their state in a database.

### Is the application fully offline?

Not on the first AI run because it must download the model. After the checkpoint is cached, inference, parsing,
editing, and export run locally. Rules mode is offline from the beginning.

### What data is persisted?

The Python application does not persist notes, cards, or jobs. Draft notes are stored in browser `localStorage`,
job state is held in server memory, and exported CSV files are created by the browser. Model files persist in the
Hugging Face cache.

### What happens when generation fails?

Exceptions are mapped to stable user-facing categories such as missing dependencies, unavailable devices, setup
failures, timeouts, and out-of-memory errors. Raw exceptions are not returned because they could contain local
paths or note fragments. The browser keeps the previous deck visible.

### How did you test it?

Python tests cover parsing, answer grounding, malformed model output, device selection, limits, job cancellation,
imports, and API behavior. JavaScript tests run in JSDOM and cover polling, editing, timeouts, storage failures,
and deck preservation. CI runs linting, coverage, Python tests, and browser tests. I also ran a live smoke test
against the actual checkpoint because mocked providers cannot measure language quality.

### Why not let the model identify every fact?

A small local model is unreliable at long multi-stage extraction and structured output. The current architecture
uses transparent sentence and block boundaries and reports its limited coverage honestly. A future system could
add a separate extraction model or semantic segmentation stage, but it would need evidence-level evaluation.

### What would you improve next?

A strong answer is:

1. Build an evaluation set with human-rated question correctness, clarity, and coverage.
2. Replace character chunking with tokenizer-aware semantic segmentation.
3. Add answer-candidate ranking so generic prose produces more focused answers.
4. Add optional OCR for scanned PDFs while clearly separating extracted text from visual interpretation.
5. Quantize the model or support ONNX for faster CPU startup and inference.
6. Add persistent decks only if users want them, with an explicit privacy model.

## Tradeoffs you should state candidly

- The model is easy to launch after Python setup, but the first download is still roughly 900 MB.
- Local inference avoids API cost but is slower than a hosted GPU service on many computers.
- Exact source answers improve factual grounding but can be awkward or overly long.
- Sentence-level units improve provenance but can split related context.
- One inference per unit is simple and auditable but not throughput-optimal.
- Source-unit coverage is measurable; true fact coverage is not yet measured.
- The app is robust for one local user, not architected for multi-user production deployment.

## Demo script

Use a short example so the architecture is visible rather than waiting on a large document.

1. Start the app with `python run.py`.
2. Paste two facts: `An address identifies one byte. A pointer occupies four bytes.`
3. Show rules mode first and explain its conservative pattern matching.
4. Switch to AI mode and generate two questions.
5. Open each source excerpt and show that the answer is copied from it.
6. Edit one card and point out that the coverage report becomes stale.
7. Use the study view and export CSV.
8. Briefly show `ai.py`, `jobs.py`, and the test suite.

## Claims to avoid

Do not say:

- “The model cannot hallucinate.” The answer is grounded, but the question can still be weak or misleading.
- “Coverage means every fact was found.” It measures processed source units.
- “It is always offline.” The first model download requires internet access.
- “Cancellation is immediate.” It occurs between inference passes.
- “It scales to many users.” The current job store and model runtime are intentionally single-process.
- “PDF import understands diagrams.” It extracts embedded text only.

## Final one-minute answer

I built Recall as a local-first flashcard generator with explicit boundaries between deterministic logic and AI.
Flask handles validation and routes, a background worker keeps model inference off the request path, and shared
parsing converts notes into bounded source units. The key decision was to select answers directly from the source
and use a fine-tuned T5 model only to phrase questions. That gives me stronger grounding and simpler validation
than asking a general model to produce complete cards. The UI keeps the source visible, reports rejected units,
and lets users edit before export. I tested the orchestration with mocked providers, the frontend with JSDOM, and
the actual checkpoint with a live smoke test. The main remaining weaknesses are semantic coverage and question
quality, so my next step would be a human-rated evaluation set and better answer-candidate ranking.
