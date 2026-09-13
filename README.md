This is a capstone project to prepare myself for university and review the Python language.

This FlashcardGenerator intended to accept user's notes and convert them into flashcards ready for export. This system uses both code algorithm and AI detection.

The AI used for this project is the "gemini-2.5-flash"

How to use:
    Ensure the virture environment is properly selected with all the required packages installed.
    Run the main file "FlashcardGenerator.py" and follow the terminal prompt
    The program should automatically create a flashcard file ready for export.


Setup code:
    pip install -r requirements.txt
    python -m nltk.downloader punkt punkt_tab
    SSL_CERT_FILE=$(python -m certifi) python -m nltk.downloader punkt punkt_tab
