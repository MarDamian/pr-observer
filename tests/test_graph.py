from pathlib import Path

from pr_observer.graph import Limits, run_review
from pr_observer.schemas import Category, Finding, Severity

SAMPLE = (Path(__file__).parent / "fixtures" / "sample.diff").read_text()


def finding(file="app/cart.py", line=14, severity=Severity.high, confidence=0.8, **kw):
    return Finding(
        file=file,
        line=line,
        severity=severity,
        title="Division by zero",
        explanation="len(items) can be 0",
        failure_scenario="total([]) raises ZeroDivisionError",
        confidence=confidence,
        category=kw.get("category", Category.correctness),
        agent=kw.get("agent", "fake"),
    )


class FakeReviewer:
    def __init__(self, name, findings):
        self.name = name
        self.findings = findings
        self.seen = None

    def review(self, rendered_diff):
        self.seen = rendered_diff
        return self.findings


def test_reviewer_sees_only_reviewable_files():
    reviewer = FakeReviewer("fake", [])
    result = run_review(SAMPLE, [reviewer], "test:model")
    assert result.files_reviewed == ["app/cart.py"]
    assert {s.path for s in result.skipped} == {
        "pnpm-lock.yaml",
        "app/old.py",
        "logo.png",
        "docs/guide.md",
    }
    assert "### app/cart.py" in reviewer.seen
    assert "pnpm-lock" not in reviewer.seen


def test_findings_outside_the_diff_are_dropped():
    reviewer = FakeReviewer(
        "fake",
        [
            finding(line=14),
            finding(line=30),  # between the two hunks
            finding(file="app/missing.py", line=1),
            finding(file="pnpm-lock.yaml", line=1),  # skipped file
        ],
    )
    result = run_review(SAMPLE, [reviewer], "test:model")
    assert [(f.file, f.line) for f in result.findings] == [("app/cart.py", 14)]
    assert result.dropped == 3


def test_parallel_reviewers_are_merged_deduped_and_sorted():
    a = FakeReviewer(
        "a", [finding(line=14, confidence=0.5, agent="a"), finding(line=44, severity=Severity.low)]
    )
    b = FakeReviewer(
        "b",
        [
            finding(line=14, confidence=0.9, agent="b"),
            finding(line=15, severity=Severity.critical, category=Category.security),
        ],
    )
    result = run_review(SAMPLE, [a, b], "test:model")
    assert [(f.line, f.severity, f.agent) for f in result.findings] == [
        (15, Severity.critical, "fake"),
        (14, Severity.high, "b"),
        (44, Severity.low, "fake"),
    ]


def test_size_budget_skips_files_and_never_calls_the_reviewer_with_nothing():
    reviewer = FakeReviewer("fake", [finding()])
    result = run_review(SAMPLE, [reviewer], "test:model", Limits(max_chars=10))
    assert result.files_reviewed == []
    assert reviewer.seen is None
    assert result.findings == []
    assert {"path": "app/cart.py", "reason": "over the size budget"} in [
        s.model_dump() for s in result.skipped
    ]
