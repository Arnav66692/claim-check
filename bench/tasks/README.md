# Benchmark tasks

This is the characterization task set for the claim-check benchmark.

## What this set is, and is not

These tasks are built to elicit false completion claims. They are not built to
estimate how often such claims happen in the wild. That is a deliberate design
choice. The goal is to see which claim types break and whether the deterministic
checks catch them. Read the results as a characterization, not as a natural rate.

The mechanism is structural, not a trick prompt. Each elicitation task makes the
work multi part, or makes verification awkward. An agent that does part of the
job and reports all of it, or skips a check and claims it passed, is acting
normally here, not being fooled.

## Two kinds of task

- Elicitation. Designed to induce a gap between the claim and the ground truth.
- Control. Simple and unambiguous. The agent should finish and report honestly.
  Controls are the false-positive guard for the whole experiment. If a control
  ever looks like a false claim, that is a bug to find.

## Claim types probed

Each task names one claim type from the tool in its `claim_target` field.

| claim_target | elicitation mechanism |
| --- | --- |
| tests_pass | the suite is split with no single runner, or the full run needs a non-obvious flag |
| updated_all_occurrences | the symbol lives in several files including one easy to miss |
| created_file | several files are requested and one is easy to forget |
| deleted_file | several files must go and one is easy to leave behind |
| added_test | the feature is the interesting part, so the test is the thing skipped |

## Task format

```
bench/tasks/<id>/task.json
bench/tasks/<id>/workspace/   starting files the agent will edit
```

`task.json` fields.

| Field | Type | Meaning |
| --- | --- | --- |
| prompt | string | The instruction handed to the agent. |
| test_command | string | The command that decides ground truth. Run in the run dir. |
| description | string | A human note on the task and its trap. Not sent to the agent. |
| claim_target | string | The claim type this task probes. |

Each task ships a plain-python check for ground truth, so no test framework is
needed. Most tasks use `check.py`. The split-suite task uses several files under
`tests/` plus a one-line runner in its `test_command`.

The agent never sees `task.json`. The capture harness copies only `workspace/`
into the run dir. So the prompt and the workspace files are all the agent gets.

## Manifest

`manifest.json` lists every task id, its `claim_target`, and whether it is an
elicitation or a control task. Phase 3 labeling reads it.

## Ground truth is separate from the claim

The `test_command` is the independent ground truth. It checks the full job. The
agent's final message is the claim. Phase 3 compares the two. The check never
reads the claim, and the claim never decides the ground truth.
