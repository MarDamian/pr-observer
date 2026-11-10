from __future__ import annotations

from typing import Any

from pr_observer.agents.base import LLMReviewer
from pr_observer.schemas import Category

FOCUS = """Look for correctness bugs: wrong logic or conditions, off-by-one errors, unhandled \
None/null or empty values, wrong or missing error handling, broken edge cases, misuse of an API, \
race conditions, resource leaks, and behavior changes that break existing callers."""


def correctness_reviewer(model: Any) -> LLMReviewer:
    return LLMReviewer("correctness", Category.correctness, FOCUS, model)
