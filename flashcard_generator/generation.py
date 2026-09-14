"""Orchestration types shared by rule-based and model-based generators."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Protocol, Sequence

from .models import Flashcard, SourceChunk
from .parser import split_sentences


EngineName = Literal["rules", "hybrid", "flan"]
PolishMode = Literal["off", "auto", "all"]

FRAGMENT_STARTERS = {
    "about", "at", "by", "for", "from", "in", "into", "of", "on", "to", "with",
}


@dataclass(slots=True)
class RuleGenerationResult:
    """Rule output grouped by how safe it is to export without a model."""

    high_confidence: list[Flashcard] = field(default_factory=list)
    low_confidence: list[Flashcard] = field(default_factory=list)
    unresolved: list[SourceChunk] = field(default_factory=list)

    @property
    def all_rule_cards(self) -> list[Flashcard]:
        return [*self.high_confidence, *self.low_confidence]

    @property
    def hybrid_sources(self) -> list[SourceChunk]:
        """Return uncertain facts once, preserving their exact provenance."""
        sources = [
            SourceChunk(card.source_id, card.source_text, "paragraph")
            for card in self.low_confidence
        ]
        sources.extend(self.unresolved)
        return _unique_sources(sources)


@dataclass(slots=True)
class ModelGenerationResult:
    cards: list[Flashcard] = field(default_factory=list)
    skipped: list[tuple[SourceChunk, str]] = field(default_factory=list)


class ModelGenerator(Protocol):
    def generate(self, sources: Sequence[SourceChunk]) -> ModelGenerationResult:
        """Generate validated cards from independent source chunks."""


@dataclass(slots=True)
class GenerationReport:
    cards: list[Flashcard]
    skipped_sources: list[tuple[SourceChunk, str]] = field(default_factory=list)


def model_sources_from_chunks(chunks: Sequence[SourceChunk]) -> list[SourceChunk]:
    """Split paragraphs into independent facts before sending them to a model."""
    sources: list[SourceChunk] = []
    for chunk in chunks:
        if chunk.kind == "labeled":
            sources.append(chunk)
            continue
        for number, sentence in enumerate(split_sentences(chunk.text), start=1):
            sources.append(
                SourceChunk(
                    source_id=f"{chunk.source_id}:sentence-{number}",
                    text=sentence,
                    kind="paragraph",
                )
            )
    return sources


def run_generation(
    chunks: Sequence[SourceChunk],
    engine: EngineName,
    model_generator: ModelGenerator | None = None,
    polish: PolishMode = "auto",
) -> GenerationReport:
    """Run the requested engine without importing optional AI dependencies."""
    from .rules import generate_rule_candidates

    rule_result = generate_rule_candidates(list(chunks))
    if engine == "rules":
        return GenerationReport(rule_result.all_rule_cards)

    if model_generator is None:
        raise ValueError(f"{engine} mode requires a model generator")

    sources = rule_result.hybrid_sources if engine == "hybrid" else model_sources_from_chunks(chunks)
    model_result = model_generator.generate(sources)
    if engine == "flan":
        return GenerationReport(model_result.cards, model_result.skipped)

    rule_cards = list(rule_result.high_confidence)
    improvement_result = _improve_rule_cards(rule_cards, model_generator, polish)
    revisions = {card.source_id: card for card in improvement_result.cards}
    cards = [revisions.get(card.source_id, card) for card in rule_cards]
    return GenerationReport(
        [*cards, *model_result.cards],
        [*model_result.skipped, *improvement_result.skipped],
    )


def needs_model_polish(card: Flashcard) -> bool:
    """Identify answers that cannot stand alone without guessing at course content."""
    if card.kind == "cloze":
        return False
    words = card.back.strip(". ").split()
    if not words:
        return True
    return words[0].casefold() in FRAGMENT_STARTERS or len(words) <= 2


def _improve_rule_cards(
    cards: Sequence[Flashcard],
    model_generator: ModelGenerator,
    polish: PolishMode,
) -> ModelGenerationResult:
    improve = getattr(model_generator, "improve", None)
    if polish == "off" or not callable(improve):
        return ModelGenerationResult()

    candidates = list(cards) if polish == "all" else [card for card in cards if needs_model_polish(card)]
    return improve(candidates)


def _unique_sources(sources: Sequence[SourceChunk]) -> list[SourceChunk]:
    seen: set[tuple[str, str]] = set()
    unique: list[SourceChunk] = []
    for source in sources:
        key = (source.source_id, source.text)
        if key not in seen:
            seen.add(key)
            unique.append(source)
    return unique
