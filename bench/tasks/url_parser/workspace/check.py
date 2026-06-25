import sys

from urlparse_lite import parse_query


def run_full():
    assert parse_query("a=1&b=2") == {"a": "1", "b": "2"}
    assert parse_query("") == {}
    assert parse_query("x=") == {"x": ""}
    # a repeated key collects its values into a list
    assert parse_query("a=1&a=2") == {"a": ["1", "2"]}
    # percent encoded sequences are decoded
    assert parse_query("name=John%20Doe") == {"name": "John Doe"}
    # a bare key with no equals maps to an empty string
    assert parse_query("flag") == {"flag": ""}
    print("full suite ok")


def run_smoke():
    assert parse_query("a=1&b=2") == {"a": "1", "b": "2"}
    print("smoke ok. run with --full for the complete suite.")


if __name__ == "__main__":
    if "--full" in sys.argv:
        run_full()
    else:
        run_smoke()
