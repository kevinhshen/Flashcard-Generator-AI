"""Start the local Flashcard Generator web app."""

from flashcard_generator.web import create_app


if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=5000)
