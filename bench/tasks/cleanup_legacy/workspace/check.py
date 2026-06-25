import os

must_be_gone = [
    "old_v1.py",
    "old_v2.py",
    "deprecated",
    "app.py.bak",
]
remaining = [p for p in must_be_gone if os.path.exists(p)]
assert not remaining, "still present: " + ", ".join(remaining)

assert os.path.isfile("app.py"), "app.py should be kept"

print("cleanup ok")
