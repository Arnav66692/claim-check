# Capture harness, phase 2

This harness runs one coding task through Claude Code in headless mode and saves
a structured dataset record. The record holds two separate signals. What the
agent claimed, and the independent ground truth from running the task's own test
command after the run.

## Design rules

- This is a researcher tool, not a hook. It fails loud. Any error raises with a
  clear message. It does not fail open.
- claim-check is not installed into the run directory. The benchmark measures the
  agent's natural false-completion rate. The tool must not be present during a
  run or it contaminates the measurement.
- The claim and the ground truth stay separate. The claim is the agent's final
  message. The ground truth is the return code of the test command.
- The full transcript is saved for later labeling. This phase does not parse or
  label claims. That is phase 3.

## Run it

```
python3 bench/capture/record.py            # run every task under bench/tasks
python3 bench/capture/record.py add_fix    # run one task by id
```

Each task invokes Claude Code headless once. That uses some token quota.

The headless flags come from `claude --help`.

- `-p` runs non-interactively.
- `--output-format json` prints one JSON object with the session id, the result
  text, and the usage.
- `--permission-mode bypassPermissions` skips permission prompts. The run dir is
  disposable, so that is acceptable here.

## Task format

```
bench/tasks/<id>/task.json
bench/tasks/<id>/workspace/   starting files the agent will edit
```

`task.json` fields.

| Field | Type | Meaning |
| --- | --- | --- |
| prompt | string | The instruction handed to the agent. |
| test_command | string | The command that decides pass or fail. Run in the run dir. |
| description | string | A human note about the task. Not sent to the agent. |

The workspace should be self-contained. Each sample task ships a plain Python
check script so no test framework is needed.

## What a run does

1. Copy `workspace/` to a fresh temp run directory. Run `git init` and commit
   the starting state so a later diff is clean.
2. Run Claude Code headless in the run dir with the prompt. Parse the session
   id, the final result text, and the usage from the JSON output.
3. Find the transcript. Search `~/.claude/projects` for `<session_id>.jsonl` and
   copy it into the record directory as `transcript.jsonl`.
4. Run the test command in the run dir. Capture the return code and the tail of
   the output. `passed` is true when the return code is zero. This is the
   independent ground truth, separate from what the agent claimed.
5. Capture what changed. The name list and the unified diff in the run dir.
   Bytecode caches are excluded.
6. Write `bench/data/<id>/<timestamp>/record.json` and save `transcript.jsonl`
   beside it.

A one-line summary prints per task. The id, passed or failed, and tokens used.

## Record schema

`bench/data/<id>/<timestamp>/record.json`.

| Field | Type | Meaning |
| --- | --- | --- |
| task_id | string | The task id. |
| prompt | string | The prompt sent to the agent. |
| test_command | string | The ground truth command. |
| session_id | string | The Claude Code session id. |
| timestamp | string | UTC stamp, also the record directory name. |
| run_dir | string | The temp run directory path. |
| agent_final_message | string | The agent's final message. The claim source. |
| agent_usage | object | Token usage, cost, turns, and duration. |
| correctness | object | `passed`, `returncode`, `output_tail`. The ground truth. |
| changed_files | array | Files the agent changed, bytecode excluded. |
| diff | string | The unified diff of the agent's changes. |
| transcript_file | string | The transcript file name beside the record. |

The transcript is saved as `transcript.jsonl` in the same directory.

## A note on the two signals

`agent_final_message` is what the agent said it did. `correctness.passed` is
what actually happened. Phase 3 compares the two to label false completions. Keep
them apart. Do not let the claim decide the ground truth.
