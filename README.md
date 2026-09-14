# Local Flashcard Generator

This project converts study notes into reviewable flashcards and exports an Anki-compatible TSV file. The current version uses deterministic local rules only: it has no API key and no cloud AI dependency.

## Current capabilities

- Reads pasted notes or a UTF-8 text file
- Preserves paragraph and labelled-section boundaries
- Creates cards from labels, definitions, question/answer pairs, and factual cloze statements
- Removes invalid and duplicate cards
- Exports tab-separated front/back fields that Anki can import

## Setup

Create a virtual environment, activate it, and install the optional sentence-tokenization dependency.

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

The program works without NLTK or downloaded NLTK data by using a standard-library sentence splitter. To use NLTK's sentence splitter, install the requirement above and optionally download its tokenizer data:

```powershell
python -m nltk.downloader punkt_tab
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

To paste notes instead, run `python FlashcardGenerator.py`, paste text, then enter `END` on its own line.

In Anki, import the generated TSV file as UTF-8 text with tab-separated fields and no header row.

## Test

```powershell
python -m unittest discover -s tests -v
```

## Next milestone

Build an evaluation set from reviewed source chunks, then add FLAN-T5 Base as an optional local generator behind the existing validation and export pipeline. See [the architecture notes](docs/architecture.md).
