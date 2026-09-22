"""Local, bounded text extraction. No uploads leave the local Python server."""

from io import BytesIO
from pathlib import Path

from pypdf import PdfReader

MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_TEXT_CHARS = 200_000


def extract_notes(filename: str, raw: bytes) -> dict:
    if len(raw) > MAX_FILE_BYTES:
        raise ValueError("File exceeds the 10 MB limit.")
    suffix = Path(filename).suffix.lower()
    warning = ""
    if suffix in {".txt", ".md"}:
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ValueError("Save text files as UTF-8 and try again.") from exc
    elif suffix == ".pdf":
        if not raw.lstrip().startswith(b"%PDF-"):
            raise ValueError("This file is not a valid PDF.")
        try:
            reader = PdfReader(BytesIO(raw))
            if reader.is_encrypted:
                raise ValueError("Password-protected PDFs are not supported. Import an unlocked copy.")
            if len(reader.pages) > 200:
                raise ValueError("PDF exceeds 200 pages. Split it into smaller files.")
            pages = []
            empty = 0
            total = 0
            for page in reader.pages:
                page_text = (page.extract_text() or "").strip()
                empty += not bool(page_text)
                total += len(page_text) + 2
                if total > MAX_TEXT_CHARS:
                    raise ValueError("Extracted text exceeds 200,000 characters. Split the PDF.")
                pages.append(page_text)
            text = "\n\n".join(pages)
            if empty:
                warning = (
                    f"{empty} page(s) had no extractable text; scanned pages need OCR. "
                    "Diagrams are not read. Check the extracted text before generating."
                )
        except ValueError:
            raise
        except Exception as exc:
            raise ValueError("Could not read this PDF. It may be damaged or unsupported.") from exc
        if not text.strip():
            raise ValueError("No embedded text found. Scanned/image-only PDFs need OCR first.")
    else:
        raise ValueError("Supported files: .txt, .md, and text-based .pdf. Images need OCR first.")
    if not text.strip():
        raise ValueError("The file contains no text.")
    if len(text) > MAX_TEXT_CHARS:
        raise ValueError("Text exceeds 200,000 characters. Import a smaller section.")
    if "\x00" in text:
        raise ValueError("The file contains binary data, not plain text.")
    return {"text": text, "warning": warning}
