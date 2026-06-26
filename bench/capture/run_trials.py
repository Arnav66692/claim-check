#!/usr/bin/env python3
"""Repeated-trials runner. Experimental arm one.

Run the existing recorder N times per task under the same full tool access
condition as the single pass. The only change from that run is sample size.

CLI.
    python3 bench/capture/run_trials.py [N]

N defaults to 10. For every task in bench/tasks/manifest.json, this runs the
recorder N times and stores each trial under bench/data/<task_id>/<trial_index>/.

It is resumable. If a record for a (task, trial) already exists, the trial is
skipped, so an interrupted run can continue. It is resilient. If one trial
errors, it is logged and the batch continues. A running total_cost_usd is
printed as it goes. The model used per run is read back from the record.

The recorder is not modified. It writes to a timestamp directory, and this
runner moves that directory to the trial index directory.
"""

import glob
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DATA = REPO / "bench" / "data"
MANIFEST = REPO / "bench" / "tasks" / "manifest.json"
RECORDER = REPO / "bench" / "capture" / "record.py"

# The recorder finds the agent with shutil.which("claude"). On a machine where a
# Claude Code auto-update is mid-flight, the claude symlink can be missing or the
# freshly written binary can be unsigned, so the OS kills it. We resolve a
# working binary ourselves and put a claude symlink on the recorder's PATH. This
# does not touch the global install. Candidates are tried in order and each must
# actually run before it is accepted.
CLAUDE_CANDIDATE_GLOBS = [
    "/opt/homebrew/lib/node_modules/@anthropic-ai/.claude-code-*/bin/claude.exe",
    "/opt/homebrew/lib/node_modules/@anthropic-ai/claude-code/node_modules/@anthropic-ai/claude-code-darwin-arm64/claude",
    str(Path.home() / ".bun/install/cache/@anthropic-ai/claude-agent-sdk-*/claude"),
]


def _runs(path):
    try:
        proc = subprocess.run([path, "--version"], capture_output=True, text=True, timeout=30)
        return proc.returncode == 0
    except Exception:
        return False


def resolve_claude():
    """Return the path to a claude binary that actually runs."""
    found = shutil.which("claude")
    if found and _runs(found):
        return found
    for pattern in CLAUDE_CANDIDATE_GLOBS:
        for cand in sorted(glob.glob(pattern)):
            if os.access(cand, os.X_OK) and _runs(cand):
                return cand
    raise SystemExit(
        "No working claude binary found. The CLI may be mid-update or unsigned. "
        "Restore a working claude, then rerun. This runner is resumable, so it "
        "picks up where it stopped."
    )


def make_claude_bindir(claude_bin):
    """Put a claude symlink in a private bin dir, outside the repo."""
    bindir = Path(tempfile.gettempdir()) / "claim-check-bin"
    bindir.mkdir(parents=True, exist_ok=True)
    link = bindir / "claude"
    if link.is_symlink() or link.exists():
        link.unlink()
    link.symlink_to(claude_bin)
    return bindir


def claude_version(claude_bin):
    try:
        proc = subprocess.run([claude_bin, "--version"], capture_output=True, text=True, timeout=30)
        return (proc.stdout.strip() or proc.stderr.strip()) or "unknown"
    except Exception:
        return "unknown"


def write_meta(target, claude_bin, version):
    """Record the resolved binary and version beside the record at run time.

    This is only ever written for a trial that just ran. A trial without a
    meta file is treated as not version verifiable. We do not stamp a version
    onto an already-finished trial, since that would manufacture agreement and
    hide version drift instead of catching it."""
    meta = {
        "claude_path": str(claude_bin),
        "claude_version": version,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    (target / "meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")


def child_dirs(path):
    if not path.is_dir():
        return set()
    return {c.name for c in path.iterdir() if c.is_dir()}


def main(argv):
    n = int(argv[1]) if len(argv) > 1 else 10
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    tasks = manifest["tasks"]
    DATA.mkdir(parents=True, exist_ok=True)

    claude_bin = resolve_claude()
    version = claude_version(claude_bin)
    bindir = make_claude_bindir(claude_bin)
    child_env = dict(os.environ)
    child_env["PATH"] = str(bindir) + os.pathsep + child_env.get("PATH", "")
    print("using claude: %s" % claude_bin, flush=True)
    print("claude version: %s" % version, flush=True)

    running_cost = 0.0
    new_cost = 0.0
    ran = 0
    skipped = 0
    errors = 0
    models = {}
    start = time.time()

    # Trial major order. Each trial index sweeps every task, so an interrupted
    # run still spreads coverage across all tasks.
    for trial in range(n):
        idx = "%02d" % trial
        for task in tasks:
            tid = task["id"]
            task_dir = DATA / tid
            target = task_dir / idx
            if (target / "record.json").exists() and (target / "meta.json").exists():
                rec = json.loads((target / "record.json").read_text(encoding="utf-8"))
                running_cost += rec["agent_usage"].get("total_cost_usd") or 0.0
                skipped += 1
                print("skip  %-18s trial %s  exists  running=$%.4f" % (tid, idx, running_cost), flush=True)
                continue

            before = child_dirs(task_dir)
            t0 = time.time()
            proc = subprocess.run(
                [sys.executable, str(RECORDER), tid],
                cwd=str(REPO),
                capture_output=True,
                text=True,
                env=child_env,
            )
            dt = time.time() - t0
            after = child_dirs(task_dir)
            fresh = [task_dir / name for name in (after - before)]
            made = [d for d in fresh if (d / "record.json").exists()]

            if proc.returncode != 0 or not made:
                errors += 1
                for d in fresh:
                    shutil.rmtree(d, ignore_errors=True)
                print(
                    "ERROR %-18s trial %s  rc=%d (%.0fs): %s"
                    % (tid, idx, proc.returncode, dt, proc.stderr.strip()[-200:]),
                    flush=True,
                )
                continue

            made[0].rename(target)
            write_meta(target, claude_bin, version)
            rec = json.loads((target / "record.json").read_text(encoding="utf-8"))
            cost = rec["agent_usage"].get("total_cost_usd") or 0.0
            running_cost += cost
            new_cost += cost
            ran += 1
            for model_name in (rec["agent_usage"].get("model_usage") or {}):
                models[model_name] = models.get(model_name, 0) + 1
            print(
                "run   %-18s trial %s  passed=%s cost=$%.4f (%.0fs)  running=$%.4f"
                % (tid, idx, rec["correctness"]["passed"], cost, dt, running_cost),
                flush=True,
            )

    elapsed = time.time() - start
    print()
    print("DONE n=%d  ran=%d skipped=%d errors=%d  elapsed=%.0fs" % (n, ran, skipped, errors, elapsed))
    print("new cost this session=$%.4f  total dataset cost=$%.4f" % (new_cost, running_cost))
    print("models seen:", models)
    if errors:
        print("note: %d trials errored. Rerun the same command to fill the gaps." % errors)


if __name__ == "__main__":
    main(sys.argv)
