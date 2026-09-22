from io import BytesIO

import pytest
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from flashcard_generator.importers import extract_notes
from flashcard_generator.web import create_app


def pdf_bytes(text=None, encrypted=False):
    """Build a tiny PDF in memory so the real parser is exercised without fixtures."""
    writer = PdfWriter()
    page = writer.add_blank_page(width=400, height=400)
    if text:
        font = DictionaryObject(
            {
                NameObject("/Type"): NameObject("/Font"),
                NameObject("/Subtype"): NameObject("/Type1"),
                NameObject("/BaseFont"): NameObject("/Helvetica"),
            }
        )
        page[NameObject("/Resources")] = DictionaryObject(
            {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})}
        )
        stream = DecodedStreamObject()
        stream.set_data(f"BT /F1 12 Tf 20 200 Td ({text}) Tj ET".encode())
        page[NameObject("/Contents")] = stream
    if encrypted:
        writer.encrypt("password")
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def test_real_pdf_extracts_text():
    assert "Force: A push or pull." in extract_notes("notes.pdf", pdf_bytes("Force: A push or pull."))["text"]


def test_upload_endpoint():
    response = (
        create_app()
        .test_client()
        .post(
            "/api/import",
            data={
                "file": (BytesIO(pdf_bytes("Velocity: Displacement per second.")), "notes.pdf"),
            },
        )
    )
    assert response.status_code == 200
    assert "Velocity:" in response.get_json()["text"]


@pytest.mark.parametrize(
    ("name", "raw", "message"),
    [
        ("scan.pdf", pdf_bytes(), "OCR"),
        ("secret.pdf", pdf_bytes("Private", encrypted=True), "Password"),
        ("bad.pdf", b"not a PDF", "valid PDF"),
        ("image.png", b"image", "Images need OCR"),
        ("empty.txt", b"   ", "no text"),
        ("bad.txt", b"\xff", "UTF-8"),
    ],
)
def test_import_errors(name, raw, message):
    with pytest.raises(ValueError, match=message):
        extract_notes(name, raw)


def test_text_utf8_bom():
    assert extract_notes("notes.md", b"\xef\xbb\xbf# Notes")["text"] == "# Notes"
