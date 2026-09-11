# CONTRIBUTING

## Contributing In General

Our project welcomes external contributions. If you have an itch, please feel
free to scratch it.

To contribute code or documentation, please submit a [pull request](https://github.com/contextforge-org/mcp-reverse-proxy/pulls).

A good way to familiarize yourself with the codebase and contribution process is
to look for and tackle low-hanging fruit in the [issue tracker](https://github.com/contextforge-org/mcp-reverse-proxy/issues).

**Note: We appreciate your effort, and want to avoid a situation where a contribution
requires extensive rework (by you or by us), sits in backlog for a long time, or
cannot be accepted at all!**

### Issue readiness

Do not start implementation on issues labeled `triage`, including issues you
opened. Wait until maintainers accept or scope the issue, remove the `triage`
label, or explicitly invite contributions.

### Proposing new features

If you would like to implement a new feature, please [raise an issue](https://github.com/contextforge-org/mcp-reverse-proxy/issues)
before sending a pull request so the feature can be discussed. Issues use the
templates under `.github/ISSUE_TEMPLATE/` (bug reports, feature requests).

### Fixing bugs

If you would like to fix a bug, please [raise an issue](https://github.com/contextforge-org/mcp-reverse-proxy/issues) before sending a
pull request so it can be tracked.

## Workflow

1. Fork the repository and create a feature branch from `main`.
2. Make your changes with tests covering the new behavior.
3. Run the checks below and keep them green.
4. Commit with `git commit -s` (DCO sign-off, see Legal below) using
   [Conventional Commits](https://www.conventionalcommits.org/) messages such as
   `feat:`, `fix:`, `docs:`, `refactor:`, or `chore:`.
5. Open a pull request against `main` and fill in the PR template.

## Before Contributing

### Setup

```bash
git clone https://github.com/contextforge-org/mcp-reverse-proxy.git
cd mcp-reverse-proxy
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

### Testing and checks

Before submitting changes:

1. `pytest` - all tests pass (the suite runs with coverage by default)
2. `ruff check .` - lint passes
3. `mypy src/` - type checks pass

### Container dependency lock

`requirements-container.txt` is the hash-pinned dependency closure installed into the container image (root `Containerfile`). Regenerate and commit it whenever `pyproject.toml` dependencies, `[build-system] requires`, or `.lockgen.in` change:

```bash
uv pip compile pyproject.toml .lockgen.in \
  --generate-hashes --universal --no-build --python-version 3.12 \
  --exclude-newer "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  -o requirements-container.txt
```

- `.lockgen.in` seeds the PEP 517 build backend (setuptools/wheel) so the project wheel can build with `pip wheel --no-build-isolation` in the image's builder stage; keep its floors in sync with `[build-system] requires` in `pyproject.toml`.
- `--python-version 3.12` (the image's interpreter) is **required**: without it uv omits `typing-extensions` (an `anyio` requirement on Python < 3.13) and the image build fails `pip check`.
- Record the new cutoff date in the lock file's header comment, then verify with `docker build -f Containerfile -t mcp-reverse-proxy .` before committing.

## Coding Standards

- **Python >= 3.11** with type hints
- **Formatting**: Black, line length 120
- **Linting**: Ruff, line length 120, rule set per `pyproject.toml`
- **Type checking**: mypy, configuration per `pyproject.toml`
- **Naming**: `snake_case` functions and modules, `PascalCase` classes, `UPPER_CASE` constants

## Pull Request Standards

- Link the issue the PR addresses (`Closes #123` only when the PR fully resolves it).
- Keep the PR focused on one concern; split unrelated work into separate PRs.
- Keep tests with the code they validate, in the same PR.
- Include testing evidence: the commands you ran and their results.
- All PRs require maintainer review and at least one LGTM before merge.

## Legal

We use the same approach as the Linux(r) Kernel community: the
[Developer's Certificate of Origin 1.1 (DCO)](DCO.txt).

When submitting a patch for review, the developer must include a sign-off
statement in the commit message:

```text
Signed-off-by: John Doe <john.doe@example.com>
```

You can add this automatically with:

```bash
git commit -s
```
