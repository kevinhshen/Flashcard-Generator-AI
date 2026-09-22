"""Backward-compatible launcher.

New users can run ``python run.py``. This file remains so existing shortcuts and
instructions continue to work.
"""

from flashcard_generator.web import run

if __name__ == "__main__":
    run()
