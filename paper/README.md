# Paper outline

A short writeup of claim-check and the benchmark.

## Working title

Catching false done claims in coding agents with deterministic checks.

## Sections

1. Problem. Agents report success they did not earn. They claim passing tests,
   created files, and finished renames that do not hold.
2. Approach. Extract claims from the final message with regex rules. Check each
   claim against the repo and the command log. No model as judge. Every check is
   deterministic.
3. Precision first. A false block is worse than a missed claim. We tune for low
   false blocks and accept some missed claims.
4. Benchmark. Capture sessions on tasks that tempt premature claims. Label with
   the same checks the hook uses. Report the unsupported-claim rate with
   confidence intervals.
5. Results. To be filled once the benchmark runs.
6. Limitations. Regex extraction misses paraphrased claims. Some claims cannot
   be checked locally and stay unverified.
7. Related work. See related-work.md.

## Claim

A small deterministic verifier cuts false done claims without breaking sessions,
because it fails open and tunes for precision.
