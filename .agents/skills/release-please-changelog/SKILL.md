---
name: release-please-changelog
description: Use this skill when setting up, reviewing, or maintaining release-please based release automation and changelog generation. Trigger it for tasks involving release PRs, changelog generation, `.release-please-manifest.json`, `release-please-config.json`, or GitHub workflow setup for automated releases.
---

# Release Please Changelog

## Overview

This skill helps agents set up or maintain `release-please` so changelogs and release PRs are generated consistently. Use it when a repo needs automated release notes, a release workflow, or cleanup of an existing `release-please` configuration.

Base this work on the official `googleapis/release-please` project and prefer patterns documented there.

## Workflow

### 1. Inspect existing release automation

Check for these files first:

- `.github/workflows/release-please.yml`
- `.github/workflows/release.yml`
- `release-please-config.json`
- `.release-please-manifest.json`
- `CHANGELOG.md`

Also inspect:

- package metadata such as `package.json` or `pyproject.toml`
- existing tag or versioning conventions
- commit history and PR title style
- whether the repo already uses Conventional Commits

Preserve working conventions when they already exist.

### 2. Identify the release strategy

Before changing anything, determine:

- is this a single-package repo or monorepo
- which component or package should release
- what version source is authoritative
- whether changelog generation already exists
- whether the repo follows Conventional Commits

Important constraint from the official project:

- `release-please` parses git history and expects Conventional Commit style messages for high-quality release PRs and changelog entries
- `fix:` maps to a patch release
- `feat:` maps to a minor release
- `!` or `BREAKING CHANGE` maps to a major release

If the versioning scheme is unclear, prefer matching the current repo rather than inventing a new one.

### 3. Set up release-please

When the repo does not already have working release automation, usually add:

- a GitHub Actions workflow that runs the official `release-please-action`
- `release-please-config.json`
- `.release-please-manifest.json` for manifest-based releases, especially monorepos or repos with multiple releasable components

Keep the setup minimal and aligned with the project type.

Typical responsibilities:

- open release PRs
- update versioned files
- generate changelog entries
- create GitHub releases when the release PR is merged

Prefer the action-based setup unless the repo already has a different official integration pattern in place.

### 4. Keep changelog quality high

`release-please` is only as good as the input history. Improve changelog quality by:

- favoring clear, scoped PR titles and commit messages
- grouping changes into user-meaningful categories
- avoiding noisy internal-only wording in changelog-facing entries
- making feature, fix, and breaking-change intent obvious

When asked to prepare release notes, summarize changes in language suitable for humans, not just raw commit subjects.

### 5. Validate before finishing

Before wrapping up:

- confirm workflow file names and paths are correct
- confirm config file paths match the repo layout
- confirm versioned files referenced by config actually exist
- confirm changelog generation matches the repo's package or app structure
- explain any assumptions about versioning or release strategy

## Common Tasks

### Set up release-please from scratch

Use this path when the repo has no release automation yet.

Steps:

1. Inspect package and versioning files
2. Create a minimal workflow using the official GitHub Action
3. Add config and manifest files if needed
4. Ensure changelog generation is enabled
5. Document how releases are expected to work

### Repair a broken setup

Use this when `release-please` files exist but releases or changelogs are incorrect.

Check for:

- wrong package paths
- mismatched manifest entries
- version files missing from config
- workflow triggers that do not match the default branch
- changelog sections that no longer reflect the repo structure
- commit history that does not give `release-please` enough Conventional Commit signal

### Improve changelog output

Use this when the changelog exists but is low quality.

Focus on:

- better release note categories
- clearer PR titles or commit conventions
- removal of unnecessary noise
- better mapping between repo structure and release sections

## Implementation Guidelines

- Prefer minimal configuration over clever configuration.
- Do not invent monorepo complexity for a single-package repo.
- Do not rewrite versioning strategy unless the user asks.
- Preserve existing `CHANGELOG.md` content unless there is a clear reason to restructure it.
- If the repo lacks a clean commit history, note that changelog quality may be limited until future PR titles improve.
- If commit messages are not Conventional Commit style, tell the user that release output quality and SemVer inference may be degraded.
- For monorepos or multiple release targets, prefer manifest-based configuration instead of improvised custom logic.

## Useful File Patterns

Common files to inspect or update:

- `.github/workflows/release-please.yml`
- `release-please-config.json`
- `.release-please-manifest.json`
- `CHANGELOG.md`
- `package.json`
- `pyproject.toml`

## Official References

Use these official sources when details matter:

- `https://github.com/googleapis/release-please`
- `https://github.com/googleapis/release-please-action`

## Output Expectations

When you use this skill, the final result should leave the repo with:

- a working or improved `release-please` setup
- clear changelog generation behavior
- configuration that matches the actual repo structure
- a short explanation of how releases will now work
