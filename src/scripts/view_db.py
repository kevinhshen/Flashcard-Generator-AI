import sqlite3
from pathlib import Path

DB = Path("data/recall_research.db")
QUERIES = Path("data/queries.sql")

SET_W = 5

conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)  # read-only: cannot change your data
conn.row_factory = sqlite3.Row

for query in QUERIES.read_text(encoding="utf-8").split(";"):

    if not query.strip():
        continue

    print("\n>>", " ".join(query.split())[:100])

    try:
        rows = conn.execute(query).fetchall()
    except sqlite3.Error as error:
        print("error:", error)
        continue

    if not rows:
        print("(no rows)")
        continue

    # print(" | ".join(rows[0].keys()))
    # for row in rows:
    #     print(" | ".join(str(value) for value in row))

    for word in rows[0].keys():
        print(f" | {word:<{SET_W}}", end="")
    print()

    for row in rows:
        for value in row:
            print(f" | {str(value):<{SET_W}}", end="")
        print()


conn.close()
