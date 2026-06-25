import importlib

with open("app.py", encoding="utf-8") as handle:
    text = handle.read()
assert "foo" not in text, "old name foo still present"

app = importlib.import_module("app")
assert app.bar() == 42
assert app.run() == 42
print("control rename ok")
