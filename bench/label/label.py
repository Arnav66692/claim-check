"""Benchmark phase 2: label.

Label claims by reusing the tool's checks. This phase imports the claim
extractor and the checks from tool/hooks/verify.py and runs them over each
captured session. The result per claim is SUPPORTED, REFUTED, WARN, or
UNVERIFIED, the same labels the live hook produces.

Do not build a second labeler. The tool is the labeling pipeline. See CLAUDE.md.

Status: stub. The wiring to the capture output is not implemented yet.
"""

# The intended import once capture output exists.
# from tool.hooks.verify import evaluate, load_settings


def label_session(*args, **kwargs):
    raise NotImplementedError("label phase not implemented yet")
