import importlib
import os

required = [
    "notes/__init__.py",
    "notes/models.py",
    "notes/storage.py",
    "notes/api.py",
    "notes/README.md",
]
missing = [p for p in required if not os.path.isfile(p)]
assert not missing, "missing files: " + ", ".join(missing)

notes = importlib.import_module("notes")
note = notes.create_note("buy milk")
assert note.text == "buy milk"
assert note.id is not None

print("scaffold ok")
