import json
from threading import Event
from urllib.error import URLError

import pytest

from flashcard_generator.ai import (
    AIError,
    Cancelled,
    Inventory,
    OllamaProvider,
    generate_deck,
    ollama_status,
    safe_ai_error,
    split_source,
)
from flashcard_generator.jobs import JobStore

NOTES = "An address identifies one byte. A pointer occupies four bytes."
FACTS = [
    {"text": "An address identifies one byte.", "source": "An address identifies one byte."},
    {"text": "A pointer occupies four bytes.", "source": "A pointer occupies four bytes."},
]


class Provider:
    model = "scripted-test-provider"

    def __init__(self, override=None):
        self.calls = []
        self.override = override

    def ask(self, stage, data, schema):
        self.calls.append((stage, data))
        if self.override:
            result = self.override(stage, data)
            if result is not None:
                return schema.model_validate(result)
        if stage == "inventory":
            return schema.model_validate({"facts": FACTS[:1]})
        if stage == "audit_inventory":
            return schema.model_validate({"facts": FACTS})
        return schema.model_validate(
            {
                "cards": [
                    {
                        "front": "Which fact is tested by " + fact["id"] + "?",
                        "back": fact["text"],
                        "fact_ids": [fact["id"]],
                    }
                    for fact in data["facts"]
                ]
            }
        )


def test_audit_recovers_omission_and_every_batch_is_reviewed():
    provider = Provider()
    result = generate_deck(NOTES, provider=provider)
    assert [s for s, _ in provider.calls] == ["inventory", "audit_inventory", "draft", "review"]
    assert len(result["cards"]) == 2
    assert result["coverage"]["all_identified_facts_covered"]
    assert result["cards"][1]["back"] == FACTS[1]["text"]
    assert all(card["source"] in NOTES for card in result["cards"])


def test_audit_correction_does_not_resurrect_misread_fact():
    def misread(stage, data):
        if stage == "inventory":
            return {"facts": [{"text": "One address stores four bytes.", "source": NOTES}]}

    provider = Provider(misread)
    result = generate_deck(NOTES, provider=provider)
    drafted = next(data for stage, data in provider.calls if stage == "draft")
    assert all(f["text"] != "One address stores four bytes." for f in drafted["facts"])
    assert "One address stores four bytes" in result["coverage"]["exclusions"][0]["reason"]


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self):
        return json.dumps(self.payload).encode()


def test_ollama_uses_local_structured_output_without_api_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    requests = []

    def open_request(request, timeout):
        requests.append((request, timeout))
        return FakeResponse({"response": '{"facts": [], "exclusions": []}', "done": True})

    provider = OllamaProvider(
        base_url="http://127.0.0.1:11434", model="test-model", timeout=12, opener=open_request
    )
    assert provider.ask("inventory", {"owned_section": NOTES}, Inventory).facts == []
    request, timeout = requests[0]
    payload = json.loads(request.data)
    assert request.full_url == "http://127.0.0.1:11434/api/generate"
    assert timeout == 12
    assert payload["model"] == "test-model"
    assert payload["stream"] is False
    assert payload["think"] is False
    assert payload["format"] == Inventory.model_json_schema()
    assert payload["options"]["temperature"] == 0
    assert "engineering tutor" in payload["system"]


def test_ollama_connection_failure_is_actionable():
    def unavailable(_request, timeout):
        raise URLError("private network details")

    provider = OllamaProvider(opener=unavailable)
    with pytest.raises(AIError) as failure:
        provider.ask("inventory", {"owned_section": NOTES}, Inventory)
    assert failure.value.code == "service_unavailable"
    assert "private network details" not in str(failure.value)


def test_ollama_status_reports_configured_model(monkeypatch):
    monkeypatch.setenv("OLLAMA_MODEL", "qwen3:8b")
    monkeypatch.setattr(
        "flashcard_generator.ai.urlopen",
        lambda _request, timeout: FakeResponse({"models": [{"name": "qwen3:8b"}]}),
    )
    assert ollama_status() == {"available": True, "model": "qwen3:8b", "model_installed": True}


@pytest.mark.parametrize("notes", ["x" * 13001, "first\n\n" * 3000, "alpha beta " * 1500])
def test_chunking_never_drops_characters(notes):
    parts = split_source(notes)
    assert "".join(parts) == notes
    assert all(0 < len(part) <= 6000 for part in parts)


def test_chunking_prefers_complete_sentences():
    notes = "A complete scientific statement. " * 300
    assert all(part.rstrip().endswith(".") for part in split_source(notes))


