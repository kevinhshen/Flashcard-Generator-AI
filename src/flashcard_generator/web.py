"""Flask routes for a local-only study application."""

from __future__ import annotations

import os
import threading
import webbrowser

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request

from .ai import generate_with_gemini, has_api_key
from .generator import generate_local
from .importers import MAX_FILE_BYTES, MAX_TEXT_CHARS, extract_notes


def create_app() -> Flask:
    load_dotenv()
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = MAX_FILE_BYTES + 65536

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

    @app.post("/api/generate")
    def generate():
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify(error="Send a JSON object containing notes."), 400
        notes = payload.get("notes")
        if not isinstance(notes, str) or not notes.strip():
            return jsonify(error="Paste some notes before generating cards."), 400
        notes = notes.strip()
        if len(notes) > MAX_TEXT_CHARS:
            return jsonify(error="Keep notes under 200,000 characters."), 413
        count = payload.get("max_cards", 30)
        if type(count) is not int or not 1 <= count <= 500:
            return jsonify(error="Maximum cards must be a whole number from 1 to 500."), 400
        use_ai = payload.get("use_ai", False)
        if type(use_ai) is not bool:
            return jsonify(error="use_ai must be true or false."), 400
        if len(notes.split()) < 3 or not any(c.isalpha() for c in notes):
            return jsonify(
                error="Not enough usable text. Enter a definition or complete question/answer."
            ), 422
        if use_ai and not has_api_key():
            return jsonify(
                error="Gemini is not configured. Add GEMINI_API_KEY and restart, or select Local rules."
            ), 400
        try:
            cards = generate_with_gemini(notes, count) if use_ai else generate_local(notes, count)
        except Exception:
            # Never expose exception strings: SDK errors can include request data.
            return jsonify(
                error=(
                    "Gemini failed or timed out. Check your key, quota, network, and GEMINI_MODEL. "
                    "No local fallback was used. Select Local rules explicitly if you want to retry offline."
                    if use_ai
                    else "Local generation failed. Try a smaller section of notes."
                )
            ), 502 if use_ai else 500
        return jsonify(
            cards=[card.to_dict() for card in cards],
            mode="ai" if use_ai else "local",
            model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash") if use_ai else None,
        )

    return app


def run(open_browser: bool = True) -> None:
    app = create_app()  # Load .env before reading HOST and PORT.
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
