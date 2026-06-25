import glob
import importlib

for path in glob.glob("**/*.py", recursive=True):
    if path == "check.py":
        continue
    with open(path, encoding="utf-8") as handle:
        text = handle.read()
    assert "compute_total" not in text, "old name still present in " + path

pricing = importlib.import_module("services.pricing")
assert pricing.calculate_total([10, 20, 30]) == 60

summary = importlib.import_module("reports.summary")
assert summary.summarize([{"items": [1, 2]}, {"items": [3]}]) == 6

print("rename function ok")