def test_late_sections_processed_before_card_limit():
    def source_facts(stage, data):
        if stage in {"inventory", "audit_inventory"}:
            quote = data["owned_section"].strip()
            return {"facts": [{"text": quote, "source": quote}]}

    notes = "First fact. " * 550 + "End fact."
    result = generate_deck(notes, 1, provider=Provider(source_facts))
    assert result["coverage"]["sections_processed"] == len(split_source(notes)) > 1
    assert result["coverage"]["uncovered"][-1]["reason"] == "Excluded by card limit."
    assert "incomplete" in result["warning"]


def test_unlocatable_source_is_reported_and_not_generated():
    def unsupported(stage, data):
        if stage == "audit_inventory":
            return {"facts": FACTS + [{"text": "Invented claim", "source": "Not in notes"}]}

    result = generate_deck(NOTES, provider=Provider(unsupported))
    assert len(result["cards"]) == 2
    assert result["coverage"]["rejected_facts"][0]["text"] == "Invented claim"
    assert not result["coverage"]["all_identified_facts_covered"]


def test_failed_review_does_not_accept_draft_and_repairs_are_bounded():
    provider = Provider(lambda stage, data: {"cards": []} if stage == "review" else None)
    result = generate_deck(NOTES, provider=provider)
    assert result["cards"] == []
    assert len(result["coverage"]["uncovered"]) == 2
    assert [s for s, _ in provider.calls].count("review") == 2


def test_unknown_ids_and_tautologies_do_not_claim_coverage():
    def invalid(stage, data):
        if stage == "review":
            return {
                "cards": [
                    {"front": "Invalid provenance?", "back": "one byte", "fact_ids": ["invented"]},
                    {"front": "Same statement", "back": "Same statement", "fact_ids": ["S1F1"]},
                ]
            }

    result = generate_deck(NOTES, provider=Provider(invalid))
    assert not result["cards"]
    assert result["coverage"]["covered_facts"] == 0


def test_conflicting_answers_are_removed_instead_of_chosen():
    def conflict(stage, data):
        if stage == "review":
            return {
                "cards": [
                    {"front": "How many bytes?", "back": f["text"], "fact_ids": [f["id"]]}
                    for f in data["facts"]
                ]
            }

    result = generate_deck(NOTES, provider=Provider(conflict))
    assert not result["cards"]
    assert len(result["coverage"]["uncovered"]) == 2


def test_missing_reviewed_fact_gets_targeted_repair():
    reviews = 0

    def omission(stage, data):
        nonlocal reviews
        if stage == "review":
            reviews += 1
            if reviews == 1:
                f = data["facts"][0]
                return {
                    "cards": [
                        {"front": "What does an address identify?", "back": f["text"], "fact_ids": [f["id"]]}
                    ]
                }

    provider = Provider(omission)
    result = generate_deck(NOTES, provider=provider)
    assert result["coverage"]["all_identified_facts_covered"]
    assert len(provider.calls[-1][1]["facts"]) == 1
    assert provider.calls[-1][1]["facts"][0]["text"] == FACTS[1]["text"]


@pytest.mark.parametrize(
    "code,expected",
    [(403, "authentication"), (404, "model_unavailable"), (503, "provider_unavailable")],
)
def test_provider_errors_are_actionable_without_secrets(code, expected):
    error = RuntimeError("secret-key-and-private-notes")
    error.code = code
    public = safe_ai_error(error)
    assert public.code == expected
    assert "secret" not in str(public)


def test_cancel_does_not_make_provider_request():
    provider = Provider()
    with pytest.raises(Cancelled):
        generate_deck(NOTES, provider=provider, cancelled=lambda: True)
    assert not provider.calls


def test_provider_failure_never_returns_partial_or_local_cards():
    def fail(stage, data):
        if stage == "review":
            raise TimeoutError("private notes")

    with pytest.raises(AIError) as failure:
        generate_deck(NOTES, provider=Provider(fail))
    assert failure.value.code == "timeout"


def test_background_job_progress_concurrency_and_cancellation():
    store = JobStore()
    entered, release = Event(), Event()

    def work(progress, cancelled):
        progress("Auditing source")
        entered.set()
        assert release.wait(3)
        return {"cards": ["must not be published after cancellation"]}

    try:
        key = store.submit(work)
        assert entered.wait(3)
        assert store.get(key)["progress"] == "Auditing source"
        with pytest.raises(ValueError):
            store.submit(work)
        assert store.cancel(key)
    finally:
        release.set()
        store.executor.shutdown(wait=True)
    assert store.get(key)["status"] == "cancelled"
    assert "result" not in store.get(key)
    assert store.get("unknown") is None
