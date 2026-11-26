import collections
import json
import pathlib

root = pathlib.Path(r"C:\Users\User\Desktop\work_docs\dnd-sheet\content\compendium")
total = 0
books = collections.Counter()
cats = collections.Counter()
for path in root.glob("*/*.jsonl"):
    rows = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    total += len(rows)
    books[path.parent.name] += len(rows)
    cats[path.stem] += len(rows)
print("records", total, "books", len(books), "gotg", books["gotg"])
print("categories", dict(sorted(cats.items(), key=lambda kv: -kv[1])))

gotg = pathlib.Path(r"C:\Users\User\Desktop\work_docs\dnd-sheet\content\compendium\gotg")
for path in sorted(gotg.glob("*.jsonl")):
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    for record in rows:
        assert record["text_en"].strip(), record["id"]
        assert "\ufffd" not in record["text_en"], record["id"]
    print(path.stem, len(rows), "ok")
