---
name: write-pr-description
description: >
  Write a pull-request description for the current build branch and save it to
  .github/PRs/. Use at the end of a session where the changes were made — when the
  user says the branch is "done", "ready for review", "ready for a PR", or asks to
  "write the PR description" / "write up these changes". Run this in the build
  session (not the review session), because that's where the intent behind the
  changes is known.
---

# Write PR Description

Summarize the work on the current branch into a clear PR description and save it to
`.github/PRs/`. This file is later read by the review skill (after it forms its own
findings) to cross-check stated intent against the actual diff — so the description
must describe what *actually* changed and *why*, not aspirations.

## 1. Establish the branch and diff

- Get the current branch: `git rev-parse --abbrev-ref HEAD`. If it's `main`,
  `master`, or `develop`, stop and tell the user — there's nothing to describe.
- Determine the base branch (check for `main`, then `master`, then `develop`).
- Gather the changes to ground the description in reality:
  `git diff <base>...HEAD --stat`, `git diff <base>...HEAD`, and
  `git log <base>..HEAD --oneline`.

## 2. Write the description

Base the description on what you know from this session PLUS the actual diff. Where
your memory of the intent and the diff disagree, trust the diff and describe what is
actually there. Be specific and concrete; avoid filler.

Use this exact structure:

```
# <concise, imperative title — e.g. "Add retry logic to the sync client">

## Summary
<2-4 sentences: what this branch does and why. The problem it solves.>

## Changes
- <the meaningful changes, grouped logically — not a raw file list>

## Testing
<what was added/run to verify: new tests, manual checks, or "None" if none>

## Notes for reviewer
<anything non-obvious: trade-offs, follow-ups deferred, areas wanting extra scrutiny.
Omit this section if there's nothing worth flagging.>
```

## 3. Save it

- Ensure the directory exists: create `.github/PRs/` if missing.
- Derive the filename from the branch name, replacing `/` with `-`
  (e.g. `feature/retry-logic` → `.github/PRs/feature-retry-logic.md`).
- Write the file, overwriting any existing description for the same branch.
- Confirm the saved path to the user.