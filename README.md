# Local Flashcard Generator

This project converts study notes into reviewable flashcards and exports an Anki-compatible TSV file. It has no API key or cloud API dependency. Rules mode stays small and offline; FLAN-T5 Base runs locally only when you choose an AI engine.

## Current capabilities

- Reads pasted notes or a UTF-8 text file
- Preserves paragraph and labelled-section boundaries
- Creates cards from labels, definitions, question/answer pairs, and factual cloze statements
- Removes invalid and duplicate cards
- Exports tab-separated front/back fields that Anki can import
- Lets you review AI cards, edit any reviewed card, regenerate AI cards from source, or discard them before export
- Offers a deterministic local FLAN-T5 Base engine with strict output and source-grounding checks

## Setup

Create a virtual environment, activate it, and install the rules-mode dependencies.

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

The program works without NLTK or downloaded NLTK data by using a standard-library sentence splitter. To use NLTK's sentence splitter, install the requirement above and optionally download its tokenizer data:

```powershell
python -m nltk.downloader punkt_tab
```

For local FLAN-T5 Base support, install the optional AI dependencies. The first AI run downloads model files from Hugging Face; use `--offline` after that to require the local cache.

```powershell
python -m pip install -r requirements-ai.txt
```

## Run

Generate and export cards from an included note file:

```powershell
python FlashcardGenerator.py --input note1.txt --output flashcards.tsv
```

Preview without writing a file:

```powershell
python FlashcardGenerator.py --input note1.txt --no-export
```

Use `hybrid` for normal AI-assisted work. It keeps high-confidence rules (labels, definitions, Q/A pairs), asks FLAN to handle uncertain or unhandled facts, and automatically offers clearly fragmentary rule answers to FLAN for a careful rewrite. Use `flan` only when you want to evaluate model-only output.

```powershell
python FlashcardGenerator.py --input note1.txt --engine hybrid --review
```

`--review` pauses only for AI-generated or AI-improved cards and shows their source. Press Enter to keep it, `e` to edit, `r` to regenerate it from that source, `d` to discard, or `q` to keep the remaining cards. Use `--review-all` when you want to edit every card. The automatic quality pass is `--polish auto`; use `--polish off` to disable it or `--polish all` to ask FLAN to check every rule card. AI cards are deterministic, one source chunk at a time, and rejected if they have malformed output or introduce a number/acronym absent from their source. Those checks reduce obvious errors; they do not prove factual correctness, so review remains part of the workflow.

To paste notes instead, run `python FlashcardGenerator.py`, paste text, then enter `END` on its own line.

In Anki, import the generated TSV file as UTF-8 text with tab-separated fields and no header row.

## Web app

The local web app uses the same generation and validation pipeline as the command line. It keeps the notes draft in your browser, reads `.txt` imports in the browser, and creates the TSV download in the browser.

```powershell
python -m pip install -r requirements-web.txt
python run_web_app.py
```

Open `http://127.0.0.1:5000` in your browser. For Hybrid or FLAN-only generation, also install `requirements-ai.txt`.

The web app includes:

- Paste notes, import a `.txt` file, use an example, and retain a local browser draft
- Rules, Hybrid, and FLAN-only generation modes
- Quality-pass and device settings for AI modes
- Editable cards, source visibility, AI-card filtering, and model regeneration from a card's source
- Anki TSV download without writing your notes to a server-side output file

## Test

```powershell
python -m unittest discover -s tests -v
```

## Next milestone

Build a reviewed evaluation set from real notes before changing prompts or model settings. Measure accepted-card precision, duplicate rate, source-grounding failures, and edit/discard rate. See [the architecture notes](docs/architecture.md).
