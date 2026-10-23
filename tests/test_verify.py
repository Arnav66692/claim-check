import json, os, re, subprocess, sys, tempfile, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
VERIFY = ROOT / "tool" / "hooks" / "verify.py"
LOGGER = ROOT / "tool" / "hooks" / "log_command.py"
SID = "TESTSESSION"


def _log_path(sid):
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", sid)[:200]
    return os.path.join(tempfile.gettempdir(), "claim-check-%s.commands.jsonl" % safe)


def run_verify(payload):
    p = subprocess.run([sys.executable, str(VERIFY)], input=json.dumps(payload),
                       capture_output=True, text=True)
    return p.returncode, p.stdout.strip()


def write_log(sid, records):
    with open(_log_path(sid), "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")


def make_repo(tmp_path):
    import subprocess as sp
    d = tmp_path / "proj"
    d.mkdir()
    (d / "app.py").write_text("def handler():\n    return OldName()\n")
    sp.run(["git", "init", "-q"], cwd=d)
    sp.run(["git", "config", "user.email", "t@t.t"], cwd=d)
    sp.run(["git", "config", "user.name", "t"], cwd=d)
    sp.run(["git", "add", "-A"], cwd=d)
    sp.run(["git", "commit", "-qm", "init"], cwd=d)
    return d


def test_block_when_tests_claimed_pass_but_failed(tmp_path):
    d = make_repo(tmp_path)
    write_log(SID, [{"command": "pytest -q", "status": "fail"}])
    rc, out = run_verify({"hook_event_name": "Stop", "session_id": SID,
                          "cwd": str(d), "last_assistant_message": "Done. All tests pass now."})
    assert rc == 0
    assert '"decision": "block"' in out
    assert "pytest" in out


def test_silent_when_tests_actually_passed(tmp_path):
    d = make_repo(tmp_path)
    write_log(SID, [{"command": "pytest -q", "status": "ok"}])
    rc, out = run_verify({"hook_event_name": "Stop", "session_id": SID,
                          "cwd": str(d), "last_assistant_message": "Done. All tests pass now."})
    assert out == ""


def test_block_created_file_absent(tmp_path):
    d = make_repo(tmp_path)
    write_log(SID, [])
    rc, out = run_verify({"hook_event_name": "Stop", "session_id": SID,
                          "cwd": str(d), "last_assistant_message": "I created config.py with the loader."})
    assert '"decision": "block"' in out
    assert "config.py" in out


def test_silent_created_file_present(tmp_path):
    d = make_repo(tmp_path)
    (d / "config.py").write_text("x = 1\n")
    write_log(SID, [])
    rc, out = run_verify({"hook_event_name": "Stop", "session_id": SID,
                          "cwd": str(d), "last_assistant_message": "I created config.py with the loader."})
    assert out == ""


def test_warn_unverified_pass(tmp_path):
    d = make_repo(tmp_path)
    write_log(SID, [])
    rc, out = run_verify({"hook_event_name": "Stop", "session_id": SID,
                          "cwd": str(d), "last_assistant_message": "Done. All tests pass."})
    assert '"systemMessage"' in out
    assert '"decision"' not in out


def test_warn_all_occurrences_remaining(tmp_path):
    d = make_repo(tmp_path)
    write_log(SID, [])
    rc, out = run_verify({"hook_event_name": "Stop", "session_id": SID,
                          "cwd": str(d), "last_assistant_message": "I renamed all occurrences of OldName to NewName."})
    assert '"systemMessage"' in out
    assert "OldName" in out


def test_no_false_positive_on_plain_message(tmp_path):
    d = make_repo(tmp_path)
    write_log(SID, [])
    rc, out = run_verify({"hook_event_name": "Stop", "session_id": SID,
                          "cwd": str(d), "last_assistant_message": "I refactored the handler and added comments."})
    assert out == ""


def test_malformed_input_does_not_crash():
    p = subprocess.run([sys.executable, str(VERIFY)], input="not json",
                       capture_output=True, text=True)
    assert p.returncode == 0


def test_logger_writes_ok_and_fail():
    sid = "LOGTEST"
    path = _log_path(sid)
    if os.path.exists(path):
        os.remove(path)
    subprocess.run([sys.executable, str(LOGGER)],
                   input=json.dumps({"hook_event_name": "PostToolUse", "session_id": sid,
                                     "tool_input": {"command": "pytest -q"}}), text=True)
    subprocess.run([sys.executable, str(LOGGER)],
                   input=json.dumps({"hook_event_name": "PostToolUseFailure", "session_id": sid,
                                     "tool_input": {"command": "pytest -q"}, "error": "exit 1"}), text=True)
    lines = open(path, encoding="utf-8").read().strip().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["status"] == "ok"
    assert json.loads(lines[1])["status"] == "fail"


def test_unrelated_success_cannot_erase_failed_test_evidence(tmp_path):
    d = make_repo(tmp_path)
    write_log(SID, [{"command": "pytest -q", "status": "fail"},
                    {"command": "make clean", "status": "ok"}])
    _, out = run_verify({"session_id": SID, "cwd": str(d),
                         "last_assistant_message": "All tests pass."})
    assert json.loads(out)["decision"] == "block"


def test_non_verification_commands_never_support_test_claim(tmp_path):
    d = make_repo(tmp_path)
    for command in ["echo pytest", "printf 'pytest'", "make clean", "pytest || true",
                    "pytest; echo done", "pytest | tee results.txt", "pytest --collect-only",
                    "pytest --version", "npm test -- --listTests", "pytest --fixtures -q", "go test -list .", "go test -n ./...", "pytest --setup-only"]:
        write_log(SID, [{"command": command, "status": "ok"}])
        _, out = run_verify({"session_id": SID, "cwd": str(d),
                             "last_assistant_message": "All tests pass."})
        assert "systemMessage" in json.loads(out), command


def test_named_command_requires_exact_argv(tmp_path):
    d = make_repo(tmp_path)
    write_log(SID, [{"command": "echo pytest -q", "status": "ok"}])
    _, out = run_verify({"session_id": SID, "cwd": str(d),
                         "last_assistant_message": "I ran `pytest -q`."})
    assert "systemMessage" in json.loads(out)


def test_build_claim_cannot_use_test_evidence(tmp_path):
    d = make_repo(tmp_path)
    write_log(SID, [{"command": "pytest", "status": "ok"}])
    _, out = run_verify({"session_id": SID, "cwd": str(d),
                         "last_assistant_message": "The build passes."})
    assert "systemMessage" in json.loads(out)


def test_direct_python_module_command_supports_tests(tmp_path):
    d = make_repo(tmp_path)
    write_log(SID, [{"command": ".venv/bin/python -m pytest -q", "status": "ok"}])
    _, out = run_verify({"session_id": SID, "cwd": str(d),
                         "last_assistant_message": "All tests pass."})
    assert not out


def test_build_dry_run_cannot_support_build_claim(tmp_path):
    d = make_repo(tmp_path)
    write_log(SID, [{"command": "go build -n ./...", "status": "ok"}])
    _, out = run_verify({"session_id": SID, "cwd": str(d),
                         "last_assistant_message": "The build passes."})
    assert "systemMessage" in json.loads(out)
