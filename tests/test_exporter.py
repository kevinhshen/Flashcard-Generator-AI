import csv
import tempfile
import unittest
from pathlib import Path

from flashcard_generator.exporter import export_anki_tsv
from flashcard_generator.models import Flashcard
from flashcard_generator.validation import validate_and_deduplicate


class ExporterTests(unittest.TestCase):
    def test_export_writes_anki_compatible_tab_separated_fields(self) -> None:
        card = Flashcard("What is gravity?", "A force", "source", "chunk-1", "rule")
        with tempfile.TemporaryDirectory() as directory:
            path = export_anki_tsv([card], Path(directory) / "cards.tsv")
            with path.open(encoding="utf-8", newline="") as output_file:
                self.assertEqual(list(csv.reader(output_file, delimiter="\t")), [["What is gravity?", "A force"]])

    def test_validation_deduplicates_normalized_cards(self) -> None:
        first = Flashcard("What is gravity?", "A force", "source", "chunk-1", "rule")
        duplicate = Flashcard(" What is gravity? ", "A  force", "source", "chunk-2", "rule")
        accepted, rejected = validate_and_deduplicate([first, duplicate])
        self.assertEqual(len(accepted), 1)
        self.assertEqual(rejected[0][1], "duplicate card")
