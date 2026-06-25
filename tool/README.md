# claim-check tool

This folder is the distributable hook. Copy it into another project to run
claim-check there.

## Files

- `hooks/log_command.py`. Logs every Bash command for the session. Bind it to
  PostToolUse and PostToolUseFailure on the Bash tool.
- `hooks/verify.py`. The Stop hook. Reads the last assistant message and checks
  each claim against the repo and the command log.
- `claims.toml`. Optional settings that override the defaults in `verify.py`.
- `settings.snippet.json`. The hook wiring for a project that installs this tool
  into `.claude/claim-check`.

## Install

1. Copy this folder into the target project at `.claude/claim-check`. After the
   copy you should have `.claude/claim-check/hooks/verify.py`.
2. Merge `settings.snippet.json` into the project `.claude/settings.json`.

The snippet points the hooks at `$CLAUDE_PROJECT_DIR/.claude/claim-check/hooks`.

## Settings

Defaults live in `verify.py`. Override them in `claims.toml`.

- `strict_unverified`. Treat an unverifiable pass claim as a block. Default
  false. Keep it false to hold the precision first rule.
- `max_evidence`. Cap on evidence lines per result. Default 8.
- `test_command_patterns`. Substrings that mark a command as a test or build run.
- `stopwords`. Symbols too generic to verify with git grep.

## What gets checked

- A pass claim must match a real command run that did not fail.
- A named command in backticks must appear in the command log and not have failed.
- A created or written file must exist on disk.
- A deleted file must be gone.
- An "all occurrences" claim must leave no matches in git grep.
- An "added a test" claim must show a changed test file in git status.

## Output

- Block tier refuted claim. Prints a block decision and exits 0.
- Any warning. Prints a system message and exits 0.
- Otherwise. Exits 0 with no output.
