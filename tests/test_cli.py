import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from pr_observer import cli
from pr_observer.llm import ConfigError, resolve_model_spec
from tests.test_graph import FakeReviewer, finding

SAMPLE = str(Path(__file__).parent / "fixtures" / "sample.diff")
runner = CliRunner()


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for var in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "GROQ_API_KEY", "PR_OBSERVER_MODEL"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr(cli, "load_dotenv", lambda *a, **k: None)


def test_resolve_model_spec(monkeypatch):
    with pytest.raises(ConfigError, match="No API key found"):
        resolve_model_spec()
    monkeypatch.setenv("GROQ_API_KEY", "x")
    assert resolve_model_spec() == ("groq", "openai/gpt-oss-120b")
    monkeypatch.setenv("GEMINI_API_KEY", "x")
    assert resolve_model_spec() == ("google_genai", "gemini-3.6-flash")
    assert resolve_model_spec("gemini") == ("google_genai", "gemini-3.6-flash")
    assert resolve_model_spec("groq:some/model") == ("groq", "some/model")
    with pytest.raises(ConfigError, match="Unknown provider"):
        resolve_model_spec("nope:model")


def test_review_without_a_key_explains_what_to_set():
    result = runner.invoke(cli.app, ["review", "--diff", SAMPLE])
    assert result.exit_code == 2
    assert "GEMINI_API_KEY" in result.output


def test_review_json_output_and_fail_on(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "x")
    monkeypatch.setattr(cli, "build_reviewers", lambda p, m: [FakeReviewer("fake", [finding()])])

    result = runner.invoke(cli.app, ["review", "--diff", SAMPLE, "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["model"] == "groq:openai/gpt-oss-120b"
    assert data["findings"][0]["line"] == 14

    assert (
        runner.invoke(cli.app, ["review", "--diff", SAMPLE, "--fail-on", "medium"]).exit_code == 1
    )
    assert (
        runner.invoke(cli.app, ["review", "--diff", SAMPLE, "--fail-on", "critical"]).exit_code == 0
    )


def test_review_rejects_two_sources():
    result = runner.invoke(cli.app, ["review", "--diff", SAMPLE, "--pr", "3"])
    assert result.exit_code == 2


def test_review_in_a_repo_without_commits(tmp_path, monkeypatch):
    import subprocess

    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(cli.app, ["review"])
    assert result.exit_code == 2
    assert "no commits yet" in result.output


def test_provider_failure_is_reported_without_a_traceback(monkeypatch):
    class Overloaded:
        name = "fake"

        def review(self, rendered_diff):
            raise RuntimeError("503 UNAVAILABLE.\n  The model is overloaded.")

    monkeypatch.setenv("GROQ_API_KEY", "x")
    monkeypatch.setattr(cli, "build_reviewers", lambda p, m: [Overloaded()])
    result = runner.invoke(cli.app, ["review", "--diff", SAMPLE])
    assert result.exit_code == 3
    assert "the model call failed (groq:openai/gpt-oss-120b). 503 UNAVAILABLE. The model" in (
        result.output
    )
    assert "Traceback" not in result.output
