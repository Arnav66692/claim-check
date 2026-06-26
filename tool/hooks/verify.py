#!/usr/bin/env python3
"""claim-check verifier.

The Stop hook. Reads the hook JSON from stdin, takes the last assistant
message, runs deterministic checks against the claims inside it, and either
blocks the run, warns, or stays silent.

Design rules.
- Precision first. A false block is worse than a missed claim.
- Every check is deterministic. No LLM calls anywhere.
- Fail open. Any error exits 0 so a user session is never broken.
"""

import json
import os
import re
import subprocess
import sys
import tempfile

try:
    import tomllib
except ImportError:  # Python < 3.11
    tomllib = None


# Result statuses.
SUPPORTED = "SUPPORTED"
REFUTED = "REFUTED"
WARN = "WARN"
UNVERIFIED = "UNVERIFIED"


DEFAULT_SETTINGS = {
    "strict_unverified": False,
    "max_evidence": 8,
    "test_command_patterns": [
        "npm test",
        "pytest",
        "go test",
        "cargo test",
        "jest",
        "vitest",
        "make",
    ],
    "stopwords": [
        "config",
        "data",
        "value",
        "result",
        "test",
        "file",
        "path",
        "name",
        "type",
        "error",
        "main",
        "index",
    ],
}


# Rule definitions. Each rule has a name, a tier ("block" or "warn"), the name
# of the check to run, a regex, and the capture group index (or None).
RULES = [
    {
        "name": "tests_pass",
        "tier": "block",
        "check": "command_pass",
        "regex": r"all tests pass|tests passing|the build passes|everything passes",
        "capture": None,
    },
    {
        "name": "ran_named_command",
        "tier": "block",
        "check": "command_pass",
        "regex": r"\bran\s+`([^`]+)`",
        "capture": 1,
    },
    {
        "name": "created_file",
        "tier": "block",
        "check": "file_created",
        "regex": r"\b(?:created|wrote|generated)\b\s+(?:[A-Za-z0-9_'\"-]+\s+){0,3}([A-Za-z0-9_./~-]+\.[A-Za-z0-9_]+)",
        "capture": 1,
    },
    {
        "name": "deleted_file",
        "tier": "warn",
        "check": "file_deleted",
        "regex": r"\b(?:deleted|removed)\b\s+(?:[A-Za-z0-9_'\"-]+\s+){0,3}([A-Za-z0-9_./~-]+\.[A-Za-z0-9_]+)",
        "capture": 1,
    },
    {
        "name": "updated_all_occurrences",
        "tier": "warn",
        "check": "all_occurrences",
        "regex": r"\b(?:updated|renamed)\s+all\s+occurrences\s+of\s+([A-Za-z_][A-Za-z0-9_]*)",
        "capture": 1,
    },
    {
        "name": "added_test",
        "tier": "warn",
        "check": "test_added",
        "regex": r"added a test|wrote tests",
        "capture": None,
    },
]


TEST_PATH_MARKERS = ("test_", "_test.", ".test.", ".spec.", "tests/", "spec/")


def safe_session_id(session_id):
    return re.sub(r"[^A-Za-z0-9_.-]", "_", str(session_id))[:200]


def log_path(session_id):
    safe = safe_session_id(session_id)
    return os.path.join(tempfile.gettempdir(), "claim-check-%s.commands.jsonl" % safe)


def load_settings():
    """Defaults overridable by tool/claims.toml."""
    settings = dict(DEFAULT_SETTINGS)
    if tomllib is None:
        return settings
    config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "claims.toml")
    try:
        with open(config_path, "rb") as f:
            data = tomllib.load(f)
        override = data.get("settings", data)
        for key in settings:
            if key in override:
                settings[key] = override[key]
    except Exception:
        pass
    return settings


