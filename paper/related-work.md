# Related work

How claim-check sits next to prior work on agent honesty and outcome checking.

## MIRAGE-Bench

Work on measuring agent hallucination in interactive settings. It studies when
an agent asserts things that are not grounded in the environment. claim-check
narrows that idea to one high value case, the done claim, and checks it with
deterministic rules instead of a judge model.

## Over-mocked tests study

Work showing that agents and developers write tests that mock so much they pass
without testing real behavior. A green test suite stops being evidence. This
motivates the tests_pass rule. A pass claim should map to a real command run,
and over-mocking is a known way a pass can mislead.

## Tool-use hallucination literature

Work on agents that report tool results that never happened, or misread tool
output. The command log in claim-check is a direct answer. The hook records what
the Bash tool actually ran and whether it failed, so a claim about a command can
be checked against the record rather than the agent's memory.

## Outcome-verification patterns

Work on verifying the outcome of an action rather than trusting the actor.
Examples include checking the filesystem after a write and rerunning a build
after a fix. claim-check applies this pattern at the Stop boundary. It reads the
final message, then verifies the outcomes the message claims.

## Where claim-check differs

- It runs as a hook, not as a separate agent. It fails open by design.
- It uses no model as judge. Every check is deterministic and cheap.
- It tunes for precision. A false block is worse than a missed claim.
