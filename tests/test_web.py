import pytest

from flashcard_generator.web import create_app


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setattr(
        "flashcard_generator.web.model_status",
        lambda: {
            "available": True,
            "model": "mrm8488/t5-base-finetuned-question-generation-ap",
            "model_cached": False,
            "model_loaded": False,
            "automatic_download": True,
        },
    )
    app = create_app()
    app.config.update(TESTING=True)
    return app.test_client()


def test_home_page_loads(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"Turn your notes into" not in response.data
    assert b"Recall flashcards" in response.data


def test_status_reports_automatic_model_readiness(client):
    assert client.get("/api/status").get_json() == {
        "ok": True,
        "ai": {
            "available": True,
            "model": "mrm8488/t5-base-finetuned-question-generation-ap",
            "model_cached": False,
            "model_loaded": False,
            "automatic_download": True,
        },
    }


def test_generate_rejects_empty_notes(client):
    response = client.post("/api/generate", json={"notes": ""})
    assert response.status_code == 400
    assert "Paste" in response.get_json()["error"]


def test_local_generation_api(client):
    response = client.post(
        "/api/generate",
        json={"notes": "Velocity: The rate of change of displacement.", "max_cards": 10, "use_ai": False},
    )
    payload = response.get_json()
    assert response.status_code == 200
    assert payload["mode"] == "local"
    assert payload["cards"][0]["front"] == "What is Velocity?"


def test_model_setup_failure_never_silently_falls_back(client, monkeypatch):
    def failing(*_args, **_kwargs):
        from flashcard_generator.ai import AIError

        raise AIError("model_setup_failed", "Could not download or load the Hugging Face model.")

    monkeypatch.setattr("flashcard_generator.web.generate_deck", failing)
    response = client.post(
        "/api/generate",
        json={"notes": "Velocity: The rate of change of displacement.", "use_ai": True},
    )
    payload = response.get_json()
    assert response.status_code == 502
    assert "Could not download or load" in payload["error"]
    assert "cards" not in payload


@pytest.mark.parametrize(
    "payload",
    [
        [],
        {"notes": None},
        {"notes": "Valid study notes", "max_cards": 1.5},
        {"notes": "Valid study notes", "max_cards": 501},
        {"notes": "Valid study notes", "use_ai": "false"},
    ],
)
def test_bad_payload_is_json_error(client, payload):
    response = client.post("/api/generate", json=payload)
    assert response.status_code == 400
    assert response.get_json()["error"]


def test_random_input_then_valid_input(client):
    assert client.post("/api/generate", json={"notes": "asdfasdf"}).status_code == 422
    response = client.post("/api/generate", json={"notes": "Force: A push or pull.", "use_ai": False})
    assert response.status_code == 200
    assert response.get_json()["cards"]


def test_local_mode_never_calls_ai(client, monkeypatch):
    def unexpected(*args, **kwargs):
        raise AssertionError("AI must not be called")

    monkeypatch.setattr("flashcard_generator.web.generate_deck", unexpected)
    response = client.post("/api/generate", json={"notes": "Force: A push or pull.", "use_ai": False})
    assert response.status_code == 200
    assert response.get_json()["mode"] == "local"


def test_ai_error_does_not_leak_or_fallback(client, monkeypatch):
    def failing(*args, **kwargs):
        raise RuntimeError("secret-key-value")

    monkeypatch.setattr("flashcard_generator.web.generate_deck", failing)
    response = client.post("/api/generate", json={"notes": "Force: A push or pull.", "use_ai": True})
    assert response.status_code == 502
    assert b"secret-key-value" not in response.data
    assert "cards" not in response.get_json()


def test_local_ai_is_default_and_needs_no_api_key(client):
    page = client.get("/").data
    assert b'value="ai" selected' in page
    assert b"T5 question model" in page
    assert b"GEMINI_API_KEY" not in page


def test_ai_job_api_and_auto_card_limit(client, monkeypatch):
    received = []

    def generate(notes, count, **kwargs):
        received.append((notes, count))
        return {"cards": [], "mode": "ai", "coverage": {"identified_facts": 0}}

    monkeypatch.setattr("flashcard_generator.web.generate_deck", generate)
    response = client.post("/api/jobs", json={"notes": "No usable study content"})
    assert response.status_code == 202
    key = response.get_json()["job_id"]
    client.application.extensions["generation_jobs"].executor.shutdown(wait=True)
    result = client.get("/api/jobs/" + key).get_json()
    assert result["status"] == "completed"
    assert result["result"]["mode"] == "ai"
    assert received == [("No usable study content", None)]
    assert client.get("/api/jobs/missing").status_code == 404
    assert client.post("/api/jobs/missing/cancel").status_code == 404
