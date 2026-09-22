import pytest

from flashcard_generator.web import create_app


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "")
    app = create_app()
    app.config.update(TESTING=True)
    return app.test_client()


def test_home_page_loads(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"Turn your notes into" not in response.data
    assert b"Recall flashcards" in response.data


def test_status_reports_ai_unavailable(client):
    assert client.get("/api/status").get_json() == {"ok": True, "ai_available": False}


def test_generate_rejects_empty_notes(client):
    response = client.post("/api/generate", json={"notes": ""})
    assert response.status_code == 400
    assert "Paste" in response.get_json()["error"]


def test_local_generation_api(client):
    response = client.post(
        "/api/generate",
        json={"notes": "Velocity: The rate of change of displacement.", "max_cards": 10},
    )
    payload = response.get_json()
    assert response.status_code == 200
    assert payload["mode"] == "local"
    assert payload["cards"][0]["front"] == "What is Velocity?"


def test_missing_ai_key_never_silently_falls_back(client):
    response = client.post(
        "/api/generate",
        json={"notes": "Velocity: The rate of change of displacement.", "use_ai": True},
    )
    payload = response.get_json()
    assert response.status_code == 400
    assert "Gemini is not configured" in payload["error"]
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
    response = client.post("/api/generate", json={"notes": "Force: A push or pull."})
    assert response.status_code == 200
    assert response.get_json()["cards"]


def test_local_mode_never_calls_ai(client, monkeypatch):
    def unexpected(*args):
        raise AssertionError("AI must not be called")

    monkeypatch.setattr("flashcard_generator.web.generate_with_gemini", unexpected)
    response = client.post("/api/generate", json={"notes": "Force: A push or pull."})
    assert response.status_code == 200
    assert response.get_json()["mode"] == "local"


def test_ai_error_does_not_leak_or_fallback(client, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    def failing(*args):
        raise RuntimeError("secret-key-value")

    monkeypatch.setattr("flashcard_generator.web.generate_with_gemini", failing)
    response = client.post("/api/generate", json={"notes": "Force: A push or pull.", "use_ai": True})
    assert response.status_code == 502
    assert b"secret-key-value" not in response.data
    assert "cards" not in response.get_json()
