"""Local web application with progress-aware, coverage-first AI generation."""

from __future__ import annotations

import os
import threading
import webbrowser

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request

from .ai import generate_deck, has_api_key, safe_ai_error
from .generator import generate_local
from .importers import MAX_FILE_BYTES, MAX_TEXT_CHARS, extract_notes
from .jobs import JobStore


def create_app() -> Flask:
    load_dotenv()
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = MAX_FILE_BYTES + 65536
    jobs = JobStore()
    app.extensions["generation_jobs"] = jobs

    @app.errorhandler(413)
    def too_large(_error):
        return jsonify(error="File/request is too large. Upload at most 10 MB."), 413

    @app.get("/")
    def index():
        return render_template("index.html", ai_available=has_api_key())

    @app.get("/api/status")
    def status():
        return jsonify({"ok": True, "ai_available": has_api_key()})

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
        use_ai = payload.get("use_ai", True)
        if type(use_ai) is not bool:
            return None, (jsonify(error="use_ai must be true or false."), 400)
        if len(notes.split()) < 3 or not any(c.isalpha() for c in notes):
            return None, (
                jsonify(error="Not enough usable text. Enter a definition or complete question/answer."),
                422,
            )
        if use_ai and not has_api_key():
            return None, (
                jsonify(
                    error="Gemini is not configured. Add GEMINI_API_KEY to .env and restart, "
                    "or select Local rules.",
                    error_code="missing_key",
                ),
                400,
            )
        return (notes, count, use_ai), None

    def perform(values, progress=lambda _m: None, cancelled=lambda: False):
        notes, count, use_ai = values
        if use_ai:
            return generate_deck(notes, count, progress=progress, cancelled=cancelled)
        return {
            "cards": [card.to_dict() for card in generate_local(notes, count or 500)],
            "mode": "local",
            "model": None,
            "warning": "Local rules only: no AI review or coverage audit. Some material may be skipped.",
        }

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
