# Recall

A Flask app that turns study notes into editable flashcards using the Gemini API. Paste notes or import a text, Markdown, or text-based PDF file, review the cards, and export them as CSV.

## Run locally

Requires Python 3.10+ and a [Gemini API key](https://aistudio.google.com/app/apikey).

From the repository folder in Windows PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
python run.py
```

Open `http://127.0.0.1:5000`, enter your API key, and click **Save**. The key is stored in the project's gitignored `.env` file.

## How it works

Gemini extracts facts from your notes, checks for omissions, then drafts and reviews cards. The app checks source excerpts, removes duplicates, and reports coverage gaps. You can edit, add, delete, and preview cards before exporting.

Gemini generation sends note text to Google and uses your API quota. Review the results against your notes; coverage counts do not guarantee accuracy or completeness. Scanned PDFs and diagrams are unsupported.

An optional **Local rules** mode handles simple note patterns offline without a language model.
