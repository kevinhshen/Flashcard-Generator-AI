"""Save one row per generation run into a SQLite file (research data)."""

import csv
import hashlib
import io
import logging
import os
import sqlite3
import subprocess
import uuid
from contextlib import closing
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

from openpyxl import Workbook

log = logging.getLogger(__name__)

# SQL commands
SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    mode TEXT, model TEXT, status TEXT, error_code TEXT,
    notes_sha256 TEXT, notes_chars INTEGER, card_limit INTEGER,
    duration_s REAL,
    input_tokens INTEGER, output_tokens INTEGER, total_tokens INTEGER,
    requests INTEGER, sections INTEGER,
    identified_facts INTEGER, covered_facts INTEGER, rejected_facts INTEGER, uncovered_facts INTEGER,
    cards_generated INTEGER, card_count INTEGER,
    coverage_pct REAL, source_verified_pct REAL, tokens_per_card REAL, seconds_per_card REAL,
    git_commit TEXT
);
CREATE TABLE IF NOT EXISTS stage_usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL REFERENCES runs(run_id),
    seq INTEGER, stage TEXT, status TEXT, seconds REAL,
    input_tokens INTEGER, output_tokens INTEGER, total_tokens INTEGER
);
CREATE TABLE IF NOT EXISTS cards (
    card_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL REFERENCES runs(run_id),
    position INTEGER, front TEXT, back TEXT, card_type TEXT, source_excerpt TEXT
);
"""

# Columns shown on the Run page after a generation (the rest stay in the database).
SUMMARY_FIELDS = (
    "run_id", "status", "duration_s", "total_tokens", "requests", "identified_facts",
    "covered_facts", "coverage_pct", "source_verified_pct", "card_count",
    "tokens_per_card", "seconds_per_card",
)
EXPORT_QUERIES = {
    "runs": "SELECT * FROM runs ORDER BY created_at",
    "stage_usage": "SELECT * FROM stage_usage ORDER BY run_id, seq",
    "cards": "SELECT * FROM cards ORDER BY run_id, position",
}
# Excel reads a text cell starting with these as a formula, so such cells are forced to text.
FORMULA_PREFIXES = ("=", "+", "-", "@")
MAX_CELL_CHARS = 32000  # Excel's per-cell limit


def db_path() -> Path:
    default = Path(__file__).resolve().parents[2] / "data"
    folder = Path(os.getenv("RECALL_DATA_DIR") or default)
    folder.mkdir(parents=True, exist_ok=True)
    return folder / "recall_research.db"


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(db_path())
    conn.execute("PRAGMA foreign_keys = ON")  # SQLite ignores REFERENCES unless this is set per connection
    conn.executescript(SCHEMA)  # CREATE ... IF NOT EXISTS: safe to run on every connection
    return conn


@lru_cache(maxsize=1)
def git_commit() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=5,
            cwd=Path(__file__).resolve().parent,
        )
        return out.stdout.strip()
    except Exception:
        return ""


def _pct(part, whole):
    return round(100 * part / whole, 1) if whole else None


def _run_row(*, notes, result, mode, model, status, error_code, card_limit, duration_s, calls):
    result = result or {}
    coverage = result.get("coverage") or {}
    cards = result.get("cards") or []
    token_keys = ("input_tokens", "output_tokens", "total_tokens")
    totals = {key: sum(call[key] for call in calls) for key in token_keys}
    identified = coverage.get("identified_facts")
    covered = coverage.get("covered_facts")
    rejected = len(coverage.get("rejected_facts") or []) if coverage else None
    return {
        "run_id": uuid.uuid4().hex,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "mode": mode,
        "model": result.get("model") or model,
        "status": status,
        "error_code": error_code,
        "notes_sha256": hashlib.sha256(notes.encode("utf-8")).hexdigest(),
        "notes_chars": len(notes),
        "card_limit": card_limit,
        "duration_s": round(duration_s, 3),
        **totals,
        "requests": coverage.get("requests", len(calls)),
        "sections": coverage.get("sections_total"),
        "identified_facts": identified,
        "covered_facts": covered,
        "rejected_facts": rejected,
        "uncovered_facts": len(coverage.get("uncovered") or []) if coverage else None,
        "cards_generated": coverage.get("cards_generated"),
        "card_count": len(cards),
        # Coverage: share of identified facts that got a card. Source-verified: share of all quoted
        # facts whose excerpt was found in the notes (a proxy for not inventing facts; not a human
        # accuracy check). identified_facts only counts facts that passed, so rejected ones are added back.
        "coverage_pct": _pct(covered, identified),
        "source_verified_pct": _pct(identified, (identified or 0) + (rejected or 0)),
        "tokens_per_card": round(totals["total_tokens"] / len(cards), 1) if cards and calls else None,
        "seconds_per_card": round(duration_s / len(cards), 2) if cards and calls else None,
        "git_commit": git_commit(),
    }


def _insert_rows(conn, table, rows):
    if not rows:
        return
    columns = list(rows[0])
    sql = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({', '.join('?' for _ in columns)})"
    conn.executemany(sql, [tuple(row[column] for column in columns) for row in rows])


def save_run(*, notes, result, mode, model, status, error_code, card_limit, duration_s, calls=()):
    """Save one run, its AI requests and its cards.

    Never raises: a storage problem must not break card generation. Returns the saved
    run row (a dict), or None if nothing was saved.
    """
    try:
        calls = list(calls or [])
        run = _run_row(
            notes=notes, result=result, mode=mode, model=model, status=status,
            error_code=error_code, card_limit=card_limit, duration_s=duration_s, calls=calls,
        )
        run_id = run["run_id"]
        call_rows = [{"run_id": run_id, "seq": seq, **call} for seq, call in enumerate(calls, 1)]
        card_rows = [
            {
                "run_id": run_id,
                "position": position,
                "front": card.get("front") or "",
                "back": card.get("back") or "",
                "card_type": card.get("card_type") or "basic",
                "source_excerpt": card.get("source") or "",
            }
            for position, card in enumerate((result or {}).get("cards") or [], 1)
        ]
        conn = connect()
        with closing(conn), conn:  # one transaction: all three tables or none
            _insert_rows(conn, "runs", [run])
            _insert_rows(conn, "stage_usage", call_rows)
            _insert_rows(conn, "cards", card_rows)
        return run
    except Exception:
        log.exception("Could not save research run")
        return None


def summary(row) -> dict:
    """The few run numbers shown on the Run page. Missing values come back as None."""
    row = row or {}
    return {field: row.get(field) for field in SUMMARY_FIELDS}


def run_count() -> int:
    conn = connect()
    with closing(conn):
        return conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0]


def _cell(value):
    if isinstance(value, str) and len(value) > MAX_CELL_CHARS:
        return value[:MAX_CELL_CHARS] + " …"
    return value


def export_workbook() -> bytes:
    """Return an .xlsx file with one sheet per table."""
    workbook = Workbook()
    workbook.remove(workbook.active)
    conn = connect()
    with closing(conn):
        for name, query in EXPORT_QUERIES.items():
            cursor = conn.execute(query)
            sheet = workbook.create_sheet(name)
            sheet.append([column[0] for column in cursor.description])
            sheet.freeze_panes = "A2"
            for row_number, row in enumerate(cursor, start=2):
                for column_number, value in enumerate(row, start=1):
                    cell = sheet.cell(row=row_number, column=column_number, value=_cell(value))
                    if isinstance(value, str) and value.startswith(FORMULA_PREFIXES):
                        cell.data_type = "s"  # keep as plain text, never a formula
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def _csv_safe(value):
    if isinstance(value, str) and value.startswith(FORMULA_PREFIXES):
        return "'" + value
    return value


def export_csv(table: str) -> bytes:
    """Return one table as CSV bytes. Only names listed in EXPORT_QUERIES are accepted."""
    query = EXPORT_QUERIES[table]
    conn = connect()
    with closing(conn):
        cursor = conn.execute(query)
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow([column[0] for column in cursor.description])
        for row in cursor:
            writer.writerow([_csv_safe(value) for value in row])
    return buffer.getvalue().encode("utf-8-sig")
