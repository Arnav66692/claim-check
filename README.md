# claim-check

A Claude Code hook that catches false "done" claims. When an agent says it
created a file, ran a command, or made the tests pass, claim-check verifies the
claim against the real state of the repo and the real command log. If the claim
is false, the run is blocked or warned. If the claim holds, claim-check stays
silent.

## Why

Agents sometimes report success they did not earn. They say the tests pass when
the last run failed. They say a file was created when it was not. claim-check
turns those claims into checks.

## Design rules

- Precision first. A false block is worse than a missed claim.
- Every check is deterministic. No LLM calls, no model as judge, anywhere.
- Fail open. Any error inside a hook exits 0 so a user session is never broken.

## How it works

Two hooks do the work.

- `tool/hooks/log_command.py` runs on every Bash command, on success and on
  failure. It appends one record per command to a session scoped log in the
  temp directory.
- `tool/hooks/verify.py` runs on Stop. It reads the last assistant message,
  extracts claims with regex rules, and runs a deterministic check per claim.

The verifier reads the claim text from the `last_assistant_message` field in the
Stop payload. It only reads the transcript file when that field is missing.

## Results

Each check returns one of four results.

- SUPPORTED. The claim holds. Silent.
- REFUTED. The claim is false. Blocks on a block tier rule, warns on a warn tier rule.
- WARN. The claim could not be confirmed. Always warns.
- UNVERIFIED. No way to check here, for example no git repo. Silent.

## Rules

| Rule | Tier | Check |
| --- | --- | --- |
| tests_pass | block | a pass claim matches a real passing command run |
| ran_named_command | block | a named command in backticks actually ran and passed |
| created_file | block | a created or written file exists on disk |
| deleted_file | warn | a deleted file is really gone |
| updated_all_occurrences | warn | no occurrences of the symbol remain in git grep |
| added_test | warn | a changed file looks like a test file |

## Install in another project

1. Copy the `tool` folder into the target project at `.claude/claim-check`.
2. Merge `tool/settings.snippet.json` into the project `.claude/settings.json`.

The snippet points the hooks at `.claude/claim-check/hooks`. The repo copy in
`.claude/settings.json` points at `tool/hooks` so claim-check runs on its own
development.

## Settings

Defaults live in `verify.py`. Override them in `tool/claims.toml`. Keep
`strict_unverified` false to hold the precision first rule.

## Tests

```
python3 -m venv .venv
.venv/bin/python -m pip install pytest
.venv/bin/python -m pytest -q
```

## Benchmark

`bench/` holds the skeleton for measuring how often agents make unsupported
claims. The claim extractor and checks in `tool/` are the benchmark labeling
pipeline. The benchmark reuses them. It does not build a second labeler. See
`CLAUDE.md` for that rule.
