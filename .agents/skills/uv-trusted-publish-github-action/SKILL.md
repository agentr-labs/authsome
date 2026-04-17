---
name: uv-trusted-publish-github-action
description: Use this skill when setting up, reviewing, or maintaining trusted publishing from GitHub Actions to PyPI for a Python package that uses `uv`. Trigger it for tasks involving `uv build`, `uv publish`, PyPI trusted publishing, package release workflows, or GitHub Actions publishing automation.
---

# Uv Trusted Publish Github Action

## Overview

This skill helps agents configure Python package publishing to PyPI using `uv` and GitHub Actions with trusted publishing. Prefer this approach when a Python library should publish from CI without storing long-lived PyPI API tokens in GitHub secrets.

Base this work on Astral's official `uv` packaging guide and prefer the trusted publishing flow documented there.
Also use Astral's trusted publishing example repository as a concrete reference for workflow shape and PyPI configuration expectations.

## Workflow

### 1. Inspect packaging readiness

Before adding publishing automation, inspect:

- `pyproject.toml`
- package metadata such as name and version configuration
- build backend configuration
- whether the repo already builds with `uv build`
- whether publishing already exists in `.github/workflows/`

Confirm the repo is actually a publishable Python package, not just an app or scripts repo.

### 2. Confirm the publish target

Determine:

- whether publishing should go to PyPI
- whether TestPyPI is needed for first-time validation
- which branch or tag should trigger publishing
- whether the package already has a matching PyPI project configured for trusted publishing

If the destination or trigger strategy is unclear, ask before setting up automated publishing.

### 3. Use trusted publishing

Prefer PyPI trusted publishing over storing static credentials.

For GitHub Actions, the usual pattern should include:

- `permissions: id-token: write`
- a GitHub `environment`, commonly `pypi`
- `astral-sh/setup-uv`
- `uv build`
- `uv publish`

The key idea is:

- GitHub Actions obtains an OIDC identity token
- PyPI trusts the configured repository and environment
- publishing happens without a saved API token secret

### 4. Configure the GitHub Actions workflow

When setting up the workflow, keep it minimal and explicit.

Typical responsibilities:

- check out the repo
- install `uv`
- build distributions with `uv build`
- publish with `uv publish`

Align the trigger with the repo's release flow. Common patterns include:

- publish on version tags
- publish on GitHub release events
- publish after a release PR merge when the repo has release automation

Astral's example repository uses a dedicated release workflow, which is a good default when the repo needs a clear separation between CI and publishing.

Do not invent a complicated release pipeline if the repo only needs a clean publish job.

### 5. Validate the packaging flow

Before finishing:

- confirm `uv build` succeeds locally or in CI
- confirm the workflow has `id-token: write`
- confirm the GitHub environment name matches the trusted publisher configuration on PyPI
- confirm package metadata is complete enough for publishing
- explain any assumptions about triggers, environments, or package naming

## Common Tasks

### Set up trusted publishing from scratch

Use this when the repo is a Python package and does not yet publish from CI.

Steps:

1. inspect `pyproject.toml`
2. verify the package builds with `uv build`
3. add a GitHub Actions publish workflow
4. configure trusted publishing assumptions clearly
5. document how releases trigger publishing

### Repair a broken publishing workflow

Use this when a workflow exists but publishing fails.

Check for:

- missing `id-token: write` permission
- missing or mismatched GitHub environment
- wrong trigger type
- `uv build` or `uv publish` commands not matching the package layout
- package metadata or build configuration problems
- mismatch between PyPI trusted publisher settings and the repository workflow

### Connect publishing to release automation

Use this when the repo already uses release tooling and publishing should happen after versioning is finalized.

Make sure:

- release and publish steps are not fighting each other
- the publish workflow runs only when the version is ready
- changelog and tag generation happen before publish when required by the repo's flow

## Implementation Guidelines

- Prefer trusted publishing over static secrets.
- Use `uv build` and `uv publish` directly instead of mixing multiple packaging flows without reason.
- Keep publishing workflows separate from heavy test workflows unless the repo already combines them cleanly.
- Do not configure package publication for non-library repos.
- If PyPI trusted publishing has not yet been configured on the package side, call that out clearly as a required external step.

## Useful File Patterns

Common files to inspect or update:

- `pyproject.toml`
- `.github/workflows/publish.yml`
- `.github/workflows/release.yml`
- `.github/workflows/release-please.yml`

## Official References

Use these official sources when details matter:

- `https://docs.astral.sh/uv/guides/package/`
- `https://github.com/astral-sh/setup-uv`
- `https://github.com/astral-sh/trusted-publishing-examples`

## Output Expectations

When you use this skill, the final result should leave the repo with:

- a clear `uv`-based publishing workflow
- trusted publishing oriented around GitHub Actions and PyPI
- publishing steps that match the repo's release flow
- a short explanation of any required PyPI-side configuration
