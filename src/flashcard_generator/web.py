"""Flask application and local browser launcher."""

from __future__ import annotations

import os
import threading
import webbrowser

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request

from .ai import generate_with_gemini, has_api_key
from .generator import generate_local


def create_app() -> Flask:
    load_dotenv()
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024

    @app.get("/")
    def index():
        return render_template("index.html", ai_available=has_api_key())

    @app.get("/api/status")
    def status():
        return jsonify({"ok": True, "ai_available": has_api_key()})

    @app.post("/api/generate")
    def generate():
        payload = request.get_json(silent=True) or {}
        notes = str(payload.get("notes", "")).strip()
        if not notes:
            return jsonify({"error": "Paste some notes before generating cards."}), 400
        if len(notes) > 200_000:
            return jsonify({"error": "Notes are too long. Keep input under 200,000 characters."}), 413

        try:
            max_cards = max(1, min(int(payload.get("max_cards", 20)), 100))
        except (TypeError, ValueError):
            return jsonify({"error": "Card count must be a whole number."}), 400

        use_ai = bool(payload.get("use_ai", False))
        try:
            cards = generate_with_gemini(notes, max_cards) if use_ai else generate_local(notes, max_cards)
        except Exception as exc:
            if use_ai:
                app.logger.warning("AI generation failed; using local fallback: %s", exc)
                fallback = generate_local(notes, max_cards)
                return jsonify({
                    "cards": [card.to_dict() for card in fallback],
                    "mode": "local-fallback",
                    "warning": (
                        "AI generation was unavailable, so local generation was used. "
                        "Check the API key, network connection, model name, and quota."
                    ),
                })
            app.logger.exception("Local flashcard generation failed")
            return jsonify({"error": "Card generation failed unexpectedly."}), 500

        return jsonify({
            "cards": [card.to_dict() for card in cards],
            "mode": "ai" if use_ai else "local",
        })

    return app


def run(open_browser: bool = True) -> None:
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "5000"))
    if open_browser:
        browser_host = "127.0.0.1" if host in {"0.0.0.0", "::"} else host
        threading.Timer(0.8, lambda: webbrowser.open(f"http://{browser_host}:{port}")).start()
    create_app().run(host=host, port=port, debug=False, use_reloader=False)


if __name__ == "__main__":
    run()
