"""Unified diff parsing and rendering.

The parser tracks the line counts from each hunk header, so a removed line whose
content starts with "-- " is never mistaken for a file header.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from fnmatch import fnmatch
from pathlib import PurePosixPath

HUNK_RE = re.compile(r"^@@ -\d+(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")

SKIP_DIRS = {"node_modules", "vendor", "dist", "build", ".venv", "__pycache__", "target"}
SKIP_NAMES = (
    "*.lock",
    "package-lock.json",
    "pnpm-lock.yaml",
    "*.min.js",
    "*.min.css",
    "*.map",
    "*.snap",
    "*_pb2.py",
    "*.pb.go",
    "*.generated.*",
    "*.svg",
)


@dataclass
class Line:
    kind: str  # "+", "-" or " "
    new_no: int | None
    text: str


@dataclass
class Hunk:
    header: str
    lines: list[Line] = field(default_factory=list)


@dataclass
class FileDiff:
    path: str
    old_path: str | None = None
    hunks: list[Hunk] = field(default_factory=list)
    is_binary: bool = False
    is_deleted: bool = False

    @property
    def commentable_lines(self) -> set[int]:
        """New-side line numbers that appear in the diff (added or context)."""
        return {ln.new_no for h in self.hunks for ln in h.lines if ln.new_no is not None}

    @property
    def skip_reason(self) -> str | None:
        if self.is_binary:
            return "binary"
        if self.is_deleted:
            return "deleted"
        if not self.hunks:
            return "no content changes"
        p = PurePosixPath(self.path)
        if SKIP_DIRS.intersection(p.parts[:-1]) or any(fnmatch(p.name, pat) for pat in SKIP_NAMES):
            return "generated or vendored"
        return None


def _clean_path(raw: str) -> str | None:
    path = raw.split("\t", 1)[0].strip()
    if path == "/dev/null":
        return None
    if path[:2] in ("a/", "b/"):
        path = path[2:]
    return path


def parse_diff(text: str) -> list[FileDiff]:
    files: list[FileDiff] = []
    cur: FileDiff | None = None
    hunk: Hunk | None = None
    old_left = new_left = new_no = 0

    for raw in text.splitlines():
        if hunk is not None and (old_left > 0 or new_left > 0):
            if raw.startswith("\\"):
                continue
            tag, body = (raw[:1] or " "), raw[1:]
            if tag == "+":
                hunk.lines.append(Line("+", new_no, body))
                new_no += 1
                new_left -= 1
            elif tag == "-":
                hunk.lines.append(Line("-", None, body))
                old_left -= 1
            else:
                hunk.lines.append(Line(" ", new_no, body))
                new_no += 1
                new_left -= 1
                old_left -= 1
            continue

        hunk = None
        if raw.startswith("diff --git "):
            cur = FileDiff(path=raw.rsplit(" b/", 1)[-1])
            files.append(cur)
        elif raw.startswith("--- "):
            if cur is None or cur.hunks:  # plain `diff -u` output has no "diff --git" line
                cur = FileDiff(path="")
                files.append(cur)
            cur.old_path = _clean_path(raw[4:])
        elif cur is None:
            continue
        elif raw.startswith("+++ "):
            new_path = _clean_path(raw[4:])
            if new_path is None:
                cur.is_deleted = True
                cur.path = cur.old_path or cur.path
            else:
                cur.path = new_path
        elif raw.startswith("rename to "):
            cur.path = raw[len("rename to ") :]
        elif raw.startswith("deleted file mode"):
            cur.is_deleted = True
        elif raw.startswith(("Binary files ", "GIT binary patch")):
            cur.is_binary = True
        elif m := HUNK_RE.match(raw):
            old_left = int(m.group(1) or 1)
            new_no = int(m.group(2))
            new_left = int(m.group(3) or 1)
            hunk = Hunk(header=raw)
            cur.hunks.append(hunk)

    return files


def render_file(f: FileDiff) -> str:
    """Render a file's hunks with explicit new-side line numbers for the model."""
    out = [f"### {f.path}"]
    for h in f.hunks:
        out.append(h.header)
        for ln in h.lines:
            num = f"{ln.new_no:>5}" if ln.new_no is not None else "     "
            out.append(f"{ln.kind}{num} | {ln.text}")
    return "\n".join(out)
