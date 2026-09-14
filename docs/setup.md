# Setup

Use a fresh virtual environment instead of the old `env` directory.

## Windows PowerShell

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## macOS or Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

NLTK is optional. The program includes a fallback sentence splitter, but you can download NLTK's tokenizer data after installing it:

```bash
python -m nltk.downloader punkt_tab
```

Run the tests before changing generation behavior:

```bash
python -m unittest discover -s tests -v
```
