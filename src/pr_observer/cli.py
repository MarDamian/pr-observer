from __future__ import annotations

from typing import Annotated

import typer
from dotenv import find_dotenv, load_dotenv

from pr_observer import __version__, sources
from pr_observer.agents import Reviewer, correctness_reviewer
from pr_observer.graph import run_review
from pr_observer.llm import ConfigError, build_model, resolve_model_spec
from pr_observer.schemas import ReviewResult, Severity

app = typer.Typer(add_completion=False, help="Multi-agent pull request reviewer.")


def build_reviewers(provider: str, model: str) -> list[Reviewer]:
    return [correctness_reviewer(build_model(provider, model))]


def _version(value: bool) -> None:
    if value:
        typer.echo(f"pr-observer {__version__}")
        raise typer.Exit


@app.callback()
def main(
    version: Annotated[
        bool, typer.Option("--version", callback=_version, is_eager=True, help="Show the version.")
    ] = False,
) -> None:
    load_dotenv(find_dotenv(usecwd=True))


def _print_text(result: ReviewResult) -> None:
    typer.echo(
        f"PR Observer · {result.model} · {len(result.files_reviewed)} file(s) reviewed, "
        f"{len(result.skipped)} skipped"
    )
    for s in result.skipped:
        typer.echo(f"  skipped {s.path} ({s.reason})")
    if result.dropped:
        typer.echo(f"  {result.dropped} finding(s) discarded for pointing outside the diff")
    if not result.findings:
        typer.echo("\nNo findings.")
        return
    for f in result.findings:
        typer.echo(f"\n[{f.severity.upper()}] {f.category}  {f.file}:{f.line}")
        typer.echo(f"  {f.title}")
        typer.echo(f"  Why: {f.explanation}")
        typer.echo(f"  Fails when: {f.failure_scenario}")
        if f.suggestion:
            typer.echo(f"  Fix: {f.suggestion}")


@app.command()
def review(
    diff: Annotated[
        str | None, typer.Option("--diff", help="Unified diff file, or '-' for stdin.")
    ] = None,
    base: Annotated[
        str | None, typer.Option("--base", help="Review this branch against a git ref.")
    ] = None,
    pr: Annotated[
        int | None, typer.Option("--pr", help="GitHub pull request number (needs gh).")
    ] = None,
    repo: Annotated[
        str | None, typer.Option("--repo", help="OWNER/NAME for --pr. Default: current repo.")
    ] = None,
    model: Annotated[
        str | None,
        typer.Option("--model", help='"provider:model", e.g. groq:openai/gpt-oss-120b.'),
    ] = None,
    as_json: Annotated[bool, typer.Option("--json", help="Print the result as JSON.")] = False,
    fail_on: Annotated[
        Severity | None,
        typer.Option("--fail-on", help="Exit with code 1 if a finding has this severity or worse."),
    ] = None,
) -> None:
    """Review a diff. With no source option, reviews your uncommitted changes."""
    if sum(x is not None for x in (diff, base, pr)) > 1:
        raise typer.BadParameter("Use only one of --diff, --base and --pr.")
    try:
        if diff is not None:
            diff_text = sources.from_file(diff)
        elif pr is not None:
            diff_text = sources.from_pull_request(pr, repo)
        else:
            diff_text = sources.from_git(base)
        if not diff_text.strip():
            typer.echo("The diff is empty. Nothing to review.", err=True)
            raise typer.Exit
        provider, model_id = resolve_model_spec(model)
        reviewers = build_reviewers(provider, model_id)
    except (sources.SourceError, ConfigError) as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(2) from exc

    try:
        result = run_review(diff_text, reviewers, f"{provider}:{model_id}")
    except Exception as exc:  # provider errors: rate limits, overload, bad key or model name
        reason = " ".join(str(exc).split())[:300] or type(exc).__name__
        typer.echo(f"Error: the model call failed ({provider}:{model_id}). {reason}", err=True)
        raise typer.Exit(3) from exc

    if as_json:
        typer.echo(result.model_dump_json(indent=2))
    else:
        _print_text(result)
    if fail_on and any(f.severity.rank <= fail_on.rank for f in result.findings):
        raise typer.Exit(1)
