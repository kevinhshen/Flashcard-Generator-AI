import unittest
from dataclasses import replace
from unittest.mock import patch

from flashcard_generator.cli import _review_cards
from flashcard_generator.models import Flashcard


class ReviewTests(unittest.TestCase):
    def setUp(self) -> None:
        self.rule_card = Flashcard("What is an atom?", "The smallest unit of matter.", "source", "rule-1", "rule")
        self.model_card = Flashcard("What is a thing?", "A thing.", "source", "flan-1", "flan")

    def test_default_review_skips_rule_cards_and_can_discard_model_cards(self) -> None:
        with patch("builtins.input", side_effect=["d"]) as prompt:
            cards = _review_cards([self.rule_card, self.model_card], review_all=False, regenerate=None)

        self.assertEqual(cards, [self.rule_card])
        self.assertEqual(prompt.call_count, 1)

    def test_regeneration_replaces_a_model_card_then_returns_to_review(self) -> None:
        replacement = replace(self.model_card, front="What does the source say?", back="A clearer answer.")
        with patch("builtins.input", side_effect=["r", ""]):
            cards = _review_cards(
                [self.model_card],
                review_all=False,
                regenerate=lambda card: (replacement, None),
            )

        self.assertEqual(cards, [replacement])
