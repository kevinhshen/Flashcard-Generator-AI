import hashlib
import sqlite3
from contextlib import closing
from io import BytesIO

import pytest
from openpyxl import load_workbook

from flashcard_generator import storage

NOTES = "An address identifies one byte. A pointer occupies four bytes."
RESULT = {
    "cards": [
        {
            "front": "What does an address identify?",
            "back": "One byte.",
            "card_type": "basic",
            "source": "An address identifies one byte.",
        },
        {
            "front": '=HYPERLINK("http://example.test")',
            "back": "Looks like a formula",
            "source": "-1 pointer",
        },
    ],
    "mode": "ai",
    "model": "test-model",
    "coverage": {
        "identified_facts": 4,
        "covered_facts": 3,
        "rejected_facts": [{"text": "unsupported"}],
        "uncovered": [{"text": "missing"}],
        "requests": 2,
        "sections_total": 1,
        "cards_generated": 2,
    },
}
CALLS = [
    {"stage": "inventory", "status": "ok", "seconds": 1.5,
     "input_tokens": 100, "output_tokens": 20, "total_tokens": 150},
    {"stage": "draft", "status": "error", "seconds": 0.5,
     "input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
    {"stage": "draft", "status": "ok", "seconds": 2.0,
     "input_tokens": 80, "output_tokens": 40, "total_tokens": 130},
]


def save(**overrides):
    fields = {
        "notes": NOTES, "result": RESULT, "mode": "ai", "model": None, "status": "completed",
        "error_code": None, "card_limit": None, "duration_s": 4.0, "calls": CALLS,
    }
    fields.update(overrides)
    return storage.save_run(**fields)


def query(sql):
    conn = storage.connect()
    with closing(conn):
        conn.row_factory = sqlite3.Row
        return [dict(row) for row in conn.execute(sql).fetchall()]


def test_run_is_saved_with_its_requests_cards_and_derived_numbers():
    row = save()
    [run] = query("SELECT * FROM runs")
    assert run["run_id"] == row["run_id"]
    assert run["model"] == "test-model"
    assert (run["input_tokens"], run["output_tokens"], run["total_tokens"]) == (180, 60, 280)
    assert run["coverage_pct"] == 75.0
    assert run["source_verified_pct"] == 80.0  # 4 quotes found in the notes, 1 not found
    assert run["card_count"] == 2
    assert run["tokens_per_card"] == 140.0
    assert run["seconds_per_card"] == 2.0
    assert run["notes_sha256"] == hashlib.sha256(NOTES.encode("utf-8")).hexdigest()
    assert run["notes_chars"] == len(NOTES)
    assert [call["stage"] for call in query("SELECT * FROM stage_usage ORDER BY seq")] == [
        "inventory", "draft", "draft"
    ]
    assert len(query("SELECT * FROM cards")) == 2


def test_source_verified_counts_rejected_facts_in_the_denominator():
    coverage = {"identified_facts": 10, "covered_facts": 10, "rejected_facts": [{"text": "x"}] * 2}
    row = save(result={"cards": [], "coverage": coverage})
    assert row["source_verified_pct"] == 83.3  # 10 of 12, not (10 - 2) of 10


def test_foreign_keys_are_enforced():
    conn = storage.connect()
    with closing(conn), pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO cards (run_id, position) VALUES ('no-such-run', 1)")


def test_full_notes_text_is_never_stored_in_the_run_row():
    save()
    assert NOTES not in str(query("SELECT * FROM runs"))


def test_failed_run_keeps_the_requests_made_before_failing():
    save(result=None, status="failed", error_code="quota", calls=CALLS[:2])
    [run] = query("SELECT * FROM runs")
    assert (run["status"], run["error_code"], run["requests"]) == ("failed", "quota", 2)
    assert run["card_count"] == 0
    assert run["coverage_pct"] is None
    assert query("SELECT * FROM cards") == []


def test_storage_problem_returns_none_instead_of_raising(monkeypatch, tmp_path):
    blocker = tmp_path / "not-a-folder"
    blocker.write_text("this file blocks the data folder")
    monkeypatch.setenv("RECALL_DATA_DIR", str(blocker))
    assert save() is None


def test_summary_of_missing_run_is_all_none():
    assert storage.summary(None)["run_id"] is None
    assert set(storage.summary(None)) == set(storage.SUMMARY_FIELDS)


def test_export_is_a_workbook_with_one_sheet_per_table():
    save()
    book = load_workbook(BytesIO(storage.export_workbook()))
    assert book.sheetnames == ["runs", "stage_usage", "cards"]
    assert book["runs"].max_row == 2
    assert "coverage_pct" in [cell.value for cell in book["runs"][1]]
    assert book["stage_usage"].max_row == 4
    assert book["cards"].max_row == 3


def test_spreadsheet_formulas_from_card_text_are_kept_as_text():
    save()
    sheet = load_workbook(BytesIO(storage.export_workbook()))["cards"]
    [cell] = [c for row in sheet.iter_rows() for c in row if c.value == '=HYPERLINK("http://example.test")']
    assert cell.data_type == "s"


def test_empty_database_exports_headers_only():
    book = load_workbook(BytesIO(storage.export_workbook()))
    assert book["runs"].max_row == 1
    assert book["cards"].max_row == 1
