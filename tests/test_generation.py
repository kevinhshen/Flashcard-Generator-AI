import unittest

from flashcard_generator.generation import ModelGenerationResult, needs_model_polish, run_generation
from flashcard_generator.models import Flashcard, SourceChunk
from flashcard_generator.parser import segment_chunks
from flashcard_generator.rules import generate_rule_candidates


class FakeModelGenerator:
    def __init__(self) -> None:
        self.sources: list[SourceChunk] = []

    def generate(self, sources) -> ModelGenerationResult:
        self.sources = list(sources)
        cards = [
            Flashcard(
                front="What does the source describe?",
                back="A source fact",
                source_text=source.text,
                source_id=source.source_id,
                generator="flan",
            )
            for source in self.sources
        ]
        return ModelGenerationResult(cards=cards)


class PolishingFakeModelGenerator(FakeModelGenerator):
    def __init__(self) -> None:
        super().__init__()
        self.polish_requests: list[Flashcard] = []

    def improve(self, cards) -> ModelGenerationResult:
        self.polish_requests = list(cards)
        return ModelGenerationResult(
            cards=[
                Flashcard(
                    front="What are private accountants?",
                    back="Private accountants work for business.",
                    source_text=card.source_text,
                    source_id=card.source_id,
                    generator="flan",
                )
                for card in self.polish_requests
            ]
        )


class GenerationPipelineTests(unittest.TestCase):
    def test_rule_candidates_keep_uncertain_clozes_out_of_high_confidence(self) -> None:
        result = generate_rule_candidates(segment_chunks("Photosynthesis converts light energy."))
        self.assertEqual(result.high_confidence, [])
        self.assertEqual(len(result.low_confidence), 1)
        self.assertEqual(result.unresolved, [])

    def test_hybrid_keeps_high_confidence_rules_and_sends_only_uncertain_sources_to_model(self) -> None:
        chunks = segment_chunks("Atom: The smallest unit of matter.\n\nPhotosynthesis converts light energy.")
        model = FakeModelGenerator()

        report = run_generation(chunks, "hybrid", model)

        self.assertEqual(report.cards[0].front, "What is Atom?")
        self.assertEqual(report.cards[0].generator, "rule")
        self.assertEqual(len(model.sources), 1)
        self.assertEqual(model.sources[0].text, "Photosynthesis converts light energy.")
        self.assertEqual(len(report.cards), 2)

    def test_flan_mode_evaluates_each_paragraph_sentence(self) -> None:
        model = FakeModelGenerator()
        report = run_generation(
            segment_chunks("Plants need light. Plants make sugar."),
            "flan",
            model,
        )

        self.assertEqual([source.text for source in model.sources], ["Plants need light.", "Plants make sugar."])
        self.assertEqual(len(report.cards), 2)

    def test_auto_polish_rewrites_fragmentary_rule_answers_only(self) -> None:
        model = PolishingFakeModelGenerator()
        report = run_generation(segment_chunks("Private accountants: for business"), "hybrid", model)

        self.assertEqual(len(model.sources), 0)
        self.assertEqual(len(model.polish_requests), 1)
        self.assertEqual(report.cards[0].front, "What are private accountants?")
        self.assertEqual(report.cards[0].back, "Private accountants work for business.")
        self.assertEqual(report.cards[0].generator, "flan")

    def test_polish_detector_leaves_standalone_answers_alone(self) -> None:
        standalone = Flashcard("What is an atom?", "The smallest unit of matter.", "source", "source-1", "rule")
        fragment = Flashcard("What is Private accountants?", "for business", "source", "source-2", "rule")

        self.assertFalse(needs_model_polish(standalone))
        self.assertTrue(needs_model_polish(fragment))
