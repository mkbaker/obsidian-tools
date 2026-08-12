#!/usr/bin/env python3
"""Shared git helpers for the vault repo."""

import subprocess

ARCHIVE_DIR = "4 ARCHIVE"


def is_repo(vault_path):
    return (vault_path / ".git").exists()


def _run(args, vault_path):
    return subprocess.run(
        ["git", "-C", str(vault_path)] + args,
        capture_output=True, text=True
    )


def changed_md_files(vault_path):
    """Modified + untracked .md files outside the archive, per git status. None if not a repo."""
    if not is_repo(vault_path):
        return None
    result = _run(["status", "--porcelain", "--", "*.md"], vault_path)
    if result.returncode != 0:
        return None
    files = []
    for line in result.stdout.splitlines():
        path_str = line[3:].strip('"')
        path = vault_path / path_str
        if ARCHIVE_DIR in path.parts:
            continue
        files.append(path)
    return sorted(files)


def diff_or_content(path, vault_path):
    """(git diff HEAD text, True) for a tracked/modified file, else (full content, False)."""
    rel = path.relative_to(vault_path)
    status = _run(["status", "--porcelain", "--", str(rel)], vault_path)
    if status.stdout.startswith("??"):
        try:
            return path.read_text(encoding="utf-8"), False
        except IOError:
            return None, False
    diff = _run(["diff", "HEAD", "--", str(rel)], vault_path)
    return diff.stdout, True


def commit_all(vault_path, message):
    """Stage and commit everything in the vault. Returns True if a commit was made."""
    if not is_repo(vault_path):
        return False
    _run(["add", "-A"], vault_path)
    status = _run(["status", "--porcelain"], vault_path)
    if not status.stdout.strip():
        return False
    _run(["commit", "-m", message], vault_path)
    return True
