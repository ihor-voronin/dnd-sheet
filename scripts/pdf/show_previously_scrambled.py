import json
import pathlib

rows = [
    json.loads(line)
    for line in pathlib.Path(r"C:\Users\User\Desktop\work_docs\dnd-sheet\content\compendium\gotg\item.jsonl")
    .read_text(encoding="utf-8")
    .splitlines()
]
for name in (
    "Crown of the Wrath Bringer",
    "Delver's Claws",
    "Shield of the Blazing Dreadnought",
    "Longbow of the Healing Hearth",
):
    record = next(row for row in rows if row["name_en"] == name)
    print("###", name, record["data"])
    print(record["text_en"])
    print()
