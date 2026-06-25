#!/usr/bin/env python3
"""claim-check command logger.

Bound to PostToolUse and PostToolUseFailure on the Bash tool. Reads the hook
JSON from stdin and appends one record per command to a session scoped log.
Always exits 0. Every error is swallowed so a user session is never broken.
"""

import json
import os
import re
import sys
import tempfile
import time


def _safe_session_id(session_id):
    """Keep only filename safe characters and cap the length."""
    return re.sub(r"[^A-Za-z0-9_.-]", "_", str(session_id))[:200]


def _log_path(session_id):
    safe = _safe_session_id(session_id)
    return os.path.join(tempfile.gettempdir(), "claim-check-%s.commands.jsonl" % safe)


def main():
    raw = sys.stdin.read()
    payload = json.loads(raw)

    session_id = payload.get("session_id", "unknown")
    tool_input = payload.get("tool_input") or {}
    command = tool_input.get("command", "")
    event = payload.get("hook_event_name", "")
    status = "ok" if event == "PostToolUse" else "fail"

    record = {
        "command": command,
        "status": status,
        "ts": time.time(),
    }
    error = payload.get("error")
    if error is not None:
        record["error"] = error

    path = _log_path(session_id)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
