# Planning

1. Accept user input as a bulk
2. Clean up bulk text
3. Pass entire bulk text into extract_flashcard
    1. Identify label/definition blocks
        1. Labeled block -> make a feinition card directly
        2. Paragraph block -> split into sentences
    2. Classify each sentences
        1. question + next sentence -> question/answer card
        2. definition sentence -> definition card
        3. fact sentence -> cloze card or skip

Bugs/Features:

Idea: track every source passage
    Every piece of the notes gets one of two outcomes: a card, or an exclusion.
        Card: the source text supports a flashcard.
        Exclusion: the source text is left out, and the reason is recorded.
    Each passage of the notes gets one outcome.
    Included: the passage backs a fact, which appears on a card.
    Excluded: the passage is non-study material, with a reason.
    Passages can be partly used, so track quotes or sentences, not whole chunks.


Feature Ideas:
    Auto search youtube video for explanations on related topics (since already using gemini)
