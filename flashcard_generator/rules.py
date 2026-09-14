"""Deterministic flashcard generation for high-confidence source chunks."""

from __future__ import annotations

import re

from .generation import RuleGenerationResult
from .models import Flashcard, SourceChunk
from .parser import split_sentences


QUESTION_STARTERS = {"what", "who", "where", "when", "why", "how", "which", "define", "explain", "describe", "list"}
STOP_WORDS = {
    "the", "a", "an", "and", "or", "but", "for", "from", "with", "that", "this",
    "these", "those", "have", "has", "had", "into", "than", "then", "only", "are",
    "was", "were", "will", "would", "could", "should", "their", "there", "about",
}
DEFINITION_PATTERNS = (
    re.compile(r"^(?P<term>.+?)\s+is\s+(?:a|an|the)\s+(?P<definition>.+)$", re.IGNORECASE),
    re.compile(r"^(?P<term>.+?)\s+refers\s+to\s+(?P<definition>.+)$", re.IGNORECASE),
    re.compile(r"^(?P<term>.+?)\s+is\s+defined\s+as\s+(?P<definition>.+)$", re.IGNORECASE),
    re.compile(r"^(?P<term>.+?)\s+means\s+(?P<definition>.+)$", re.IGNORECASE),
)
EXISTENTIAL_FACT_PATTERN = re.compile(r"^there\s+(?:is|are)\b", re.IGNORECASE)
GROUP_IDENTITY_PATTERN = re.compile(
    r"^(?P<subject>[A-Z][A-Za-z'’-]*(?:\s+and\s+[a-z][A-Za-z'’-]*)+)\s+are\s+(?P<predicate>.+)$"
)
TRAILING_CLAUSE_PATTERN = re.compile(r",\s+(?:but|and|or)\s+", re.IGNORECASE)
GENERIC_CONCEPTS = {"the", "this", "these", "that", "those", "there", "it", "only"}


def _is_question(sentence: str) -> bool:
    first_word = sentence.split(maxsplit=1)[0].lower().rstrip("?:") if sentence.split() else ""
    return sentence.endswith("?") or first_word in QUESTION_STARTERS


def _definition_card(sentence: str, chunk: SourceChunk) -> Flashcard | None:
    for pattern in DEFINITION_PATTERNS:
        match = pattern.match(sentence)
        if match:
            term = match.group("term").strip().rstrip(":")
            definition = match.group("definition").strip().rstrip(".")
            return Flashcard(
                front=f"What is {term}?",
                back=definition,
                source_text=chunk.text,
                source_id=chunk.source_id,
                generator="rule",
            )
    return None


def _group_identity_card(sentence: str, chunk: SourceChunk) -> Flashcard | None:
    """Turn a clear two-part identity fact into a direct retrieval question."""
    match = GROUP_IDENTITY_PATTERN.match(sentence)
    if not match:
        return None

    predicate = TRAILING_CLAUSE_PATTERN.split(match.group("predicate"), maxsplit=1)[0].rstrip(".")
    if not predicate.lower().startswith("the "):
        return None

    return Flashcard(
        front=f"What are {predicate}?",
        back=match.group("subject"),
        source_text=chunk.text,
        source_id=chunk.source_id,
        generator="rule",
    )


def _leading_named_candidate(candidates: list[tuple[re.Match[str], str]]) -> tuple[re.Match[str], str] | None:
    """Prefer a leading named concept over a repeated generic noun later in a sentence."""
    if not candidates:
        return None

    first_match, first_word = candidates[0]
    if first_word[0].isupper() and first_word.casefold() not in GENERIC_CONCEPTS:
        return first_match, first_word
    return None


def _cloze_card(sentence: str, chunk: SourceChunk) -> Flashcard | None:
    if EXISTENTIAL_FACT_PATTERN.match(sentence):
        return None

    candidates: list[tuple[re.Match[str], str]] = []
    for match in re.finditer(r"\b[A-Za-z][A-Za-z'-]*\b", sentence):
        word = match.group(0)
        if len(word) < 4 or word.lower() in STOP_WORDS:
            continue
        candidates.append((match, word))

    if not candidates:
        return None

    match, word = _leading_named_candidate(candidates) or max(candidates, key=lambda candidate: len(candidate[1]))
    front = f"{sentence[:match.start()]}_______{sentence[match.end():]}"
    return Flashcard(
        front=front,
        back=word,
        source_text=chunk.text,
        source_id=chunk.source_id,
        generator="rule",
        kind="cloze",
    )


def _label_question(label: str) -> str:
    cleaned = label.rstrip("?").strip()
    if cleaned.lower().startswith(tuple(QUESTION_STARTERS)):
        return f"{cleaned}?"
    if cleaned[0].isdigit() or cleaned.lower().startswith(("types of", "examples of")):
        return f"What are {cleaned}?"
    return f"What is {cleaned}?"


def _sentence_source(chunk: SourceChunk, sentence: str, number: int) -> SourceChunk:
    return SourceChunk(f"{chunk.source_id}:sentence-{number}", sentence, "paragraph")


def generate_rule_candidates(chunks: list[SourceChunk]) -> RuleGenerationResult:
    """Classify rule cards by confidence and retain facts rules cannot express well."""
    result = RuleGenerationResult()
    for chunk in chunks:
        if chunk.kind == "labeled" and chunk.label:
            result.high_confidence.append(
                Flashcard(
                    front=_label_question(chunk.label),
                    back=chunk.text.rstrip("."),
                    source_text=chunk.text,
                    source_id=chunk.source_id,
                    generator="rule",
                )
            )
            continue

        sentences = split_sentences(chunk.text)
        index = 0
        while index < len(sentences):
            sentence = sentences[index]
            sentence_chunk = _sentence_source(chunk, sentence, index + 1)
            if _is_question(sentence) and index + 1 < len(sentences) and not _is_question(sentences[index + 1]):
                answer = sentences[index + 1]
                qa_chunk = SourceChunk(
                    f"{chunk.source_id}:qa-{index + 1}",
                    f"{sentence}\n{answer}",
                    "paragraph",
                )
                result.high_confidence.append(
                    Flashcard(
                        front=sentence.rstrip() if sentence.endswith("?") else f"{sentence}?",
                        back=answer.rstrip("."),
                        source_text=qa_chunk.text,
                        source_id=qa_chunk.source_id,
                        generator="rule",
                    )
                )
                index += 2
                continue

            card = _definition_card(sentence, sentence_chunk) or _group_identity_card(sentence, sentence_chunk)
            if card:
                result.high_confidence.append(card)
            else:
                card = _cloze_card(sentence, sentence_chunk)
                if card:
                    result.low_confidence.append(card)
                else:
                    result.unresolved.append(sentence_chunk)
            index += 1
    return result


def generate_rule_cards(chunks: list[SourceChunk]) -> list[Flashcard]:
    """Backward-compatible deterministic card generation for rules-only mode."""
    return generate_rule_candidates(chunks).all_rule_cards
