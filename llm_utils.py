#!/usr/bin/env python3
"""Shared LLM logic: calls Claude via the claude CLI."""

import os
import subprocess
import sys

DEFAULT_MODEL = "haiku"


def call_llm(prompt, use_sonnet=False, use_claude=False, ollama_model=None, model=None):
    """Call Claude CLI. Returns (text, model_label)."""
    model = model or DEFAULT_MODEL
    label = f"claude/{model}"
    print(f"  Using {label}")

    env = {**os.environ, "CLAUDE_CONFIG_DIR": os.path.expanduser("~/.claude-personal")}
    result = subprocess.run(
        [os.path.expanduser("~/.claude/local/claude"), "-p", prompt, "--model", model, "--no-session-persistence"],
        capture_output=True,
        text=True,
        env=env,
    )

    if result.returncode != 0:
        print(f"Error: claude CLI failed:\n{result.stderr}", file=sys.stderr)
        sys.exit(1)

    return result.stdout.strip(), label
