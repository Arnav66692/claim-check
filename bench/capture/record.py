#!/usr/bin/env python3
"""Benchmark phase 2: capture.

Run one coding task through Claude Code in headless mode and save a structured
dataset record. The record holds what the agent claimed and, separately, the
independent ground truth from running the task's own test command.

This is a researcher tool, not a hook. It fails loud. Any error raises with a
clear message. It does not fail open.

The benchmark measures the agent's natural false-completion rate. So claim-check
is not installed into the run directory. The tool must not be present during a
run or it contaminates the measurement.

Two separate signals.
- The claim. The agent's final message, taken from the headless JSON output.
- The ground truth. The return code of the task's test command, run after the
  agent finishes, independently.

The full session transcript is saved for later labeling. This phase does not
parse or label claims. That is phase 3.

CLI.
    python3 bench/capture/record.py [task_id]

With no task id, every task under bench/tasks runs.

Headless flags. Confirmed with `claude --help`.
- -p / --print runs non-interactively and prints the result.
- --output-format json prints one JSON object with session_id, result, usage.
- --permission-mode bypassPermissions skips permission prompts. The run dir is
  disposable, so this is acceptable here.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
TASKS_DIR = REPO_ROOT / "bench" / "tasks"
DATA_DIR = REPO_ROOT / "bench" / "data"

AGENT_TIMEOUT_SECONDS = 900
TEST_TIMEOUT_SECONDS = 120
OUTPUT_TAIL_CHARS = 4000


class CaptureError(RuntimeError):
    """Raised when the capture cannot complete. Fail loud."""


def run_checked(args, cwd, what):
    """Run a command and raise with a clear message on failure."""
    proc = subprocess.run(args, cwd=str(cwd), capture_output=True, text=True)
    if proc.returncode != 0:
        raise CaptureError(
            "%s failed with code %d.\nargs: %s\nstderr:\n%s"
            % (what, proc.returncode, " ".join(args), proc.stderr.strip())
        )
    return proc.stdout


def find_claude():
    path = shutil.which("claude")
    if not path:
        raise CaptureError(
            "claude executable not found on PATH. Install Claude Code first."
        )
    return path


def discover_tasks(task_id):
    if not TASKS_DIR.is_dir():
        raise CaptureError("tasks directory not found at %s" % TASKS_DIR)
    if task_id:
        task_dir = TASKS_DIR / task_id
        if not (task_dir / "task.json").is_file():
            raise CaptureError("no task.json for task id '%s' under %s" % (task_id, TASKS_DIR))
        return [task_dir]
    tasks = sorted(p for p in TASKS_DIR.iterdir() if (p / "task.json").is_file())
    if not tasks:
        raise CaptureError("no tasks found under %s" % TASKS_DIR)
    return tasks


def load_task(task_dir):
    task_file = task_dir / "task.json"
    try:
        data = json.loads(task_file.read_text(encoding="utf-8"))
    except Exception as exc:
        raise CaptureError("could not parse %s: %s" % (task_file, exc))
    for field in ("prompt", "test_command", "description"):
        value = data.get(field)
        if not isinstance(value, str) or not value.strip():
            raise CaptureError("task %s is missing a non-empty '%s' field" % (task_dir.name, field))
    workspace = task_dir / "workspace"
    if not workspace.is_dir():
        raise CaptureError("task %s has no workspace directory" % task_dir.name)
    return data, workspace


def make_run_dir(task_id, workspace):
    """Copy the workspace to a fresh temp dir, then commit the starting state."""
    run_dir = Path(tempfile.mkdtemp(prefix="claim-check-run-%s-" % task_id))
    for item in workspace.iterdir():
        dest = run_dir / item.name
        if item.is_dir():
            shutil.copytree(item, dest)
        else:
            shutil.copy2(item, dest)
    git_id = ["-c", "user.email=bench@claim-check", "-c", "user.name=claim-check-bench"]
    run_checked(["git", "init", "-q"], run_dir, "git init")
    run_checked(["git"] + git_id + ["add", "-A"], run_dir, "git add starting state")
    run_checked(["git"] + git_id + ["commit", "-qm", "starting state"], run_dir, "git commit starting state")
    return run_dir


def invoke_agent(claude, prompt, run_dir):
    """Run Claude Code headless and parse the JSON output."""
    args = [
        claude,
        "-p",
        prompt,
        "--output-format",
        "json",
        "--permission-mode",
        "bypassPermissions",
    ]
    try:
        proc = subprocess.run(
            args,
            cwd=str(run_dir),
            capture_output=True,
            text=True,
            timeout=AGENT_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        raise CaptureError("claude run timed out after %d seconds" % AGENT_TIMEOUT_SECONDS)
    if proc.returncode != 0:
        raise CaptureError(
            "claude exited with code %d.\nstderr:\n%s" % (proc.returncode, proc.stderr.strip())
        )
    out = proc.stdout.strip()
    if not out:
        raise CaptureError("claude produced no stdout. stderr:\n%s" % proc.stderr.strip())
    try:
        data = json.loads(out)
    except json.JSONDecodeError as exc:
        raise CaptureError("could not parse claude JSON output: %s\nfirst 500 chars:\n%s" % (exc, out[:500]))
    if data.get("is_error"):
        raise CaptureError("claude reported an error result: %s" % data.get("result", "")[:500])
    session_id = data.get("session_id")
    if not session_id:
        raise CaptureError("claude JSON output had no session_id")
    final_message = data.get("result")
    if final_message is None:
        raise CaptureError("claude JSON output had no result field")
    raw_usage = data.get("usage") or {}
    # Keep every token category separate. The Phase 4 token sub-study needs real
    # per-category numbers. A single sum would mix cache reads with new tokens.
    usage = {
        "input_tokens": raw_usage.get("input_tokens"),
        "output_tokens": raw_usage.get("output_tokens"),
        "cache_creation_input_tokens": raw_usage.get("cache_creation_input_tokens"),
        "cache_read_input_tokens": raw_usage.get("cache_read_input_tokens"),
        "total_cost_usd": data.get("total_cost_usd"),
        "num_turns": data.get("num_turns"),
        "duration_ms": data.get("duration_ms"),
        "model_usage": data.get("modelUsage") or data.get("model_usage"),
        "raw_usage": raw_usage,
    }
    return session_id, final_message, usage


def io_tokens(usage):
    """Input plus output tokens, new tokens only, for the one-line summary.

    Cache reads are not added in. The stored record keeps every category."""
    new_in = usage.get("input_tokens") or 0
    out = usage.get("output_tokens") or 0
    return new_in + out


def find_transcript(session_id):
    """Find <session_id>.jsonl under ~/.claude/projects."""
    projects = Path.home() / ".claude" / "projects"
    if not projects.is_dir():
        raise CaptureError("projects directory not found at %s" % projects)
    matches = list(projects.rglob("%s.jsonl" % session_id))
    if not matches:
        raise CaptureError(
            "transcript %s.jsonl not found under %s. Session persistence may be off."
            % (session_id, projects)
        )
    return matches[0]


def run_test(test_command, run_dir):
    """Run the task's test command as the independent ground truth."""
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    try:
        proc = subprocess.run(
            test_command,
            cwd=str(run_dir),
            capture_output=True,
            text=True,
            shell=True,
            env=env,
            timeout=TEST_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        raise CaptureError("test command timed out after %d seconds" % TEST_TIMEOUT_SECONDS)
    combined = (proc.stdout or "") + (proc.stderr or "")
    tail = combined[-OUTPUT_TAIL_CHARS:]
    return proc.returncode, tail


def capture_diff(run_dir):
    """Stage the agent's changes and return the name list and unified diff."""
    git_id = ["-c", "user.email=bench@claim-check", "-c", "user.name=claim-check-bench"]
    run_checked(["git"] + git_id + ["add", "-A"], run_dir, "git add after run")
    exclude = [":(exclude)**/__pycache__/**", ":(exclude)**/*.pyc"]
    names = run_checked(
        ["git", "diff", "--cached", "--name-only", "--", "."] + exclude,
        run_dir,
        "git diff name list",
    )
    diff = run_checked(
        ["git", "-c", "core.quotepath=false", "diff", "--cached", "--", "."] + exclude,
        run_dir,
        "git diff unified",
    )
    changed_files = [line for line in names.splitlines() if line.strip()]
    return changed_files, diff


def process_task(claude, task_dir):
    task_id = task_dir.name
    task, workspace = load_task(task_dir)
    prompt = task["prompt"]
    test_command = task["test_command"]

    run_dir = make_run_dir(task_id, workspace)
    session_id, final_message, usage = invoke_agent(claude, prompt, run_dir)

    transcript_src = find_transcript(session_id)

    returncode, output_tail = run_test(test_command, run_dir)
    passed = returncode == 0

    changed_files, diff = capture_diff(run_dir)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    record_dir = DATA_DIR / task_id / timestamp
    record_dir.mkdir(parents=True, exist_ok=True)

    transcript_name = "transcript.jsonl"
    shutil.copy2(transcript_src, record_dir / transcript_name)

    record = {
        "task_id": task_id,
        "prompt": prompt,
        "test_command": test_command,
        "session_id": session_id,
        "timestamp": timestamp,
        "run_dir": str(run_dir),
        "agent_final_message": final_message,
        "agent_usage": usage,
        "correctness": {
            "passed": passed,
            "returncode": returncode,
            "output_tail": output_tail,
        },
        "changed_files": changed_files,
        "diff": diff,
        "transcript_file": transcript_name,
    }
    record_path = record_dir / "record.json"
    record_path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")

    return {
        "task_id": task_id,
        "passed": passed,
        "io_tokens": io_tokens(usage),
        "total_cost_usd": usage.get("total_cost_usd"),
        "record_path": record_path,
    }


def main(argv):
    task_id = argv[1] if len(argv) > 1 else None
    claude = find_claude()
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    tasks = discover_tasks(task_id)
    summaries = []
    for task_dir in tasks:
        summary = process_task(claude, task_dir)
        summaries.append(summary)
        cost = summary["total_cost_usd"]
        cost_str = "$%.4f" % cost if isinstance(cost, (int, float)) else "n/a"
        print(
            "%s: %s, %d in+out tokens, %s"
            % (
                summary["task_id"],
                "passed" if summary["passed"] else "failed",
                summary["io_tokens"],
                cost_str,
            )
        )
    return summaries


if __name__ == "__main__":
    main(sys.argv)
