import os
import stat
from contextlib import closing
from io import BytesIO

import pytest
from dotenv import dotenv_values
from openpyxl import load_workbook

from flashcard_generator import storage
from flashcard_generator.ai import AIError
from flashcard_generator.web import create_app


@pytest.fixture()
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("GEMINI_API_KEY", "")
    app = create_app(env_path=tmp_path / ".env")
    app.config.update(TESTING=True)
    return app.test_client()


def test_home_page_loads(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"Turn your notes into" not in response.data
    assert b"Recall flashcards" in response.data


def test_status_reports_ai_unavailable(client):
    assert client.get("/api/status").get_json() == {"ok": True, "ai_available": False}


def test_save_key_creates_private_env_and_enables_generation(client, tmp_path, monkeypatch, caplog):
    key = "test-gemini-secret"
    path = tmp_path / ".env"
    assert not path.exists()
    response = client.post("/api/settings/api-key", json={"api_key": f"  {key}  "})
    assert response.status_code == 200
    assert response.get_json() == {"ok": True, "ai_available": True}
    assert dotenv_values(path)["GEMINI_API_KEY"] == key
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert client.get("/api/status").get_json()["ai_available"] is True
    assert key not in client.get("/").text + response.text + caplog.text
    assert 'class="api-key-setup" hidden' in client.get("/").text

    def generate(*args, **kwargs):
        assert os.environ["GEMINI_API_KEY"] == key
        return {"cards": [], "mode": "ai"}

    monkeypatch.setattr("flashcard_generator.web.generate_deck", generate)
    response = client.post("/api/jobs", json={"notes": "Force is a push or pull."})
    assert response.status_code == 202
    client.application.extensions["generation_jobs"].executor.shutdown(wait=True)
    assert client.get("/api/jobs/" + response.json["job_id"]).json["status"] == "completed"

    # A fresh app reads the saved file without relying on the process environment.
    monkeypatch.delenv("GEMINI_API_KEY")
    reloaded = create_app(env_path=path).test_client()
    assert reloaded.get("/api/status").json["ai_available"] is True


def test_save_key_preserves_other_env_settings(client, tmp_path):
    path = tmp_path / ".env"
    path.write_text("# My settings\nPORT=5050\nGEMINI_API_KEY='old-key'\nGEMINI_MODEL=test-model\n")
    response = client.post("/api/settings/api-key", json={"api_key": "replacement-key"})
    assert response.status_code == 200
    assert dotenv_values(path) == {
        "PORT": "5050", "GEMINI_API_KEY": "replacement-key", "GEMINI_MODEL": "test-model"
    }
    assert "# My settings" in path.read_text()


@pytest.mark.parametrize("key", [None, 123, "", "   ", "x" * 4097, "key\nPORT=9", "a b", "${SECRET}"])
def test_invalid_key_does_not_write_or_enable(client, tmp_path, key):
    response = client.post("/api/settings/api-key", json={"api_key": key})
    assert response.status_code == 400
    assert not (tmp_path / ".env").exists()
    assert client.get("/api/status").json["ai_available"] is False


@pytest.mark.parametrize("key", ["AQ.test-key_with.punctuation~+/=", "AQ." + "a" * 1024])
def test_encoded_key_formats_round_trip_and_activate(client, tmp_path, monkeypatch, key):
    response = client.post("/api/settings/api-key", json={"api_key": key})
    assert response.status_code == 200
    assert os.environ["GEMINI_API_KEY"] == key
    assert dotenv_values(tmp_path / ".env")["GEMINI_API_KEY"] == key
    assert key not in response.text + client.get("/").text
    monkeypatch.delenv("GEMINI_API_KEY")
    reloaded = create_app(env_path=tmp_path / ".env").test_client()
    assert reloaded.get("/api/status").json["ai_available"] is True
    assert os.environ["GEMINI_API_KEY"] == key


def test_key_save_rejects_non_objects_and_cross_site_requests(client, tmp_path):
    for payload in [[], "secret"]:
        assert client.post("/api/settings/api-key", json=payload).status_code == 400
    assert client.post("/api/settings/api-key", data={"api_key": "secret"}).status_code == 415
    for headers in [{"Origin": "https://other.example"}, {"Sec-Fetch-Site": "cross-site"}]:
        assert client.post(
            "/api/settings/api-key", json={"api_key": "secret"}, headers=headers
        ).status_code == 403
    assert not (tmp_path / ".env").exists()


def test_save_failure_keeps_previous_key_and_does_not_leak(client, tmp_path, monkeypatch, caplog):
    key = "private-key-that-must-not-leak"
    path = tmp_path / ".env"
    path.write_text("PORT=5050\n")

    def fail(*args):
        raise PermissionError(key)

    monkeypatch.setattr("flashcard_generator.web.set_key", fail)
    response = client.post("/api/settings/api-key", json={"api_key": key})
    assert response.status_code == 500
    assert key not in response.text + caplog.text
    assert path.read_text() == "PORT=5050\n"
    assert client.get("/api/status").json["ai_available"] is False


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
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    def failing(*args, **kwargs):
        raise RuntimeError("secret-key-value")

    monkeypatch.setattr("flashcard_generator.web.generate_deck", failing)
    response = client.post("/api/generate", json={"notes": "Force: A push or pull.", "use_ai": True})
    assert response.status_code == 502
    assert b"secret-key-value" not in response.data
    assert "cards" not in response.get_json()


def test_ai_is_default_even_without_key(client):
    response = client.post("/api/jobs", json={"notes": "Force is a push or pull."})
    assert response.status_code == 400
    assert response.get_json()["error_code"] == "missing_key"
    assert b'value="ai" selected' in client.get("/").data


def test_generation_is_saved_and_export_downloads_a_workbook(client):
    response = client.post(
        "/api/generate",
        json={"notes": "Velocity: The rate of change of displacement.", "use_ai": False},
    )
    payload = response.get_json()
    assert payload["run_id"]
    assert payload["metrics"]["run_id"] == payload["run_id"]
    assert payload["metrics"]["card_count"] == len(payload["cards"])
    assert "calls" not in payload  # internal bookkeeping stays out of the page response

    export = client.get("/api/export.xlsx")
    assert export.status_code == 200
    assert export.mimetype == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert "attachment" in export.headers["Content-Disposition"]
    assert load_workbook(BytesIO(export.data))["runs"].max_row == 2
    assert "Saved runs: 1" in client.get("/export").text


def test_notes_label_is_saved_and_research_data_stays_off_the_page(client, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    def generate(notes, count, **kwargs):
        return {
            "cards": [], "mode": "ai", "model": "test-model", "calls": [],
            "stats": {"chunk_size": 6000},
            "facts": [{"fact_id": "S1F1", "section": 1, "text": "Fact", "outcome": "no_card"}],
        }

    monkeypatch.setattr("flashcard_generator.web.generate_deck", generate)
    payload = client.post(
        "/api/generate", json={"notes": "Force is a push or pull.", "notes_label": "  dsa.txt "}
    ).get_json()
    assert not {"calls", "stats", "facts"} & set(payload)
    conn = storage.connect()
    with closing(conn):
        assert conn.execute("SELECT notes_label, chunk_size FROM runs").fetchall() == [("dsa.txt", 6000)]
        assert conn.execute("SELECT fact_id, outcome FROM facts").fetchall() == [("S1F1", "no_card")]


@pytest.mark.parametrize("label", [123, ["dsa.txt"], "x" * 256])
def test_bad_notes_label_is_rejected(client, label):
    response = client.post(
        "/api/generate", json={"notes": "Force: A push or pull.", "use_ai": False, "notes_label": label}
    )
    assert response.status_code == 400


def test_failed_run_saves_the_counts_attached_to_its_error(client, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    def failing(notes, count, **kwargs):
        error = AIError("quota", "Gemini quota/rate limit reached.")
        error.stats = {"facts_inventoried": 4}
        raise error

    monkeypatch.setattr("flashcard_generator.web.generate_deck", failing)
    assert client.post("/api/generate", json={"notes": "Force is a push or pull."}).status_code == 502
    conn = storage.connect()
    with closing(conn):
        assert conn.execute("SELECT status, facts_inventoried FROM runs").fetchall() == [("failed", 4)]


def test_failed_ai_job_is_saved_with_its_error_code(client, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    def failing(notes, count, **kwargs):
        raise AIError("quota", "Gemini quota/rate limit reached.")

    monkeypatch.setattr("flashcard_generator.web.generate_deck", failing)
    key = client.post("/api/jobs", json={"notes": "Force is a push or pull."}).get_json()["job_id"]
    client.application.extensions["generation_jobs"].executor.shutdown(wait=True)
    assert client.get("/api/jobs/" + key).get_json()["status"] == "failed"
    conn = storage.connect()
    with closing(conn):
        assert conn.execute("SELECT status, error_code FROM runs").fetchall() == [("failed", "quota")]


def test_ai_job_api_and_auto_card_limit(client, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
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
