"""Local web application with progress-aware, coverage-first AI generation."""

from __future__ import annotations

import io
import os
import sqlite3
import threading
import time
import webbrowser
from datetime import datetime
from pathlib import Path

import markdown
from dotenv import load_dotenv, set_key
from flask import Flask, jsonify, render_template, request, send_file


from . import storage
from .ai import AVAILABLE_MODELS, MODEL, Cancelled, generate_deck, has_api_key, safe_ai_error
from .generator import generate_local
from .importers import MAX_FILE_BYTES, MAX_TEXT_CHARS, extract_notes
from .jobs import JobStore

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def create_app(*, env_path: Path | None = None) -> Flask:
    # Read and write the same file, independent of the launch directory.
    env_path = Path(env_path) if env_path is not None else Path(__file__).resolve().parents[2] / ".env"
    load_dotenv(env_path)
    app = Flask(__name__)
    key_lock = threading.Lock()
    app.config["MAX_CONTENT_LENGTH"] = MAX_FILE_BYTES + 65536
    jobs = JobStore()
    app.extensions["generation_jobs"] = jobs

    @app.errorhandler(413)
    def too_large(_error):
        return jsonify(error="File/request is too large. Upload at most 10 MB."), 413

    @app.get("/")
    def index():
        return render_template(
            "index.html", ai_available=has_api_key(), models=AVAILABLE_MODELS, default_model=MODEL
        )

    @app.get("/about")
    def about():
        readme = Path(__file__).resolve().parents[2] / "README.md"
        html = markdown.markdown(
            readme.read_text(encoding="utf-8") if readme.exists() else "README.md not found.",
            extensions=["fenced_code", "tables", "sane_lists"],
        )
        return render_template("about.html", readme_html=html)

    @app.get("/compare")
    def compare():
        return render_template("compare.html")

    @app.get("/export")
    def export():
        try:
            runs, database = storage.run_count(), str(storage.db_path())
        except (OSError, sqlite3.Error):
            runs, database = None, None
        return render_template("export.html", runs=runs, database=database)

    @app.get("/api/export.xlsx")
    def export_xlsx():
        try:
            data = storage.export_workbook()
        except (OSError, sqlite3.Error):
            return jsonify(error="Could not read the research database."), 500
        return send_file(
            io.BytesIO(data),
            mimetype=XLSX_MIME,
            as_attachment=True,
            download_name=f"recall-research-{datetime.now():%Y-%m-%d}.xlsx",
        )

    @app.get("/api/export.csv")
    def export_csv_file():
        table = request.args.get("table", "runs")
        if table not in storage.EXPORT_QUERIES:
            return jsonify(error="Unknown table."), 404
        try:
            data = storage.export_csv(table)
        except (OSError, sqlite3.Error):
            return jsonify(error="Could not read the research database."), 500
        return send_file(
            io.BytesIO(data),
            mimetype="text/csv",
            as_attachment=True,
            download_name=f"recall-{table}-{datetime.now():%Y-%m-%d}.csv",
        )

    @app.get("/api/status")
    def status():
        return jsonify({"ok": True, "ai_available": has_api_key()})

    @app.post("/api/settings/api-key")
    def save_api_key():
        # JSON and same-origin requests prevent cross-site form submissions to
        # this local server. Never put credentials in a URL or response.
        origin = request.headers.get("Origin")
        if (origin and origin != request.host_url.rstrip("/")) or request.headers.get(
            "Sec-Fetch-Site"
        ) == "cross-site":
            return jsonify(error="Save the key from this app's page."), 403
        if not request.is_json:
            return jsonify(error="Send the API key as JSON."), 415
        payload = request.get_json(silent=True)
        key = payload.get("api_key") if isinstance(payload, dict) else None
        # Treat API keys as opaque tokens; formats can include punctuation and
        # longer encoded credentials. Only reject unsafe .env syntax/whitespace.
        if not isinstance(key, str) or not key.strip() or len(key) > 4096:
            return jsonify(error="Paste a valid Gemini API key."), 400
        key = key.strip()
        if not all(
            character.isascii() and (character.isalnum() or character in "_.~+/=-")
            for character in key
        ):
            return jsonify(error="Paste only the Gemini API key, without quotes or spaces."), 400
        with key_lock:
            try:
                if env_path.exists():
                    env_path.chmod(0o600)
                # python-dotenv preserves other settings and replaces the file
                # atomically; a new file is private to the current user.
                set_key(env_path, "GEMINI_API_KEY", key)
            except (OSError, UnicodeError):
                return jsonify(
                    error="Could not save .env. Check the project folder's write permissions."
                ), 500
            # Only enable generation after the key is safely persisted.
            os.environ["GEMINI_API_KEY"] = key
        return jsonify(ok=True, ai_available=True)

    @app.post("/api/import")
    def import_file():
        uploaded = request.files.get("file")
        if uploaded is None:
            return jsonify(error="Choose a TXT, Markdown, or PDF file."), 400
        try:
            return jsonify(extract_notes(uploaded.filename or "", uploaded.read(MAX_FILE_BYTES + 1)))
        except ValueError as exc:
            return jsonify(error=str(exc)), 400

    def validate_payload():
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return None, (jsonify(error="Send a JSON object containing notes."), 400)
        notes = payload.get("notes")
        if not isinstance(notes, str) or not notes.strip():
            return None, (jsonify(error="Paste some notes before generating cards."), 400)
        notes = notes.strip()
        if len(notes) > MAX_TEXT_CHARS:
            return None, (jsonify(error="Keep notes under 200,000 characters."), 413)
        count = payload.get("max_cards")
        if count is not None and (type(count) is not int or not 1 <= count <= 500):
            return None, (jsonify(error="Maximum cards must be blank or a whole number from 1 to 500."), 400)
        model = payload.get("model")
        if model is not None and model not in AVAILABLE_MODELS:
            return None, (jsonify(error="Unknown model. Choose one from the list."), 400)
        use_ai = payload.get("use_ai", True)
        if type(use_ai) is not bool:
            return None, (jsonify(error="use_ai must be true or false."), 400)
        label = payload.get("notes_label")
        if label is not None and (not isinstance(label, str) or len(label) > 255):
            return None, (jsonify(error="notes_label must be text of at most 255 characters."), 400)
        if len(notes.split()) < 3 or not any(c.isalpha() for c in notes):
            return None, (
                jsonify(error="Not enough usable text. Enter a definition or complete question/answer."),
                422,
            )
        if use_ai and not has_api_key():
            return None, (
                jsonify(
                    error="Gemini is not configured. Save your Gemini API key in the setup field, "
                    "or select Local rules.",
                    error_code="missing_key",
                ),
                400,
            )
        return (notes, count, use_ai, model, (label or "").strip() or None), None

    def generate_once(values, progress, cancelled):
        notes, count, use_ai, model, _label = values
        if use_ai:
            options = {"model": model} if model else {}
            return generate_deck(notes, count, progress=progress, cancelled=cancelled, **options)
        return {
            "cards": [card.to_dict() for card in generate_local(notes, count or 500)],
            "mode": "local",
            "model": None,
            "warning": "Local rules only: no AI review or coverage audit. Some material may be skipped.",
        }

    # Main action. Every run is saved (completed, failed or cancelled) before its result is returned.
    # A storage problem never changes the result: save_run() logs it and returns None.
    def perform(values, progress=lambda _m: None, cancelled=lambda: False):
        notes, count, use_ai, model, label = values
        started = time.perf_counter()
        requested = (model or os.getenv("GEMINI_MODEL", MODEL)) if use_ai else None
        result = None
        try:
            result = generate_once(values, progress, cancelled)
            if cancelled():  # cancelled during the final request: the job will report cancelled too
                raise Cancelled()
        except Exception as exc:
            safe = safe_ai_error(exc)
            storage.save_run(
                notes=notes, result=None, mode="ai" if use_ai else "local", model=requested,
                status="cancelled" if safe.code == "cancelled" else "failed", error_code=safe.code,
                card_limit=count, duration_s=time.perf_counter() - started,
                calls=getattr(safe, "calls", None) or (result or {}).get("calls", []),
                stats=getattr(safe, "stats", None) or (result or {}).get("stats"),
                notes_label=label,
            )
            raise
        # Research-only data: saved below, but not sent to the page.
        calls = result.pop("calls", [])
        stats = result.pop("stats", None)
        facts = result.pop("facts", [])
        row = storage.save_run(
            notes=notes, result=result, mode=result.get("mode"), model=requested, status="completed",
            error_code=None, card_limit=count, duration_s=time.perf_counter() - started, calls=calls,
            stats=stats, facts=facts, notes_label=label,
        )
        result["run_id"] = row["run_id"] if row else None
        result["metrics"] = storage.summary(row)
        return result

    @app.post("/api/generate")
    def generate():
        values, error = validate_payload()
        if error:
            return error
        try:
            return jsonify(perform(values))
        except Exception as exc:
            safe = safe_ai_error(exc)
            return jsonify(error=str(safe), error_code=safe.code), 502

    @app.post("/api/jobs")
    def start_job():
        values, error = validate_payload()
        if error:
            return error
        try:
            key = jobs.submit(lambda progress, cancelled: perform(values, progress, cancelled))
        except ValueError as exc:
            return jsonify(error=str(exc)), 409
        return jsonify(job_id=key), 202

    @app.get("/api/jobs/<key>")
    def job_status(key):
        snapshot = jobs.get(key)
        if snapshot is None:
            return jsonify(error="Generation session expired or the server restarted. Generate again."), 404
        return jsonify(snapshot)

    @app.post("/api/jobs/<key>/cancel")
    def cancel_job(key):
        if not jobs.cancel(key):
            return jsonify(error="Generation session not found."), 404
        return jsonify(ok=True)

    return app


def run(open_browser: bool = True) -> None:
    app = create_app()
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "5000"))
    if open_browser:
        browser_host = "127.0.0.1" if host in {"0.0.0.0", "::"} else host
        timer = threading.Timer(0.8, lambda: webbrowser.open(f"http://{browser_host}:{port}"))
        timer.daemon = True
        timer.start()
    app.run(host=host, port=port, debug=False, use_reloader=False)


if __name__ == "__main__":
    run()
