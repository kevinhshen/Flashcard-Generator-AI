import unittest

from flashcard_generator.parser import segment_chunks
from flashcard_generator.rules import generate_rule_cards


class RuleGenerationTests(unittest.TestCase):
    def test_label_uses_a_grammatical_question(self) -> None:
        cards = generate_rule_cards(segment_chunks("Photosynthesis: Plants convert light into chemical energy."))
        self.assertEqual(cards[0].front, "What is Photosynthesis?")

    def test_fact_creates_a_cloze_card(self) -> None:
        cards = generate_rule_cards(segment_chunks("Photosynthesis converts light energy into chemical energy."))
        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0].kind, "cloze")
        self.assertEqual(cards[0].back, "Photosynthesis")

    def test_cloze_prefers_a_substantive_word_over_an_auxiliary(self) -> None:
        cards = generate_rule_cards(segment_chunks("This has been known as the monetary unit assumption."))
        self.assertEqual(cards[0].back, "assumption")

    def test_existence_statement_without_a_specific_fact_is_skipped(self) -> None:
        cards = generate_rule_cards(segment_chunks("There are several types of external users of accounting information."))
        self.assertEqual(cards, [])

    def test_cloze_prefers_a_leading_named_concept(self) -> None:
        sentence = "Investors, who are owners of a business, use accounting information to make decisions."
        cards = generate_rule_cards(segment_chunks(sentence))
        self.assertEqual(cards[0].back, "Investors")
        self.assertIn("_______, who are owners", cards[0].front)

    def test_group_identity_becomes_a_direct_retrieval_card(self) -> None:
        sentence = "Investors and creditors are the main external users of accounting information, but other users exist."
        cards = generate_rule_cards(segment_chunks(sentence))
        self.assertEqual(cards[0].front, "What are the main external users of accounting information?")
        self.assertEqual(cards[0].back, "Investors and creditors")

    def test_question_uses_the_next_sentence_from_its_own_chunk(self) -> None:
        cards = generate_rule_cards(segment_chunks("What is an atom? An atom is the smallest unit of matter."))
        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0].front, "What is an atom?")
        self.assertEqual(cards[0].back, "An atom is the smallest unit of matter")

    def test_multiple_chunks_do_not_duplicate_cards(self) -> None:
        text = "Photosynthesis converts light energy.\n\nGravity: A force that attracts objects.\n\nAtoms contain protons."
        cards = generate_rule_cards(segment_chunks(text))
        self.assertEqual(len(cards), 3)
        self.assertEqual(len({card.front for card in cards}), 3)

    def test_heading_before_a_label_does_not_create_a_cloze_card(self) -> None:
        text = "Business structures\nSole proprietorship: A business owned by one person."
        cards = generate_rule_cards(segment_chunks(text))
        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0].front, "What is Sole proprietorship?")
