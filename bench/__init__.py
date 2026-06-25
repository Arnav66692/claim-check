"""claim-check benchmark.

Three phases. Capture a Claude Code session. Label the claims by reusing the
tool's checks. Analyze the unsupported-claim rate with confidence intervals.

The labeling phase imports the tool's claim extractor and checks. It does not
build a second labeler. See CLAUDE.md.
"""
