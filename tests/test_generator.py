from flashcard_generator.generator import clean_text, generate_local, parse_blocks


def test_clean_text_normalizes_lines_without_losing_paragraphs():
    raw = "Alpha  \r\n\r\n\r\n Beta \t value ."
    assert clean_text(raw) == "Alpha\n\nBeta value."


def test_labeled_block_includes_continuation_lines():
    blocks = parse_blocks("Photosynthesis: Converts light energy\ninto chemical energy.")
    assert blocks == [
        {
            "type": "labeled",
            "label": "Photosynthesis",
            "content": "Converts light energy into chemical energy.",
        }
    ]


def test_label_card_has_natural_grammar():
    cards = generate_local("Photosynthesis: A process used by plants.")
    assert cards[0].front == "What is Photosynthesis?"
    assert cards[0].back == "A process used by plants."


def test_question_is_paired_with_following_answer():
    cards = generate_local("Where is DNA stored? It is stored mainly in the nucleus.")
    assert cards[0].front == "Where is DNA stored?"
    assert cards[0].back == "It is stored mainly in the nucleus"


def test_definition_becomes_basic_card():
    cards = generate_local("Inertia is the tendency of an object to resist changes in motion.")
    assert cards[0].front == "Define Inertia."
    assert cards[0].back == "the tendency of an object to resist changes in motion"


def test_factual_sentence_becomes_source_grounded_cloze():
    cards = generate_local("Water freezes at 0 degrees Celsius under standard pressure.")
    assert cards[0].card_type == "cloze"
    assert cards[0].back == "0 degrees Celsius"
    assert "_____" in cards[0].front


def test_separate_paragraphs_do_not_duplicate_cards():
    notes = "Alpha is a first concept used for testing.\n\nBeta is a second concept used for testing."
    cards = generate_local(notes)
    assert [card.front for card in cards] == ["Define Alpha.", "Define Beta."]


def test_empty_input_returns_no_cards():
    assert generate_local("   ") == []


def test_does_not_blank_arbitrary_words():
    assert generate_local("asdf qwerty zxcvbn randomlongword blabla") == []


def test_does_not_invent_context_for_pronouns():
    assert generate_local("It is a special system.") == []


def test_maximum_can_exceed_100():
    notes = "\n\n".join(f"Concept {n}: Definition number {n}." for n in range(150))
    assert len(generate_local(notes, 150)) == 150
