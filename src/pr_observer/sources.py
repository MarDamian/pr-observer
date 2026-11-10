"""Where the diff comes from: a file, stdin, a git range or a GitHub pull request."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


class SourceError(Exception):
    pass


def _run(cmd: list[str]) -> str:
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    except FileNotFoundError as exc:
        raise SourceError(f"'{cmd[0]}' is not installed or not on PATH.") from exc
    if proc.returncode != 0:
        raise SourceError(proc.stderr.strip() or f"{' '.join(cmd)} failed")
    return proc.stdout


def from_file(path: str) -> str:
    if path == "-":
        return sys.stdin.read()
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise SourceError(f"Cannot read {path}: {exc.strerror}") from exc


def from_git(base: str | None) -> str:
    """Changes on this branch since `base`, or uncommitted changes when no base is given."""
    if subprocess.run(
        ["git", "rev-parse", "--verify", "-q", "HEAD"], capture_output=True
    ).returncode:
        _run(["git", "rev-parse", "--git-dir"])  # raises the real error outside a repository
        raise SourceError("This repository has no commits yet. Commit first, or pass --diff.")
    target = f"{base}...HEAD" if base else "HEAD"
    return _run(["git", "diff", "--no-color", "--no-ext-diff", target])


def from_pull_request(number: int, repo: str | None) -> str:
    cmd = ["gh", "pr", "diff", str(number), "--color", "never"]
    if repo:
        cmd += ["--repo", repo]
    return _run(cmd)
