"""Data structures shared by parsing, generation, and export."""

from dataclasses import dataclass
from typing import Literal


ChunkKind = Literal["labeled", "paragraph"]
CardKind = Literal["basic", "cloze"]
GeneratorName = Literal["rule", "flan"]


@dataclass(frozen=True, slots=True)
class SourceChunk:
    """A self-contained portion of the user's notes."""

    source_id: str
    text: str
    kind: ChunkKind
    label: str | None = None


@dataclass(frozen=True, slots=True)
class Flashcard:
    """A card with enough provenance to review model output later."""

    front: str
    back: str
    source_text: str
    source_id: str
    generator: GeneratorName
    kind: CardKind = "basic"