def load_log(session_id):
    entries = []
    try:
        with open(log_path(session_id), "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entries.append(json.loads(line))
                except Exception:
                    continue
    except Exception:
        pass
    return entries


def get_message(payload):
    """Use last_assistant_message. Fall back to the transcript only if absent."""
    message = payload.get("last_assistant_message")
    if message:
        return message
    transcript_path = payload.get("transcript_path")
    if not transcript_path:
        return ""
    return read_transcript_last_assistant(transcript_path)


def read_transcript_last_assistant(transcript_path):
    """Best effort fallback. Return the last assistant text block."""
    last_text = ""
    try:
        with open(transcript_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except Exception:
                    continue
                if rec.get("role") != "assistant" and rec.get("type") != "assistant":
                    continue
                content = rec.get("content")
                if content is None and isinstance(rec.get("message"), dict):
                    content = rec["message"].get("content")
                text = _extract_text(content)
                if text:
                    last_text = text
    except Exception:
        return last_text
    return last_text


def _extract_text(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
            elif isinstance(block, str):
                parts.append(block)
        return "".join(parts)
    return ""


# ----- Checks. Each returns (status, evidence). -----


def check_command_pass(captured, entries, settings, cwd):
    captured = (captured or "").strip()
    if captured:
        matched = [e for e in entries if captured in (e.get("command") or "")]
        label = "`%s`" % captured
    else:
        patterns = settings["test_command_patterns"]
        matched = [
            e
            for e in entries
            if any(pat in (e.get("command") or "") for pat in patterns)
        ]
        label = "tests"
    if not matched:
        evidence = "claimed %s passed but no matching command ran" % label
        if settings["strict_unverified"]:
            return REFUTED, evidence
        return WARN, evidence
    latest = matched[-1]
    if latest.get("status") == "fail":
        return REFUTED, "claimed %s passed but `%s` failed" % (label, latest.get("command") or "")
    return SUPPORTED, ""


def _resolve(path, cwd):
    if os.path.isabs(path):
        return path
    return os.path.join(cwd, path)


def check_file_created(path, entries, settings, cwd):
    resolved = _resolve(path, cwd)
    if os.path.exists(resolved):
        return SUPPORTED, ""
    return REFUTED, "claimed to create `%s` but it does not exist" % path


def check_file_deleted(path, entries, settings, cwd):
    resolved = _resolve(path, cwd)
    if not os.path.exists(resolved):
        return SUPPORTED, ""
    return REFUTED, "claimed to delete `%s` but it still exists" % path


def check_all_occurrences(symbol, entries, settings, cwd):
    symbol = symbol or ""
    if len(symbol) < 4 or symbol.lower() in set(settings["stopwords"]):
        return WARN, "claimed to update all occurrences of `%s`, too short or generic to verify" % symbol
    try:
        proc = subprocess.run(
            ["git", "grep", "-nFw", "--", symbol],
            cwd=cwd,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return UNVERIFIED, ""
    if proc.returncode == 0:
        lines = [l for l in proc.stdout.splitlines() if l.strip()]
        shown = lines[: settings["max_evidence"]]
        joined = "; ".join(shown)
        return REFUTED, "claimed to update all occurrences of `%s` but %d remain: %s" % (
            symbol,
            len(lines),
            joined,
        )
    if proc.returncode == 1:
        return SUPPORTED, ""
    return UNVERIFIED, ""


def check_test_added(captured, entries, settings, cwd):
    try:
        proc = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=cwd,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return WARN, "claimed to add tests but no test file changed"
    if proc.returncode != 0:
        return WARN, "claimed to add tests but no test file changed"
    changed = []
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        # Format is "XY path" with an optional rename "old -> new".
        parts = line.split(None, 1)
        path = parts[1] if len(parts) > 1 else line
        if "->" in path:
            path = path.split("->")[-1].strip()
        changed.append(path)
    for path in changed:
        low = path.lower()
        if any(marker in low for marker in TEST_PATH_MARKERS):
            return SUPPORTED, ""
    return WARN, "claimed to add tests but no test file changed"


CHECKS = {
    "command_pass": check_command_pass,
    "file_created": check_file_created,
    "file_deleted": check_file_deleted,
    "all_occurrences": check_all_occurrences,
    "test_added": check_test_added,
}


def find_claim_matches(message):
    """Detect completion claims in a message.

    Returns a list of (rule, match) for every rule regex that matches. This is
    claim-check's claim detection. It is the single source of truth, shared by
    the Stop hook here and the benchmark analysis, so both use one definition."""
    matches = []
    for rule in RULES:
        regex = re.compile(rule["regex"], re.IGNORECASE)
        for match in regex.finditer(message or ""):
            matches.append((rule, match))
    return matches


def claimed_done(message):
    """True if the message contains at least one completion claim."""
    return bool(find_claim_matches(message))


def evaluate(message, entries, settings, cwd):
    """Run every rule over the message. Return a list of result dicts."""
    results = []
    for rule, match in find_claim_matches(message):
        captured = None
        if rule["capture"] is not None:
            captured = match.group(rule["capture"])
        check = CHECKS[rule["check"]]
        status, evidence = check(captured, entries, settings, cwd)
        results.append(
            {
                "rule": rule["name"],
                "tier": rule["tier"],
                "status": status,
                "evidence": evidence,
            }
        )
    return results


def build_output(results):
    blocks = [r for r in results if r["tier"] == "block" and r["status"] == REFUTED]
    warns = [
        r
        for r in results
        if r["status"] == WARN or (r["tier"] == "warn" and r["status"] == REFUTED)
    ]
    if blocks:
        reason = "\n".join("- " + r["evidence"] for r in blocks)
        return {
            "decision": "block",
            "reason": reason,
            "hookSpecificOutput": {"hookEventName": "Stop"},
        }
    if warns:
        bullets = "\n".join("- " + r["evidence"] for r in warns)
        return {"systemMessage": "claim-check:\n" + bullets}
    return None


def main():
    raw = sys.stdin.read()
    payload = json.loads(raw)

    message = get_message(payload) or ""
    cwd = payload.get("cwd") or os.getcwd()
    session_id = payload.get("session_id", "unknown")

    settings = load_settings()
    entries = load_log(session_id)

    results = evaluate(message, entries, settings, cwd)
    output = build_output(results)
    if output is not None:
        sys.stdout.write(json.dumps(output))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
