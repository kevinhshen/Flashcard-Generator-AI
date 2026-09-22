import pytest

from flashcard_generator.web import create_app


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    app = create_app()
    app.config.update(TESTING=True)
    return app.test_client()


def test_home_page_loads(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"Turn your notes into" in response.data


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


def test_ai_failure_falls_back_to_local(client):
    response = client.post(
        "/api/generate",
        json={"notes": "Velocity: The rate of change of displacement.", "use_ai": True},
    )
    payload = response.get_json()
    assert response.status_code == 200
    assert payload["mode"] == "local-fallback"
    assert payload["cards"]
