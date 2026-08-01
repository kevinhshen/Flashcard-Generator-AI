# AI Flashcard Generater

## Purpose
This is a capstone project to prepare myself for university. The purpose of this project is for me to review the Python language, and learn how to work in a team project environment, which include proper documentation, the use of Github and many more.

## Current status
The previous version generated flashcard based on purely code algorithm.
I am currently working on the AI part, and the program is temperary not working.


This FlashcardGenerator intended to accept user's notes and convert them into flashcards ready for export. This system uses both code algorithm and AI detection.

The AI used for this project is the "gemini-2.5-flash"

## How it currently works
Ensure the virture environment is properly selected with all the required packages installed.
Run the main file "FlashcardGenerator.py" and follow the terminal prompt
The program should automatically create a flashcard file ready for export.

## Run the project
1. Create and activate the virtual environment.
2. Run `pip install -r requirements.txt`.
3. Copy `.env.example` to `.env`.
4. Add `GEMINI_API_KEY` to `.env`.
5. Run:

```powershell
python main.py

