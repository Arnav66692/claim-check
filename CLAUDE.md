# claim-check

A Claude Code hook that catches false "done" claims, plus a benchmark skeleton.

## Key rule for the benchmark

The tool's claim extractor and checks are the benchmark's labeling pipeline.
Reuse them. Do not build a second labeler. The rules and checks in
`tool/hooks/verify.py` decide whether a claim is SUPPORTED, REFUTED, WARN, or
UNVERIFIED. The benchmark in `bench/` imports that same logic to label captured
sessions. A second labeler would drift from the tool and make the numbers lie.

## Design rules

- Precision first. A false block is worse than a missed claim.
- Every check is deterministic. No LLM calls, no model as judge, anywhere.
- Fail open. Any error inside a hook exits 0 so a user session is never broken.
- The verifier reads claim text from the `last_assistant_message` field in the
  Stop payload. It only reads the transcript file when that field is missing.

## Writing style

Short sentences. Periods and commas only. No em-dashes, no semicolons. Banned
words: leverage, tapestry, foster, delve, seamless, robust, game-changer.

## Layout

- `tool/hooks/log_command.py` logs every Bash command for the session.
- `tool/hooks/verify.py` is the Stop hook that checks claims.
- `tool/claims.toml` overrides the defaults.
- `tests/test_verify.py` is the test suite.
- `bench/` is the benchmark skeleton. Capture, label, analyze.
- `paper/` holds the writeup outline and related work.

## Tests

```
python3 -m pytest -q
```

## Keeping the graph current

If a graphify graph exists, run `graphify update .` after code changes.
