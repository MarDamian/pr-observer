"""Review pipeline: collect -> reviewers (in parallel) -> validate."""

from __future__ import annotations

import operator
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Annotated, TypedDict

from langgraph.graph import END, START, StateGraph

from pr_observer.agents.base import Reviewer
from pr_observer.diff import FileDiff, parse_diff, render_file
from pr_observer.schemas import Finding, ReviewResult, SkippedFile


@dataclass(frozen=True)
class Limits:
    max_files: int = 40
    max_chars: int = 120_000


class State(TypedDict, total=False):
    diff_text: str
    files: list[FileDiff]
    skipped: list[SkippedFile]
    rendered: str
    raw_findings: Annotated[list[Finding], operator.add]
    findings: list[Finding]
    dropped: int


def _collect(limits: Limits):
    def collect(state: State) -> State:
        files: list[FileDiff] = []
        skipped: list[SkippedFile] = []
        parts: list[str] = []
        used = 0
        for f in parse_diff(state["diff_text"]):
            reason = f.skip_reason
            if reason is None:
                text = render_file(f)
                if len(files) >= limits.max_files or used + len(text) > limits.max_chars:
                    reason = "over the size budget"
            if reason is not None:
                skipped.append(SkippedFile(path=f.path, reason=reason))
                continue
            files.append(f)
            parts.append(text)
            used += len(text)
        return {"files": files, "skipped": skipped, "rendered": "\n\n".join(parts)}

    return collect


def _review(reviewer: Reviewer):
    def review(state: State) -> State:
        if not state["rendered"]:
            return {"raw_findings": []}
        return {"raw_findings": reviewer.review(state["rendered"])}

    return review


def _validate(state: State) -> State:
    """Drop findings that point at a file or line the diff does not contain, then dedupe."""
    lines_by_file = {f.path: f.commentable_lines for f in state["files"]}
    kept: dict[tuple[str, int, str], Finding] = {}
    dropped = 0
    for finding in state.get("raw_findings", []):
        if finding.line not in lines_by_file.get(finding.file, ()):
            dropped += 1
            continue
        key = (finding.file, finding.line, finding.category)
        if key not in kept or finding.confidence > kept[key].confidence:
            kept[key] = finding
    findings = sorted(kept.values(), key=lambda f: (f.severity.rank, f.file, f.line))
    return {"findings": findings, "dropped": dropped}


def build_graph(reviewers: Sequence[Reviewer], limits: Limits | None = None):
    graph = StateGraph(State)
    graph.add_node("collect", _collect(limits or Limits()))
    graph.add_node("validate", _validate)
    graph.add_edge(START, "collect")
    for reviewer in reviewers:
        node = f"review_{reviewer.name}"
        graph.add_node(node, _review(reviewer))
        graph.add_edge("collect", node)
        graph.add_edge(node, "validate")
    graph.add_edge("validate", END)
    return graph.compile()


def run_review(
    diff_text: str,
    reviewers: Sequence[Reviewer],
    model_name: str,
    limits: Limits | None = None,
) -> ReviewResult:
    state = build_graph(reviewers, limits).invoke({"diff_text": diff_text})
    return ReviewResult(
        model=model_name,
        files_reviewed=[f.path for f in state["files"]],
        skipped=state["skipped"],
        findings=state["findings"],
        dropped=state["dropped"],
    )
