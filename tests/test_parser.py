import unittest

from flashcard_generator.parser import clean_text, segment_chunks


class ParserTests(unittest.TestCase):
    def test_clean_text_keeps_a_single_blank_line_between_paragraphs(self) -> None:
        text = "First sentence.  \r\n\r\n\r\nSecond sentence."
        self.assertEqual(clean_text(text), "First sentence.\n\nSecond sentence.")

    def test_segment_chunks_keeps_labelled_and_paragraph_content_separate(self) -> None:
        text = "Intro fact.\n\nTerm: A definition.\nIt continues.\n\nOutro fact."
        chunks = segment_chunks(text)

        self.assertEqual([chunk.kind for chunk in chunks], ["paragraph", "labeled", "paragraph"])
        self.assertEqual(chunks[1].label, "Term")
        self.assertEqual(chunks[1].text, "A definition. It continues.")
        self.assertEqual(chunks[2].text, "Outro fact.")

    def test_numbered_label_is_recognized(self) -> None:
        chunks = segment_chunks("3 types of accountant: Public, private, and government.")
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0].label, "3 types of accountant")

    def test_document_and_uppercase_section_headings_are_not_source_chunks(self) -> None:
        chunks = segment_chunks("Building statements\nRECOGNITION AND MEASUREMENT\nOnly measurable events are recorded.")
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0].text, "Only measurable events are recorded.")

    def test_title_like_heading_before_a_label_is_not_source_content(self) -> None:
        text = "Business structures\nSole proprietorship: A business owned by one person."
        chunks = segment_chunks(text)

        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0].label, "Sole proprietorship")
        self.assertEqual(chunks[0].text, "A business owned by one person.")

    def test_sentence_before_a_label_remains_a_paragraph(self) -> None:
        text = "Businesses create value.\nBusiness type: A way a business is organized."
        chunks = segment_chunks(text)

        self.assertEqual([chunk.kind for chunk in chunks], ["paragraph", "labeled"])
        self.assertEqual(chunks[0].text, "Businesses create value.")
