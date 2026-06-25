import os

checks = [
    ("settings.py", "DEBUG = False"),
    ("logging.conf", "[loggers]"),
    (".env.example", "API_KEY="),
    ("Makefile", "run:"),
]
for path, needle in checks:
    assert os.path.isfile(path), "missing file: " + path
    with open(path, encoding="utf-8") as handle:
        text = handle.read()
    assert needle in text, "missing marker in " + path

print("templates ok")
