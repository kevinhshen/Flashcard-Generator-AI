# Setup

This project needs both Python packages and NLTK tokenizer data.

## 1. Activate the virtual environment

### macOS

```bash
source ".venv/bin/activate"
```

### Windows PowerShell

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\env\Scripts\Activate.ps1
```

## 2. Install Python packages

```bash
python -m pip install -r requirements.txt
```

## 3. Download NLTK data

Run this once after installing requirements:

```bash
python -m nltk.downloader punkt punkt_tab
```

## macOS certificate fix

If macOS shows an SSL error like `CERTIFICATE_VERIFY_FAILED`, run:

```bash
open "/Applications/Python 3.13/Install Certificates.command"
```

Then retry:

```bash
python -m nltk.downloader punkt punkt_tab
```

If that still fails, use the certificate bundle from `certifi`:

```bash
SSL_CERT_FILE=$(python -m certifi) python -m nltk.downloader punkt punkt_tab
```

## Run the app

```bash
python FlashcardGenerator.py
```
