from types import SimpleNamespace
from unittest.mock import MagicMock

from flashcard_generator.ai import GeneratedCard, GeneratedDeck, generate_with_gemini


def test_ai_filters_invalid_evidence_and_duplicates(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test")
    source = "Force is a push or pull."
    valid = GeneratedCard(front="Define force.", back="A push or pull.", source=source)
    unsupported = GeneratedCard(front="What is mass?", back="Something.", source="Not in notes.")
    circular = GeneratedCard(front="Force", back="Force", source=source)
    fake = MagicMock()
    fake.__enter__.return_value.models.generate_content.return_value = SimpleNamespace(
        parsed=GeneratedDeck(cards=[valid, unsupported, circular, valid])
    )
    monkeypatch.setattr("google.genai.Client", lambda **kwargs: fake)
    cards = generate_with_gemini(source, 500)
    assert len(cards) == 1
    assert cards[0].source == source
