from dotenv import load_dotenv

load_dotenv()  # reads GEMINI_API_KEY from your .env file

from flashcard_generator.ai import generate_deck

notes = open("examples/sample_notes_4.txt", encoding="utf-8").read()
result = generate_deck(notes)
print(result["usage"])
print(len(result["cards"]), "cards")
