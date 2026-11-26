"""Fail-safe model-runner spy used under the names claude and codex."""

import os


with open(os.environ["SPY_FILE"], "a", encoding="utf-8") as stream:
    stream.write("called\n")
