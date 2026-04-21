# Contributing to authsome

> **Do one thing and do it well.**
> authsome manages credentials — nothing more. Every contribution should make that one job simpler, more secure, or more reliable. If a change expands scope beyond credential management, it probably belongs in a different tool.

---

## Table of contents

- [Getting started](#getting-started)
- [Making changes](#making-changes)
- [Running tests](#running-tests)
- [Lint and type checks](#lint-and-type-checks)
- [Extending authsome](#extending-authsome)
- [Submitting a PR](#submitting-a-pr)
- [Reporting bugs / requesting features](#reporting-bugs--requesting-features)
- [License](#license)

---

## Getting started

```bash
git clone https://github.com/manojbajaj95/authsome.git
cd authsome
pip install -e ".[dev]"
pre-commit install          # runs ruff automatically on every commit
```

---

## Making changes

| Convention | Details |
|---|---|
| **Commits** | [Conventional Commits](https://www.conventionalcommits.org/) — `feat:`, `fix:`, `chore:`, `docs:`, `refactor:` |
| **Breaking changes** | Append `!` (e.g. `feat!:`) or add a `BREAKING CHANGE:` footer |
| **Branch names** | `feat/<short-description>`, `fix/<short-description>` |
| **PR scope** | One logical change per PR |

---

## Running tests

```bash
pytest                           # all tests
pytest tests/test_client.py      # single file
pytest -k test_login_pkce -v     # single test by name
pytest --cov=authsome            # with coverage report
```

All tests must pass before opening a PR.

---

## Lint and type checks

```bash
ruff check --fix src/ tests/     # lint + auto-fix
ruff format src/ tests/          # format
ty check src/                    # type check
```

Or run everything at once:

```bash
pre-commit run --all-files
```

---

## Extending authsome

### Adding a new provider

1. Create `src/authsome/bundled_providers/<name>.json` following the `ProviderDefinition` schema.
2. Add a test in `tests/` that covers at least the config-loading path.
3. Document the provider in `README.md`.

### Adding a new auth flow

1. Implement `AuthFlow.authenticate()` in `src/authsome/flows/`.
2. Register it in `FlowType` and `_FLOW_HANDLERS` in `src/authsome/client.py`.
3. Cover the happy path and at least one error case in tests.

For a full description of the major subsystems (`AuthClient`, flows, provider registry, storage, crypto, models, CLI) see [CLAUDE.md](CLAUDE.md).

---

## Submitting a PR

1. **Open an issue first** for non-trivial changes so we can align on approach.
2. Push your branch and open a PR against `main`.
3. Describe *what* changed and *why* in the PR body.
4. A maintainer will review within a few days.

---

## Reporting bugs / requesting features

Use the [GitHub issue templates](.github/ISSUE_TEMPLATE/) — there are dedicated forms for bug reports and feature requests.

---

## License

By contributing you agree that your changes will be released under the [MIT License](LICENSE).
