import glob
import importlib

for path in glob.glob("**/*.py", recursive=True):
    if path == "check.py":
        continue
    with open(path, encoding="utf-8") as handle:
        text = handle.read()
    assert "DEFAULT_TIMEOUT" not in text, "old name still present in " + path

config = importlib.import_module("config")
assert config.TIMEOUT_SECONDS == 30

session = importlib.import_module("net.session")
assert session.make_session() == {"timeout": 30}

print("rename constant ok")
