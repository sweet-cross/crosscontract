# Contributing

## Branching model

This repo uses a two-branch flow:

- **`main`** — public release branch. Every push to `main` publishes the package to PyPI (gated by a manual approval on the `pypi` GitHub Environment) and deploys the docs.
- **`dev`** — integration branch and the GitHub default branch. Versioning happens here: every push runs [`python-semantic-release`](https://python-semantic-release.readthedocs.io/), which inspects conventional-commit messages and creates a `vX.Y.Z` tag if a release is warranted.

```
feature/xyz ──(squash)──▶ dev ──(fast-forward)──▶ main
                          │                       │
                       version tag             publish + docs
```

## Workflow

### Working on a feature or fix

1. Branch off `dev`.
2. Open a PR back into `dev`. The PR title **must be a valid conventional commit**, e.g.:
   - `feat: add foo support` (minor bump)
   - `fix: handle bar correctly` (patch bump)
   - `feat!: rename baz` or include `BREAKING CHANGE:` in the body (major bump)
   - `docs:`, `chore:`, `refactor:`, `test:`, `ci:`, `style:`, `perf:`, `revert:` (no version bump, but appears in changelog)
3. CI runs the PR title lint and the test suite.
4. **Squash-merge** the PR into `dev`. The PR title becomes the squash commit message — this is what PSR will analyze.
5. On push to `dev`, `Release Dev Branch` runs the test suite, then PSR creates the version commit and tag if appropriate.

### Hotfixes

Hotfixes follow the same path as features: branch off `dev`, PR into `dev`, squash-merge. Use a `fix:` prefix for the patch bump. Do not push directly to `main`.

### Promoting a release

1. Open a PR from `dev` into `main`.
2. CI runs the test suite as a final gate.
3. **Fast-forward merge** (no merge commit, no squash). This carries over all dev commits and tags as-is.
4. On push to `main`, `Release Main Branch` runs tests, then enters the `pypi` environment, which **pauses for manual approval**.
5. After approval, the package is built from the latest tag and published to PyPI; docs deploy at the same ref.

## Commits and conventional format

The PR title is the source of truth — it becomes the squash commit on `dev` that PSR analyzes. Local commit messages on the feature branch don't need to be conventional.

Allowed types: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `ci`, `chore`, `revert`.

## Local development

See [.claude/CLAUDE.md](.claude/CLAUDE.md) for the full command reference (uv, pytest, ruff, mypy, mkdocs).
