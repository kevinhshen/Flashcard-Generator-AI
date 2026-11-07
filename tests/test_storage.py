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
    assert book.sheetnames == ["runs", "stage_usage", "cards", "facts"]
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
    assert book["facts"].max_row == 1


def test_input_size_label_settings_and_stage_counts_are_saved():
    stats = {"chunk_size": 6000, "temperature": 0.15, "prompt_sha256": "abc", "model_version": "m-1",
             "retries": 2, "retry_wait_s": 6, "facts_added_by_audit": 3, "not_a_column": "ignored"}
    save(stats=stats, notes_label="dsa.txt")
    [run] = query("SELECT * FROM runs")
    assert run["notes_chars"] == len(NOTES)
    assert run["notes_words"] == 10
    assert run["notes_label"] == "dsa.txt"
    assert (run["chunk_size"], run["temperature"], run["prompt_sha256"]) == (6000, 0.15, "abc")
    assert (run["model_version"], run["retries"], run["retry_wait_s"]) == ("m-1", 2, 6)
    assert run["facts_added_by_audit"] == 3
    assert run["batch_size"] is None  # not reported, so left empty rather than guessed
    assert run["git_dirty"] in {0, 1, None}


def test_token_types_and_api_time_add_up_across_requests():
    calls = [{**CALLS[0], "thinking_tokens": 5, "cached_tokens": 7}, {**CALLS[2], "thinking_tokens": 1}]
    save(calls=calls)
    [run] = query("SELECT * FROM runs")
    assert (run["thinking_tokens"], run["cached_tokens"]) == (6, 7)
    assert run["api_seconds"] == 3.5


def test_request_details_are_saved():
    call = {**CALLS[0], "input_chars": 900, "items_returned": 4, "finish_reason": "STOP"}
    failed = {**CALLS[1], "input_chars": 800, "error_code": "quota"}
    save(calls=[call, failed])
    first, second = query("SELECT * FROM stage_usage ORDER BY seq")
    assert (first["input_chars"], first["items_returned"], first["finish_reason"]) == (900, 4, "STOP")
    assert (second["status"], second["error_code"]) == ("error", "quota")


def test_cards_record_their_facts_and_lengths():
    result = {**RESULT, "cards": [{"front": "Front?", "back": "Back", "fact_ids": ["S1F1", "S1F2"]},
                                  {"front": "Local card", "back": "No fact ids"}]}
    save(result=result)
    with_ids, without_ids = query("SELECT * FROM cards ORDER BY position")
    assert with_ids["fact_ids"] == "S1F1,S1F2"
    assert (with_ids["front_chars"], with_ids["back_chars"]) == (6, 4)
    assert without_ids["fact_ids"] is None


def test_facts_are_saved_and_exported_with_their_outcome():
    facts = [
        {"fact_id": "S1F1", "section": 1, "text": "A fact", "source_quote": "A quote", "outcome": "covered"},
        {"fact_id": None, "section": 1, "text": "Gone", "source_quote": "Other", "outcome": "audit_removed"},
    ]
    row = save(facts=facts)
    saved = query("SELECT * FROM facts ORDER BY id")
    assert [fact["outcome"] for fact in saved] == ["covered", "audit_removed"]
    assert saved[0]["run_id"] == row["run_id"]
    assert saved[1]["fact_id"] is None
    assert load_workbook(BytesIO(storage.export_workbook()))["facts"].max_row == 3
    assert "audit_removed" in storage.export_csv("facts").decode("utf-8-sig")


def test_old_database_is_upgraded_without_touching_its_rows():
    old_columns = "run_id TEXT PRIMARY KEY, created_at TEXT NOT NULL, notes_chars INTEGER"
    conn = sqlite3.connect(storage.db_path())
    with closing(conn), conn:
        conn.execute(f"CREATE TABLE runs ({old_columns})")
        conn.execute("INSERT INTO runs VALUES ('old-run', '2026-01-01', 123)")
        conn.execute("CREATE TABLE cards (card_id INTEGER PRIMARY KEY, run_id TEXT, front TEXT)")
        conn.execute("INSERT INTO cards (run_id, front) VALUES ('old-run', 'Old front')")

    upgraded = storage.connect()
    with closing(upgraded):
        upgraded.row_factory = sqlite3.Row
        old = dict(upgraded.execute("SELECT * FROM runs WHERE run_id = 'old-run'").fetchone())
        card = dict(upgraded.execute("SELECT * FROM cards").fetchone())
    assert (old["created_at"], old["notes_chars"]) == ("2026-01-01", 123)
    assert old["notes_words"] is None
    assert (card["front"], card["fact_ids"]) == ("Old front", None)


def test_real_older_database_still_accepts_new_runs():
    """The exact case in data/: tables made by the previous version, then a new run is saved."""
    previous_schema = storage.SCHEMA
    conn = sqlite3.connect(storage.db_path())
    with closing(conn):
        conn.executescript(previous_schema)  # SCHEMA holds the original columns only
    assert save(stats={"chunk_size": 6000}, facts=[{"fact_id": "S1F1", "outcome": "covered"}]) is not None
    assert query("SELECT chunk_size FROM runs") == [{"chunk_size": 6000}]


def test_control_characters_from_pdfs_do_not_break_the_excel_export():
    result = {**RESULT, "cards": [{"front": "Page\x0cbreak?", "back": "Yes", "source": "Page\x0cbreak"}]}
    save(result=result)
    sheet = load_workbook(BytesIO(storage.export_workbook()))["cards"]
    assert "Pagebreak?" in [cell.value for row in sheet.iter_rows() for cell in row]
