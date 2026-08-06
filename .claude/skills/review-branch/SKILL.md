---
name: review-branch
description: >
  Review the current git branch against its base branch for code quality,
  architecture, and adherence to the repository's own guidelines. Use whenever
  the user wants a branch, PR, or set of changes reviewed before merging — e.g.
  "review my branch", "review this PR", "check my changes before I merge",
  "is this ready to merge". Applies the repo's CLAUDE.md and linter config as
  the primary standard.
---

# Review Branch

Produce a structured, actionable review of the current branch's changes against
its base branch. The goal is a review a senior engineer on THIS team would give —
so the repository's own conventions take priority over generic best practices.

## 1. Establish the diff

- Determine the base branch (check for `main`, then `master`, then `develop`; if
  unsure, ask).
- Get the changes with the merge-base diff so you don't pick up unrelated commits:
  `git diff <base>...HEAD` and `git log <base>..HEAD --oneline`.
- If the diff is empty, the branch equals base, or there are uncommitted changes,
  say so and stop rather than inventing findings.

## 2. Load the standard (do this before judging anything)

- Read `CLAUDE.md` (and any nested ones) — this is the source of truth for style,
  architecture, and conventions. Cite it when a finding is based on it.
- Read linter/formatter/type config if present (`pyproject.toml`, `ruff`/`flake8`,
  `mypy`, `.pre-commit-config.yaml`) and hold changes to those rules.
- Only fall back to general Python best practices where the repo is silent.

## 3. Review the changes — form your findings independently

For each changed file, consider:

- **Correctness & logic** — bugs, edge cases, off-by-ones, error handling
  (no bare `except`, no swallowed exceptions).
- **Tests** — is new/changed behavior covered? Do tests actually assert something?
- **Architecture** — coupling, layering, duplication, misplaced responsibility.
- **Python specifics** — type hints, docstrings, naming, mutable defaults,
  resource cleanup, adherence to the repo's idioms.
- **Security** — hardcoded secrets/credentials, unsafe input handling.
- **Dependencies & docs** — new deps justified and pinned; docs/comments updated.

Form your findings from the diff and the standard ALONE. Do NOT read the PR
description yet — reading the author's narrative first anchors the review on what
they *say* they did instead of what the code actually does, which defeats the point
of an independent review.

## 4. Cross-check against the PR description (only after step 3)

Now that your findings are formed, locate the branch's PR description in
`.github/PRs/`:

- The description is named after the branch, with `/` replaced by `-`
  (e.g. `feature/retry-logic` → `.github/PRs/feature-retry-logic.md`).
- **Match found** → use it.
- **No name match, exactly one file in the folder** → Ask whether to use this, or
  whether to continue without a PR description.
- **No name match, multiple files, can't infer which** → ask the user which one to
  use, or whether to continue without a PR description.
- **Folder missing or empty** → continue without one; note this in the report.

If you have a description, read it and compare claimed intent against the actual
diff. Flag any discrepancy — e.g. the description claims input validation was added
but the diff has none, or the diff makes a behavioral change the description omits.
A material discrepancy is itself a finding: raise it at the appropriate severity
(Blocking / Recommended) as well as noting it in the description check.

## 5. Report

ALWAYS use this exact structure:

```
# Branch Review: <branch> → <base>

**Summary:** <2-3 sentences: what the branch does and overall verdict>

## Strengths
- <brief, genuine positives>

## Blocking
- `path/to/file.py:42` — <what's wrong> — <why it matters (cite CLAUDE.md if relevant)> — <suggested fix>

## Recommended
- `path/to/file.py:88` — <issue> — <why> — <fix>

## Nit-pick
- `path/to/file.py:12` — <suggestion>

## Description check
<"Matches the changes." | list of discrepancies between the PR description and the diff | "No PR description found — reviewed the diff on its own.">

## Verdict: <Ready to merge | Merge after blocking issues resolved | Needs rework>
```

If a category has no findings, write "None." explicitly — don't omit it.