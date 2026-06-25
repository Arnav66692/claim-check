# Benchmark tasks

Each task is a small repo and a prompt that pushes an agent toward a claim. A
good task makes it tempting to say "done" before the work holds. Examples.

- Make the failing test pass. The agent may claim a pass without rerunning.
- Create a config file. The agent may claim a file it never wrote.
- Rename a symbol everywhere. The agent may miss some occurrences.
- Delete a dead module. The agent may claim a delete that did not happen.

Each task folder should hold the starting repo state and the prompt. The
capture phase runs the agent on the task. The label phase scores the claims.
The analyze phase reports the unsupported-claim rate across tasks.

Status: no tasks yet. This folder is the place to add them.
