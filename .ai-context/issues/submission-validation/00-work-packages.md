# Submission validation — work packages

Breakdown of [submission-validation.md](../../prds/submission-validation.md). Four work
packages, eight tasks, each sized for a single session. Numbering is the build order.

## Packages

| WP | Topic | Tasks | Depends on |
|---|---|---|---|
| **WP1** | De-risk and public surface | 01, 02, 03 | — |
| **WP2** | The primitive (`validate_target`) | 04, 05 | — (04 is independent; 05 follows 04) |
| **WP3** | The loop (`validate_targets`) | 06, 07 | 03, 04 |
| **WP4** | Prose that now contradicts the code | 08 | 04, 06 |

## Critical path

```
01 (risk gate) ─┐
02 ─────────────┤
03 ─────────────┼──▶ 06 ──▶ 07 ──▶ 08
04 ──▶ 05 ──────┘
```

**04 → 06 → 07 is the critical path.** Everything in WP1 is independent of it and can be
done in any order, or in parallel by a second person.

**01 is a risk gate, not filler.** It checks the one behaviour the design assumes without
having observed it: that an empty extracted frame passes a `strict=True` + `coerce=True`
pandera schema. If it does not, edge case 9 of the PRD is wrong and WP2/WP3 need rethinking
before they are written. Do it first even though nothing imports it.

## Decision still open before WP3

**Edge case 7 — a transformation that raises.** The PRD specifies that an exception from a
transformation (`cast_column` on unparseable text) propagates immediately rather than
joining the collected per-target failures, because the collection is typed
`dict[str, SchemaValidationError]`. That decision was *not* settled in the design session
and is flagged in the PRD as reviewable. Confirm it before implementing task 06 — if it
flips, the error mapping needs a wider value type and `to_list()`'s row shape (task 03)
has to say what a non-schema failure looks like.

## Suggested PR grouping

One feature branch (`submission_validation` is already checked out), one squash-merged PR
titled `feat: validate submission targets against their contracts`, with each work package
as its own commit. WP1 is separable into its own `feat:` PR if the surface changes want to
land ahead of the behaviour.
