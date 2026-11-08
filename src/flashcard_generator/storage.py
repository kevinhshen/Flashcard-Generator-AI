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
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE

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
CREATE TABLE IF NOT EXISTS facts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL REFERENCES runs(run_id),
    fact_id TEXT, section INTEGER, text TEXT, source_quote TEXT, outcome TEXT
);
"""

# Columns added after the first release. connect() adds any that a database is missing, so existing
# databases keep working and their old rows stay untouched (the new columns are simply empty there).
# To record something new, add it here rather than to SCHEMA.
ADDED_COLUMNS = {
    "runs": {
        "notes_words": "INTEGER",
        "notes_label": "TEXT",
        "chunk_size": "INTEGER",
        "batch_size": "INTEGER",
        "temperature": "REAL",
        "max_output_tokens": "INTEGER",
        "prompt_sha256": "TEXT",
        "git_dirty": "INTEGER",
        "model_version": "TEXT",
        "thinking_tokens": "INTEGER",
        "cached_tokens": "INTEGER",
        "api_seconds": "REAL",
        "retries": "INTEGER",
        "retry_wait_s": "REAL",
        "facts_inventoried": "INTEGER",
        "facts_added_by_audit": "INTEGER",
        "facts_removed_by_audit": "INTEGER",
        "cards_drafted": "INTEGER",
        "cards_reviewed": "INTEGER",
        "cards_failed_checks": "INTEGER",
        "repair_requests": "INTEGER",
        "facts_repaired": "INTEGER",
        "conflicting_questions": "INTEGER",
        "exclusions": "INTEGER",
    },
    "stage_usage": {
        "thinking_tokens": "INTEGER",
        "cached_tokens": "INTEGER",
        "input_chars": "INTEGER",
        "items_returned": "INTEGER",
        "finish_reason": "TEXT",
        "error_code": "TEXT",
    },
    "cards": {"fact_ids": "TEXT", "front_chars": "INTEGER", "back_chars": "INTEGER"},
}
# Values generate_deck() reports in result["stats"]. Local-rules runs have none, so these stay empty.
STAT_FIELDS = (
    "chunk_size", "batch_size", "temperature", "max_output_tokens", "prompt_sha256", "model_version",
    "retries", "retry_wait_s", "facts_inventoried", "facts_added_by_audit", "facts_removed_by_audit",
    "cards_drafted", "cards_reviewed", "cards_failed_checks", "repair_requests", "facts_repaired",
    "conflicting_questions", "exclusions",
)
CALL_FIELDS = (
    "stage", "status", "seconds", "input_tokens", "output_tokens", "thinking_tokens", "cached_tokens",
    "total_tokens", "input_chars", "items_returned", "finish_reason", "error_code",
)

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
    "facts": "SELECT * FROM facts ORDER BY run_id, id",
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
    _add_missing_columns(conn)
    return conn


def _add_missing_columns(conn):
    for table, columns in ADDED_COLUMNS.items():
        existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
        for name, kind in columns.items():
            if name in existing:
                continue
            try:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {kind}")
            except sqlite3.OperationalError as exc:
                # Another connection (the page and a background job can overlap) added it first.
                if "duplicate column" not in str(exc):
                    raise


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


@lru_cache(maxsize=1)
def git_dirty() -> int | None:
    """1 if the code had uncommitted changes, 0 if not, None if git could not tell."""
    try:
        out = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True, text=True, timeout=5,
            cwd=Path(__file__).resolve().parent,
        )
        return (1 if out.stdout.strip() else 0) if out.returncode == 0 else None
    except Exception:
        return None


def _pct(part, whole):
    return round(100 * part / whole, 1) if whole else None


def _run_row(
    *, notes, result, mode, model, status, error_code, card_limit, duration_s, calls, stats, notes_label
):
    result = result or {}
    coverage = result.get("coverage") or {}
    cards = result.get("cards") or []
    token_keys = ("input_tokens", "output_tokens", "thinking_tokens", "cached_tokens", "total_tokens")
    totals = {key: sum(call.get(key) or 0 for call in calls) for key in token_keys}
    identified = coverage.get("identified_facts")
    covered = coverage.get("covered_facts")
    rejected = len(coverage.get("rejected_facts") or []) if coverage else None
    return {
        "run_id": uuid.uuid4().hex, # random unique ID
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "mode": mode,
        "model": result.get("model") or model,
        "status": status,
        "error_code": error_code,
        "notes_sha256": hashlib.sha256(notes.encode("utf-8")).hexdigest(),
        "notes_chars": len(notes),
        "notes_words": len(notes.split()),
        "notes_label": notes_label,
        "card_limit": card_limit,
        "duration_s": round(duration_s, 3),
        **totals,
        "api_seconds": round(sum(call.get("seconds") or 0 for call in calls), 3) if calls else None,
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
        "git_dirty": git_dirty(),
        **{field: stats.get(field) for field in STAT_FIELDS},
    }


def _insert_rows(conn, table, rows):
    if not rows:
        return
    columns = list(rows[0])
    sql = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({', '.join('?' for _ in columns)})"
    conn.executemany(sql, [tuple(row[column] for column in columns) for row in rows])


def save_run(
    *, notes, result, mode, model, status, error_code, card_limit, duration_s,
    calls=(), stats=None, facts=(), notes_label=None,
):
    """Save one run, its AI requests, its cards and its facts.

    Never raises: a storage problem must not break card generation. Returns the saved
    run row (a dict), or None if nothing was saved.
    """
    try:
        calls = list(calls or [])
        run = _run_row(
            notes=notes, result=result, mode=mode, model=model, status=status,
            error_code=error_code, card_limit=card_limit, duration_s=duration_s, calls=calls,
            stats=stats or {}, notes_label=notes_label,
        )
        run_id = run["run_id"]
        call_rows = [
            {"run_id": run_id, "seq": seq, **{field: call.get(field) for field in CALL_FIELDS}}
            for seq, call in enumerate(calls, 1)
        ]
        card_rows = [
            {
                "run_id": run_id,
                "position": position,
                "front": card.get("front") or "",
                "back": card.get("back") or "",
                "card_type": card.get("card_type") or "basic",
                "source_excerpt": card.get("source") or "",
                "fact_ids": ",".join(card.get("fact_ids") or []) or None,
                "front_chars": len(card.get("front") or ""),
                "back_chars": len(card.get("back") or ""),
            }
            for position, card in enumerate((result or {}).get("cards") or [], 1)
        ]
        fact_rows = [
            {
                "run_id": run_id,
                "fact_id": fact.get("fact_id"),
                "section": fact.get("section"),
                "text": fact.get("text"),
                "source_quote": fact.get("source_quote"),
                "outcome": fact.get("outcome"),
            }
            for fact in facts or []
        ]
        conn = connect()
        with closing(conn), conn:  # one transaction: every table or none
            _insert_rows(conn, "runs", [run])
            _insert_rows(conn, "stage_usage", call_rows)
            _insert_rows(conn, "cards", card_rows)
            _insert_rows(conn, "facts", fact_rows)
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
    if not isinstance(value, str):
        return value
    # Text from PDFs can hold control characters, which openpyxl refuses to write.
    value = ILLEGAL_CHARACTERS_RE.sub("", value)
    return value[:MAX_CELL_CHARS] + " …" if len(value) > MAX_CELL_CHARS else value


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
