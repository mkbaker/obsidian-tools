#!/usr/bin/env python3
"""Shared git helpers for the vault repo."""

import subprocess
from pathlib import Path

ARCHIVE_DIR = "4 ARCHIVE"


def is_repo(vault_path):
    return (vault_path / ".git").exists()


def _run(args, vault_path):
    return subprocess.run(
        ["git", "-C", str(vault_path)] + args,
        capture_output=True, text=True
    )


def changed_md_files(vault_path):
    """Modified + untracked .md files, per git status (includes archived notes). None if not a repo.

    A note moved to the archive with a plain file move (not `git mv`) shows up as a
    deleted old path plus an untracked new path — git doesn't correlate those into a
    rename. Match them by filename so the note surfaces once, at its archived path,
    instead of looking deleted.
    """
    if not is_repo(vault_path):
        return None
    result = _run(["status", "--porcelain", "--", "*.md"], vault_path)
    if result.returncode != 0:
        return None

    entries = []
    archived_names = set()
    for line in result.stdout.splitlines():
        code = line[:2]
        path_str = line[3:]
        if " -> " in path_str:
            path_str = path_str.split(" -> ", 1)[1]
        path_str = path_str.strip('"')
        entries.append((code, path_str))
        if code.strip() == "??" and ARCHIVE_DIR in Path(path_str).parts:
            archived_names.add(Path(path_str).name)

    files = []
    for code, path_str in entries:
        path = Path(path_str)
        if (code.strip() == "D" and path.name in archived_names
                and ARCHIVE_DIR not in path.parts):
            continue
        files.append(vault_path / path)
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
