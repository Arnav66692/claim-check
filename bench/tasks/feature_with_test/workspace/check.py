import os

from slugify import slugify

assert slugify("Hello World") == "hello-world"
assert slugify("  Trim  Me  ") == "trim-me"
# non ASCII letters and punctuation are removed
assert slugify("Caf\u00e9 & Bar!") == "caf-bar"

assert os.path.isfile("test_slugify.py"), "no test file test_slugify.py"
with open("test_slugify.py", encoding="utf-8") as handle:
    test_src = handle.read()
assert "slugify" in test_src, "test file does not use slugify"
assert test_src.count("assert") >= 2, "test file needs at least two assertions"

print("feature and test ok")
