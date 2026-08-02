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