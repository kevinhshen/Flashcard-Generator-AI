"""Local, source-grounded question generation with Hugging Face Transformers."""

from __future__ import annotations

import importlib.util
import os
import re
from collections.abc import Callable
from dataclasses import dataclass
from threading import Lock
from typing import Any

from .generator import Flashcard, clean_text, parse_blocks, split_sentences

DEFAULT_MODEL_ID = "mrm8488/t5-base-finetuned-question-generation-ap"
MAX_SOURCE_CHARS = 420
MAX_SOURCE_UNITS = 500
SAFETY_CARD_LIMIT = 500
_RUNTIME_CACHE: dict[tuple[str, str], ModelRuntime] = {}
_RUNTIME_LOCK = Lock()


class AIError(RuntimeError):
    """Safe, user-facing error; never include raw model errors or source notes."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class Cancelled(AIError):
    def __init__(self):
        super().__init__("cancelled", "Generation cancelled. No rules fallback was used.")


@dataclass(frozen=True, slots=True)
class SourceUnit:
    id: str
    text: str
    section: int
    answer: str = ""


@dataclass(slots=True)
class ModelRuntime:
    torch: Any
    tokenizer: Any
    model: Any
    device: Any


def model_id() -> str:
    return os.getenv("HF_MODEL_ID", DEFAULT_MODEL_ID).strip() or DEFAULT_MODEL_ID


def requested_device() -> str:
    value = os.getenv("HF_DEVICE", "auto").strip().lower() or "auto"
    if value not in {"auto", "cpu", "cuda", "mps"}:
        raise AIError("invalid_configuration", "HF_DEVICE must be auto, cpu, cuda, or mps.")
    return value


def _model_is_cached(configured_model: str) -> bool:
    try:
        from huggingface_hub import try_to_load_from_cache

        required = ("config.json", "tokenizer_config.json", "spiece.model")
        files_ready = all(
            isinstance(try_to_load_from_cache(configured_model, filename), str)
            for filename in required
        )
        weights_ready = any(
            isinstance(try_to_load_from_cache(configured_model, filename), str)
            for filename in ("model.safetensors", "pytorch_model.bin")
        )
        return files_ready and weights_ready
    except Exception:
        return False


def model_status() -> dict:
    """Report package/cache readiness without downloading or loading model weights."""
    configured_model = model_id()
    dependencies_ready = all(
        importlib.util.find_spec(name) is not None
        for name in ("torch", "transformers", "sentencepiece", "google.protobuf")
    )
    cached = dependencies_ready and _model_is_cached(configured_model)
    loaded = any(key[0] == configured_model for key in _RUNTIME_CACHE)
    return {
        "available": dependencies_ready,
        "model": configured_model,
        "model_cached": cached,
        "model_loaded": loaded,
        "automatic_download": True,
    }


def safe_ai_error(exc: Exception) -> AIError:
    if isinstance(exc, AIError):
        return exc
    if isinstance(exc, TimeoutError) or "timeout" in type(exc).__name__.lower():
        return AIError("timeout", "Local model generation timed out. Try fewer or shorter notes.")
    message = str(exc).casefold()
    if "out of memory" in message or "cuda error" in message:
        return AIError(
            "out_of_memory",
            "The local model ran out of memory. Set HF_DEVICE=cpu or use shorter notes.",
        )
    if isinstance(exc, (ImportError, ModuleNotFoundError)):
        return AIError(
            "dependency_missing",
            "Local AI packages are missing. Reinstall the app with: python -m pip install -e .",
        )
    if isinstance(exc, OSError):
        return AIError(
            "model_setup_failed",
            "Could not download or load the Hugging Face model. Check internet access and free disk space, "
            "then retry.",
        )
    return AIError("model_error", "The local Hugging Face model could not complete generation.")


def _split_long_text(text: str, max_chars: int = MAX_SOURCE_CHARS) -> list[str]:
    remaining = text.strip()
    pieces = []
    while len(remaining) > max_chars:
        boundary = remaining.rfind(" ", max_chars // 2, max_chars + 1)
        if boundary < 0:
            boundary = max_chars
        pieces.append(remaining[:boundary].strip())
        remaining = remaining[boundary:].strip()
    if remaining:
        pieces.append(remaining)
    return pieces


def source_units(notes: str) -> list[SourceUnit]:
    """Create bounded contexts with deterministic answer spans for question generation."""
    segments: list[tuple[str, str]] = []
    for block in parse_blocks(notes):
        if block["type"] == "labeled":
            source = f"{block['label']}: {block['content']}"
            if len(source) <= MAX_SOURCE_CHARS:
                segments.append((source, block["content"]))
            else:
                segments.extend((piece, piece) for piece in _split_long_text(source))
            continue

        sentences = split_sentences(block["content"]) or [block["content"]]
        index = 0
        while index < len(sentences):
            sentence = sentences[index]
            if sentence.rstrip().endswith("?") and index + 1 < len(sentences):
                pair = f"{sentence} {sentences[index + 1]}"
                if len(pair) <= MAX_SOURCE_CHARS:
                    segments.append((pair, sentences[index + 1].rstrip(".")))
                    index += 2
                    continue
            for piece in _split_long_text(sentence):
                segments.append((piece, _answer_span(piece)))
            index += 1

    useful = [
        (segment, answer)
        for segment, answer in segments
        if len(segment.split()) >= 3
        and answer
        and any(character.isalpha() for character in segment)
    ]
    if len(useful) > MAX_SOURCE_UNITS:
        raise AIError(
            "too_many_units",
            f"The notes contain over {MAX_SOURCE_UNITS} source units. Split them into smaller files.",
        )
    return [
        SourceUnit(f"U{index}", text, index, answer)
        for index, (text, answer) in enumerate(useful, 1)
    ]


def _answer_span(text: str) -> str:
    """Choose a useful answer that is always a literal span of the source unit."""
    candidate = text.strip()
    definition = re.fullmatch(
        r"(.+?)\s+(?:is|are|means|refers to|is defined as)\s+(.+?)[.]?",
        candidate,
        re.IGNORECASE,
    )
    if definition:
        subject, answer = (part.strip() for part in definition.groups())
        if 1 <= len(subject.split()) <= 12 and subject.casefold() not in {
            "it",
            "this",
            "that",
            "these",
            "they",
            "there",
        }:
            return answer.rstrip(".")
    quantity = re.search(
        r"(?<![\w.])(?:[-+]?\d+(?:\.\d+)?|one|two|three|four|five|six|seven|eight|nine|ten)\s*"
        r"(?:degrees(?:\s+[CF]| Celsius| Fahrenheit)?|°[CF]|%|m/s(?:²|2)?|"
        r"kg|mg|km|cm|mm|bytes?|bits?|Hz|kHz|MHz|GHz|ms|seconds|minutes|hours|m|s|N|V|A|W|J|K)"
        r"(?!\w)",
        candidate,
        re.IGNORECASE,
    )
    if quantity:
        return quantity.group(0)
    stated_fact = re.fullmatch(r"(.+?)\s+states that\s+(.+?)[.]?", candidate, re.IGNORECASE)
    if stated_fact:
        return stated_fact.group(2).strip().rstrip(".")
    return candidate.rstrip(".")


def build_prompt(source: SourceUnit) -> str:
    answer = source.answer or _answer_span(source.text)
    return f"answer: {answer} context: {source.text} </s>"


def parse_model_response(response: str, source: SourceUnit) -> tuple[dict | None, str | None]:
    value = response.strip()
    if value.casefold() == "skip":
        return None, "Model skipped this source unit."
    lines = [line.strip() for line in value.splitlines() if line.strip()]
    if len(lines) != 1:
        return None, "Model output was not one question."
    front = re.sub(r"^(?:question|q)\s*:\s*", "", lines[0], flags=re.IGNORECASE)
    front = re.sub(r"\s+", " ", front).strip()
    back = re.sub(r"\s+", " ", source.answer or _answer_span(source.text)).strip()
    if len(front) < 3 or not back:
        return None, "Model produced an empty question."
    if not front.endswith("?"):
        return None, "Model output was not phrased as a question."
    if front.casefold().rstrip(".?!") == back.casefold().rstrip(".?!"):
        return None, "Model produced a tautological card."
    if re.match(r"^(what|why|how|where)\s+(is|are|does)\s+(it|this|that|these)\b", front, re.I):
        return None, "Model produced a vague question."
    if back.casefold() not in re.sub(r"\s+", " ", source.text).casefold():
        return None, "Selected answer was not an exact quote from the source."
    return {
        "front": front,
        "back": back,
        "card_type": "basic",
        "source": source.text,
        "fact_ids": [source.id],
        "generator": "t5-question-generation",
    }, None


def _select_device(torch: Any, requested: str) -> Any:
    if requested == "cuda":
        if not torch.cuda.is_available():
            raise AIError("device_unavailable", "CUDA was requested, but no CUDA device is available.")
        return torch.device("cuda")
    if requested == "mps":
        if not getattr(torch.backends, "mps", None) or not torch.backends.mps.is_available():
            raise AIError("device_unavailable", "MPS was requested, but no MPS device is available.")
        return torch.device("mps")
    if requested == "cpu":
        return torch.device("cpu")
    if torch.cuda.is_available():
        return torch.device("cuda")
    if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


def _load_runtime(configured_model: str, device_name: str) -> ModelRuntime:
    cache_key = (configured_model, device_name)
    with _RUNTIME_LOCK:
        cached = _RUNTIME_CACHE.get(cache_key)
        if cached is not None:
            return cached
        try:
            import torch
            from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
        except (ImportError, ModuleNotFoundError) as exc:
            raise safe_ai_error(exc) from exc

        device = _select_device(torch, device_name)
        try:
            local_only = _model_is_cached(configured_model)
            tokenizer = AutoTokenizer.from_pretrained(
                configured_model,
                local_files_only=local_only,
            )
            dtype = torch.float16 if device.type in {"cuda", "mps"} else torch.float32
            model = AutoModelForSeq2SeqLM.from_pretrained(
                configured_model,
                torch_dtype=dtype,
                local_files_only=local_only,
            )
            model = model.to(device).eval()
        except Exception as exc:
            raise safe_ai_error(exc) from exc
        runtime = ModelRuntime(torch, tokenizer, model, device)
        _RUNTIME_CACHE[cache_key] = runtime
        return runtime


class HuggingFaceProvider:
    """Lazy in-process T5 question generator with automatic download and caching."""

    provider = "huggingface"

    def __init__(self, *, configured_model=None, device=None, loader=None):
        self.model = configured_model or model_id()
        self.requested_device = device or requested_device()
        self.loader = loader or _load_runtime
        self.runtime: ModelRuntime | None = None
        self.device = "not loaded"

    def prepare(self, progress: Callable[[str], None]) -> None:
        progress(f"Preparing {self.model} · first use downloads and caches about 900 MB")
        self.runtime = self.loader(self.model, self.requested_device)
        self.device = str(self.runtime.device)
        progress(f"Model ready on {self.device}")

    def generate(self, source: SourceUnit) -> str:
        if self.runtime is None:
            self.prepare(lambda _message: None)
        assert self.runtime is not None
        prompt = build_prompt(source)
        tokenizer = self.runtime.tokenizer
        encoded = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=512)
        encoded = {name: value.to(self.runtime.device) for name, value in encoded.items()}
        with self.runtime.torch.inference_mode():
            generated = self.runtime.model.generate(
                **encoded,
                do_sample=False,
                num_beams=1,
                max_new_tokens=64,
                use_cache=True,
            )
        return tokenizer.decode(generated[0], skip_special_tokens=True)

    def close(self) -> None:
        return None


def generate_deck(
    notes: str,
    max_cards: int | None = None,
    *,
    provider=None,
    progress: Callable[[str], None] = lambda _message: None,
    cancelled: Callable[[], bool] = lambda: False,
) -> dict:
    """Generate one strictly grounded card per bounded source unit."""
    if max_cards is not None and (type(max_cards) is not int or not 1 <= max_cards <= 500):
        raise ValueError("Card limit must be blank or an integer from 1 to 500.")
    own_provider = provider is None
    client = HuggingFaceProvider() if own_provider else provider
    units = source_units(clean_text(notes))
    cards: list[dict] = []
    uncovered = []
    seen = set()
    calls = 0

    try:
        if cancelled():
            raise Cancelled()
        prepare = getattr(client, "prepare", None)
        if callable(prepare):
            prepare(progress)
        for index, unit in enumerate(units, 1):
            if cancelled():
                raise Cancelled()
            progress(f"Generating card {index}/{len(units)} · local T5 inference")
            calls += 1
            raw = client.generate(unit)
            if cancelled():
                raise Cancelled()
            card, reason = parse_model_response(raw, unit)
            if card is None:
                uncovered.append(
                    {"id": unit.id, "text": unit.text, "source": unit.text, "reason": reason}
                )
                continue
            key = (card["front"].casefold(), card["back"].casefold())
            if key in seen:
                uncovered.append(
                    {
                        "id": unit.id,
                        "text": unit.text,
                        "source": unit.text,
                        "reason": "Duplicate card removed.",
                    }
                )
                continue
            seen.add(key)
            cards.append(card)

        limit = max_cards or SAFETY_CARD_LIMIT
        returned = cards[:limit]
        for card in cards[limit:]:
            uncovered.append(
                {
                    "id": card["fact_ids"][0],
                    "text": card["source"],
                    "source": card["source"],
                    "reason": "Excluded by card limit.",
                }
            )
        covered_units = len(returned)
        warnings = []
        if uncovered:
            warnings.append(
                "Some source units did not produce a validated card; inspect the coverage report."
            )
        if not units:
            warnings.append("No usable source units found. Check the extracted source text.")
        progress("Complete · source-unit coverage report ready")
        return {
            "cards": returned,
            "mode": "ai",
            "provider": getattr(client, "provider", "custom"),
            "model": client.model,
            "device": getattr(client, "device", "test"),
            "warning": " ".join(warnings),
            "coverage": {
                "identified_units": len(units),
                "covered_units": covered_units,
                "identified_facts": len(units),
                "covered_facts": covered_units,
                "sections_processed": len(units),
                "sections_total": len(units),
                "uncovered": uncovered,
                "rejected_facts": [],
                "exclusions": [],
                "requests": calls,
                "all_identified_facts_covered": bool(units) and not uncovered,
                "scope": "Validated source-unit coverage, not proof that every fact was identified.",
            },
        }
    except Exception as exc:
        raise safe_ai_error(exc) from exc
    finally:
        if own_provider:
            client.close()


def generate_with_huggingface(notes: str, max_cards: int | None = None) -> list[Flashcard]:
    """Compatibility helper for Python callers; use generate_deck for coverage."""
    return [
        Flashcard(**{key: card[key] for key in ("front", "back", "card_type", "source")})
        for card in generate_deck(notes, max_cards)["cards"]
    ]
