"""Local Flask interface for reviewing and exporting flashcards in a browser."""

from __future__ import annotations

from threading import Lock
from typing import Any

from flask import Flask, jsonify, render_template, request

from .flan_t5 import DEFAULT_MODEL_ID, FlanT5Generator, FlanT5UnavailableError
from .generation import EngineName, PolishMode, run_generation
from .models import Flashcard
from .parser import segment_chunks
from .validation import validate_and_deduplicate


MAX_NOTES_CHARS = 100_000
MAX_CARD_FIELD_CHARS = 2_000
VALID_ENGINES = {"rules", "hybrid", "flan"}
VALID_POLISH_MODES = {"off", "auto", "all"}
VALID_DEVICES = {"auto", "cpu", "cuda", "mps"}


def create_app(test_config: dict[str, Any] | None = None) -> Flask:
    """Create a local-only web app without changing the CLI behavior."""
    app = Flask(__name__)
    app.config.from_mapping(MAX_NOTES_CHARS=MAX_NOTES_CHARS)
    if test_config:
        app.config.update(test_config)

    app.extensions["flan_models"] = {}
    app.extensions["generation_lock"] = Lock()

    @app.get("/")
    def index() -> str:
        return render_template("index.html", default_model=DEFAULT_MODEL_ID)

    @app.post("/api/generate")
    def generate() -> tuple[Any, int] | Any:
        try:
            payload = _json_object(request)
            notes = _required_text(payload, "notes", app.config["MAX_NOTES_CHARS"])
            engine = _choice(payload, "engine", VALID_ENGINES, "hybrid")
            polish = _choice(payload, "polish", VALID_POLISH_MODES, "auto")
            device = _choice(payload, "device", VALID_DEVICES, "auto")
            offline = bool(payload.get("offline", False))
            model_id = _optional_text(payload.get("modelId"), DEFAULT_MODEL_ID, 200)
        except ValueError as error:
            return jsonify(error=str(error)), 400

        try:
            with app.extensions["generation_lock"]:
                report = _run_notes(app, notes, engine, polish, device, offline, model_id)
        except FlanT5UnavailableError as error:
            return jsonify(error=str(error), requires_ai=True), 422

        cards, rejected = validate_and_deduplicate(report.cards)
        return jsonify(
            cards=[_card_payload(card, index) for index, card in enumerate(cards)],
            summary={
                "accepted": len(cards),
                "rejected": len(rejected),
                "skipped": len(report.skipped_sources),
            },
        )

    @app.post("/api/regenerate")
    def regenerate() -> tuple[Any, int] | Any:
        try:
            payload = _json_object(request)
            card = _card_from_payload(payload.get("card"))
            if card.generator != "flan":
                raise ValueError("Only AI-generated or AI-improved cards can be regenerated")
            device = _choice(payload, "device", VALID_DEVICES, "auto")
            offline = bool(payload.get("offline", False))
            model_id = _optional_text(payload.get("modelId"), DEFAULT_MODEL_ID, 200)
        except ValueError as error:
            return jsonify(error=str(error)), 400

        try:
            with app.extensions["generation_lock"]:
                model = _model_for(app, model_id, device, offline)
                replacement, reason = model.regenerate_card(card)
        except FlanT5UnavailableError as error:
            return jsonify(error=str(error), requires_ai=True), 422

        if replacement is None:
            return jsonify(error=reason or "The model did not return a replacement"), 422
        accepted, rejected = validate_and_deduplicate([replacement])
        if rejected:
            return jsonify(error=rejected[0][1]), 422
        return jsonify(card=_card_payload(accepted[0], payload.get("card", {}).get("id", "regenerated")))

    return app


def _run_notes(
    app: Flask,
    notes: str,
    engine: str,
    polish: str,
    device: str,
    offline: bool,
    model_id: str,
):
    chunks = segment_chunks(notes)
    if engine == "rules":
        return run_generation(chunks, "rules")
    model = _model_for(app, model_id, device, offline)
    return run_generation(chunks, engine, model, polish=polish)


def _model_for(app: Flask, model_id: str, device: str, offline: bool) -> FlanT5Generator:
    key = (model_id, device, offline)
    models: dict[tuple[str, str, bool], FlanT5Generator] = app.extensions["flan_models"]
    if key not in models:
        models[key] = FlanT5Generator(model_id=model_id, device=device, offline=offline)
    return models[key]


def _json_object(request: Any) -> dict[str, Any]:
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        raise ValueError("Send a JSON object")
    return payload


def _required_text(payload: dict[str, Any], key: str, limit: int) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} is required")
    if len(value) > limit:
        raise ValueError(f"{key} is limited to {limit:,} characters")
    return value.strip()


def _optional_text(value: Any, default: str, limit: int) -> str:
    if value is None or value == "":
        return default
    if not isinstance(value, str) or len(value) > limit:
        raise ValueError("modelId is invalid")
    return value


def _choice(payload: dict[str, Any], key: str, allowed: set[str], default: str) -> str:
    value = payload.get(key, default)
    if value not in allowed:
        raise ValueError(f"{key} must be one of: {', '.join(sorted(allowed))}")
    return value


def _card_from_payload(value: Any) -> Flashcard:
    if not isinstance(value, dict):
        raise ValueError("card is required")
    front = _required_text(value, "front", MAX_CARD_FIELD_CHARS)
    back = _required_text(value, "back", MAX_CARD_FIELD_CHARS)
    source_text = _required_text(value, "sourceText", MAX_NOTES_CHARS)
    source_id = _required_text(value, "sourceId", 500)
    generator = value.get("generator")
    kind = value.get("kind", "basic")
    if generator not in {"rule", "flan"} or kind not in {"basic", "cloze"}:
        raise ValueError("card metadata is invalid")
    return Flashcard(front, back, source_text, source_id, generator, kind)


def _card_payload(card: Flashcard, card_id: int | str) -> dict[str, str]:
    return {
        "id": str(card_id),
        "front": card.front,
        "back": card.back,
        "sourceText": card.source_text,
        "sourceId": card.source_id,
        "generator": card.generator,
        "kind": card.kind,
    }
