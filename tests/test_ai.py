from contextlib import nullcontext
from threading import Event
from types import SimpleNamespace

import pytest

from flashcard_generator.ai import (
    AIError,
    Cancelled,
    HuggingFaceProvider,
    ModelRuntime,
    SourceUnit,
    _select_device,
    build_prompt,
    generate_deck,
    parse_model_response,
    safe_ai_error,
    source_units,
)
from flashcard_generator.jobs import JobStore

NOTES = "An address identifies one byte. A pointer occupies four bytes."


class Provider:
    model = "scripted-t5-qg"
    device = "cpu"
    provider = "scripted"

    def __init__(self, responses=None, failure=None):
        self.responses = responses or {}
        self.failure = failure
        self.calls = []
        self.prepared = False

    def prepare(self, progress):
        self.prepared = True
        progress("Model ready on cpu")

    def generate(self, source):
        self.calls.append(source)
        if self.failure:
            raise self.failure
        return self.responses.get(
            source.id,
            f"question: What statement is supported by source unit {source.id}?",
        )


def test_source_units_split_independent_facts_and_keep_question_answer_pairs():
    units = source_units(
        "Velocity: The rate of change of displacement.\n\n"
        "What is the SI unit of force? The SI unit of force is the newton."
    )
    assert [unit.text for unit in units] == [
        "Velocity: The rate of change of displacement.",
        "What is the SI unit of force? The SI unit of force is the newton.",
    ]
    assert [unit.answer for unit in units] == [
        "The rate of change of displacement.",
        "The SI unit of force is the newton",
    ]


def test_source_units_select_concise_literal_answer_spans():
    units = source_units(
        "An address identifies one byte. A pointer occupies four bytes. "
        "Newton's second law states that force equals mass times acceleration."
    )
    assert [unit.answer for unit in units] == [
        "one byte",
        "four bytes",
        "force equals mass times acceleration",
    ]


def test_generation_is_local_source_grounded_and_reports_unit_coverage():
    provider = Provider()
    progress = []
    result = generate_deck(NOTES, provider=provider, progress=progress.append)
    assert provider.prepared
    assert len(result["cards"]) == 2
    assert all(card["back"] in NOTES for card in result["cards"])
    assert result["provider"] == "scripted"
    assert result["device"] == "cpu"
    assert result["coverage"]["identified_units"] == 2
    assert result["coverage"]["covered_units"] == 2
    assert result["coverage"]["all_identified_facts_covered"]
    assert progress[-1] == "Complete · source-unit coverage report ready"


def test_prompt_uses_answer_aware_question_generation_contract():
    source = SourceUnit("U1", "Force is a push.", 1, "a push")
    assert build_prompt(source) == "answer: a push context: Force is a push. </s>"


@pytest.mark.parametrize(
    "response,reason",
    [
        ("SKIP", "skipped"),
        ("not structured", "not phrased"),
        ("question: What is force?\nanswer: A push", "not one question"),
        ("question: What is it?", "vague"),
    ],
)
def test_invalid_model_outputs_are_rejected(response, reason):
    card, error = parse_model_response(response, SourceUnit("U1", "Force is a push.", 1, "a push"))
    assert card is None
    assert reason.casefold() in error.casefold()


def test_model_generates_only_the_question_and_answer_stays_source_grounded():
    card, error = parse_model_response(
        "question: What is force?",
        SourceUnit("U1", "Force is   a push or pull.", 1, "a push or pull"),
    )
    assert error is None
    assert card["back"] == "a push or pull"
    assert card["generator"] == "t5-question-generation"


def test_non_source_answer_span_is_rejected_before_card_acceptance():
    card, error = parse_model_response(
        "question: What is force?",
        SourceUnit("U1", "Force is a push.", 1, "invented answer"),
    )
    assert card is None
    assert "exact quote" in error


def test_invalid_output_is_reported_without_replacing_it_with_rules_cards():
    provider = Provider({"U1": "This is not a question"})
    result = generate_deck(NOTES, provider=provider)
    assert len(result["cards"]) == 1
    assert result["coverage"]["covered_units"] == 1
    assert "not phrased" in result["coverage"]["uncovered"][0]["reason"]


def test_card_limit_is_applied_after_all_units_are_processed():
    provider = Provider()
    result = generate_deck(NOTES, 1, provider=provider)
    assert len(provider.calls) == 2
    assert len(result["cards"]) == 1
    assert result["coverage"]["uncovered"][-1]["reason"] == "Excluded by card limit."


def test_duplicate_cards_do_not_claim_duplicate_coverage():
    response = "question: What is a byte fact?"
    provider = Provider({"U1": response, "U2": response})
    result = generate_deck("First fact is one byte. Second fact is one byte.", provider=provider)
    assert len(result["cards"]) == 1
    assert result["coverage"]["uncovered"][0]["reason"] == "Duplicate card removed."


def test_provider_prepares_lazy_runtime_with_automatic_download_message():
    runtime = ModelRuntime(SimpleNamespace(), SimpleNamespace(), SimpleNamespace(), "cpu")
    calls = []
    provider = HuggingFaceProvider(
        configured_model="mrm8488/t5-base-finetuned-question-generation-ap",
        device="auto",
        loader=lambda model, device: calls.append((model, device)) or runtime,
    )
    progress = []
    provider.prepare(progress.append)
    assert calls == [("mrm8488/t5-base-finetuned-question-generation-ap", "auto")]
    assert "900 MB" in progress[0]
    assert provider.device == "cpu"


class FakeTorch:
    def __init__(self, cuda=False, mps=False):
        self.cuda = SimpleNamespace(is_available=lambda: cuda)
        self.backends = SimpleNamespace(mps=SimpleNamespace(is_available=lambda: mps))
        self.inference_mode = nullcontext

    @staticmethod
    def device(name):
        return SimpleNamespace(type=name, __str__=lambda self: name)


def test_device_selection_prefers_cuda_then_cpu():
    assert _select_device(FakeTorch(cuda=True), "auto").type == "cuda"
    assert _select_device(FakeTorch(), "auto").type == "cpu"
    with pytest.raises(AIError, match="CUDA"):
        _select_device(FakeTorch(), "cuda")


def test_cancel_does_not_make_model_request():
    provider = Provider()
    with pytest.raises(Cancelled):
        generate_deck(NOTES, provider=provider, cancelled=lambda: True)
    assert not provider.calls


def test_provider_failure_never_returns_partial_or_rules_cards():
    provider = Provider(failure=OSError("private source and cache path"))
    with pytest.raises(AIError) as failure:
        generate_deck(NOTES, provider=provider)
    assert failure.value.code == "model_setup_failed"
    assert "private source" not in str(failure.value)


def test_out_of_memory_error_is_actionable_without_raw_details():
    public = safe_ai_error(RuntimeError("CUDA out of memory near private source"))
    assert public.code == "out_of_memory"
    assert "private source" not in str(public)


def test_background_job_progress_concurrency_and_cancellation():
    store = JobStore()
    entered, release = Event(), Event()

    def work(progress, cancelled):
        progress("Loading local model")
        entered.set()
        assert release.wait(3)
        return {"cards": ["must not be published after cancellation"]}

    try:
        key = store.submit(work)
        assert entered.wait(3)
        assert store.get(key)["progress"] == "Loading local model"
        with pytest.raises(ValueError):
            store.submit(work)
        assert store.cancel(key)
    finally:
        release.set()
        store.executor.shutdown(wait=True)
    assert store.get(key)["status"] == "cancelled"
    assert "result" not in store.get(key)
    assert store.get("unknown") is None
