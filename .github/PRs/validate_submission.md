# Replace the derived routing `enum` with an unclaimed-row check

## Summary

A submission contract's routing field was specified to carry an `enum` *derived* from
the targets, and `_check_routing_column` rejected an authored one on that basis — but
nothing ever built the derived set, so the rule was enforced without being delivered.
The derivation turns out to be impossible: `Target.filters` is an arbitrary
column → value conjunction, so a target may never mention the routing column at all, and
a set derived from only the targets that *do* mention it would wrongly reject rows
destined for the rest.

The `enum` also never expressed the property it appeared to. It asserts that a routing
vocabulary is *known*, not that a row is *consumed* — a row carrying a valid routing
value still vanishes when a second filter over another column fails to match. That
property is row coverage, it is decidable only against data, and this branch delivers it
as `SubmissionContract.unclaimed_rows`.

## Changes

**Dropped the routing-column `enum` ban** — `_check_routing_column` no longer rejects an
authored `enum`; the exists / required / string rules are untouched, since they still
underwrite deriving a target's `filters` from its `name`. An authored `enum` is now an
ordinary field constraint, useful to an author who does know the closed set.

**Added `SubmissionContract.unclaimed_rows(df)`** — returns the rows of a submission
bundle that no target's `filters` match. It is a pure query: no raise, no warning, input
frame untouched. Whether an unclaimed row is an error or a warning is deliberately left
to the caller, which is what keeps that decision reversible.

Two details worth naming:

- **Filters match on the column's string form** (`df[col].astype(str) == value`). No
  Frictionless → backend type mapping is introduced anywhere. This follows the
  `cast_column` precedent: spec vocabulary stays Frictionless, the pandas mapping lives
  in the code that touches pandas. It is sound because string comparison can only
  *under*-match, and under-matching is exactly what this method detects — the two
  mechanisms close the loop on each other.
- **The per-target string cast is hoisted.** Columns named by any target's filters are
  cast once, not once per (target, filter) pair — with 24 targets filtering on
  `variable`, the naive form casts the same column 24 times.

**Documentation.** `Target.filters`' description now states the conjunction semantics and
the string-form matching, with the datetime case spelled out. CONTEXT.md's *Routing
column* term is rewritten and an *Unclaimed rows* term added. ADR 0004's *Why* clause and
its first Consequences bullet are amended — the bullet states the withdrawal explicitly
rather than quietly reading as though it always said this.

## Testing

`TestUnclaimedRows` in `src/tests/submission/test_submission_contract.py` — five tests
over a three-target contract: the core unclaimed case (asserting index labels survive, so
a caller can report *which* rows), a fully claimed bundle returning an empty frame, a
target constraining only a non-routing `Int64` column, filters behaving as a conjunction,
and input-frame purity. The shared fixture builds `year` as nullable `Int64` rather than
plain `int64`, since that is the dtype the method meets after pandera coercion.

The test that asserted the `enum` ban is inverted rather than deleted: it now asserts the
constraint survives onto the loaded model, which proves the `enum` actually reaches the
field and will be enforced by the pandera adapter.

Suite green locally (`uv run pytest src/tests/submission/`).

## Notes for reviewer

**Base is `dev`, not `main`.** `main...HEAD` pulls in PRs #80–#82, which already landed.

**Deliberate non-goals**, each recorded in `TODO.md` rather than implemented:

- *Contested rows* (claimed by more than one target). ADR 0004 makes overlap legal, so
  this is a question, not a bug — but note `unclaimed_rows` folds each target's mask into
  a single accumulator and keeps no intermediates, so adding contested detection later
  means reshaping that loop rather than adding a line. That is the shape decision most
  worth a second opinion here.
- *Load-time filter parseability* (`{year: "abc"}` on an integer column). Would sit
  beside the existing filter-key check and needs no backend. It would **not** catch the
  datetime case, which is why that trap is documented on `Target.filters` instead.
- *Raise-or-warn on unclaimed rows*, which belongs at the execution site.

**Known sharp edge:** a filter on a datetime column must match the full string form
(`2030-01-01 00:00:00`). It fails toward unclaimed, so it surfaces rather than corrupting
anything, but the report will not name the cause. Documented on the field description.

**Precondition, not a branch:** `unclaimed_rows` assumes a frame conforming to the
`tableschema`. A missing filter column raises `KeyError` from the hoisted column
selection, which names the columns and fails before any target is scanned.
