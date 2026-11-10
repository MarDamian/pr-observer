# PR Observer

Multi-agent pull request reviewer that verifies its own findings before commenting.

> **Status:** early development. The local CLI and the correctness reviewer work today.
> Security and performance reviewers, the verifier agent, the GitHub Action and the public
> benchmark are next.

## How it works

1. **Collect:** parses the diff and drops lockfiles, binaries, deleted and generated files.
2. **Review:** specialized reviewer agents run in parallel on a LangGraph graph and return
   structured findings (file, line, severity, failure scenario, suggested fix).
3. **Validate:** any finding that points at a file or line outside the diff is discarded, then
   findings are deduplicated and sorted by severity.

The diff is treated as untrusted data, and the tool never executes code from the pull request.

## Quick start

Runs on free-tier models from Gemini or Groq.

```bash
git clone https://github.com/MarDamian/pr-observer && cd pr-observer
python -m venv .venv && .venv/bin/pip install -e .
cp .env.example .env   # add GEMINI_API_KEY or GROQ_API_KEY
```

```bash
pr-observer review                    # your uncommitted changes
pr-observer review --base main        # this branch against main
pr-observer review --pr 123           # a GitHub pull request (needs gh)
pr-observer review --diff change.diff # a diff file, or "-" for stdin
```

Options: `--json` for machine-readable output, `--fail-on high` to exit with code 1 in CI, and
`--model provider:model` to pick the model (for example `groq:openai/gpt-oss-120b`).

## Docker

```bash
docker build -t pr-observer .

# Review the repository in the current directory
docker run --rm --env-file .env -v "$PWD":/repo:ro pr-observer review --base main

# Or pipe a diff in
git diff | docker run --rm -i --env-file .env pr-observer review --diff -
```

With Compose: `docker compose run --rm observer review --base main`. Set `REPO=/path/to/repo`
to review a different repository.

## Development

```bash
.venv/bin/pip install -e '.[dev]'
.venv/bin/pytest
.venv/bin/ruff check .
```

## License

MIT
