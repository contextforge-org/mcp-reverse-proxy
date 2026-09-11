# AGENTS.md

Guidance for AI coding agents working in this repository. Human-facing
details live in `CONTRIBUTING.md`, `USER_README.md`, and `docs/`; this file
is the operational summary for automated contributors.

## Commits — read first

- **Every commit MUST be signed off** (`git commit -s` / `--signoff`). The
  `Signed-off-by:` trailer certifies the Developer Certificate of Origin
  (`DCO.txt`, Linux Foundation DCO 1.1). Unsigned commits are not acceptable,
  even for trivial changes.
- Commit messages MUST follow [Conventional Commits](https://www.conventionalcommits.org/):
  `feat:`, `fix:`, `docs:`, `refactor:`, `build:`, `ci:`, or `chore:`,
  optionally scoped (e.g. `fix(logging): ...`). Match the existing history.

## Project layout

- `src/mcp_reverse_proxy/` — the package (src layout).
  - `client.py`, `base.py` — proxy core and transport interface.
  - `transports/` — server-side adapters: `stdio_adapter.py`,
    `sse_adapter.py`, `streamablehttp_adapter.py`, `websocket_adapter.py`.
  - `cli.py` / `__main__.py` — `mcp-reverse-proxy` console entry point.
- `tests/` — unit tests; `tests/integration/` — end-to-end tests against a
  live FastMCP companion server (`companion_server.py`).

## Setup

The project uses [uv](https://docs.astral.sh/uv/) (see `uv.lock`; CI uses
`astral-sh/setup-uv`). Python >= 3.11.

```bash
uv venv && uv pip install -e ".[dev]"
# Integration tests additionally need:
uv pip install -e ".[integration]"
```

## Commands (must be green before pushing — these are the CI gates)

```bash
uv run ruff check src tests        # lint
uv run mypy src/mcp_reverse_proxy  # type check
uv run pytest tests/ -q            # unit + integration (integration self-skips without the extra)
uv run pytest tests/ -q -m "not integration"   # unit tests only
uv build                           # packaging check
```

Formatting: Black, line-length 120 (`uv run black src tests`). Ruff also
uses line-length 120, target py311.

## Testing conventions

- `pytest` runs with coverage by default (`addopts` in `pyproject.toml`);
  pass `--no-cov` for quick local iterations.
- `asyncio_mode = "auto"` — async tests need no decorator.
- Integration tests are marked `integration` and call
  `pytest.importorskip("fastmcp")`; without the `integration` extra they
  **skip silently** — a "passing" run may have skipped them. Check for
  `SKIPPED` in verbose output when touching transports.

## Code conventions

- Imports are grouped with the repo's section-comment style
  (`# Future` / `# Standard` / `# Third-Party` / `# First-Party`); keep it.
- Logging goes through `logging_config.py` (`LoggingService` /
  `CorrelationIdJsonFormatter`), not ad-hoc `logging.getLogger` handlers.

## Contribution workflow

- Open an issue before a PR (bugs and features both). Do not implement
  issues labeled `triage` until a maintainer scopes them.
- PRs target `main`; fill in the PR template.
