# WP3 — Language, ADR, and backlog

## Context

The derived routing `enum` is not an implementation detail that quietly disappears — it
is asserted as settled in both the ubiquitous language and ADR 0004. Two documents
currently make a claim that WP1 makes false, and leaving them is worse than never having
written them: the next reader takes CONTEXT.md at its word.

This WP is part of the change, not a follow-up.

## Acceptance Criteria

- [ ] No document in `.ai-context/` still claims the routing field's permitted values are
      derived from the targets.
- [ ] **Unclaimed rows** exists as a term in CONTEXT.md with an `_Avoid_` line.
- [ ] The `TODO.md` item calling for the derived enum's assembly is **deleted**, not
      reworded.
- [ ] The two non-goals from WP1 and WP2 are recorded in `TODO.md` with enough context to
      act on cold.

## Implementation Details

**Modify:**

### `.ai-context/CONTEXT.md`

- **Routing column** entry (~line 277). Its second sentence — permitted values are
  "*derived* from the targets, never authored, so the **Extraction instructions** stay the
  single source of truth and cannot drift from the **Schema**" — is now false in both
  halves: nothing derives them, and an authored `enum` is permitted. Replace it. What the
  routing column still *is*: the bundle column whose value selects a **Target**,
  conventionally `variable`, required and string-typed, and the default source of a
  target's filter when `filters` is omitted. Keep the existing `_Avoid_` line.
- Add an **Unclaimed rows** term: rows of a submission bundle that no **Target**'s filters
  match, and which extraction would therefore silently drop. Reported by
  `SubmissionContract`, never acted on by it — whether they are an error or a warning is
  the caller's policy. `_Avoid_`: leftover, unpacked, orphan rows, unrouted.
- Consider a **Relationships** line: extraction coverage is a property of a bundle against
  its **Extraction instructions**, not of the **Schema**. Optional — add it only if it
  earns its place among the existing entries.

### `.ai-context/adrs/0004-submission-contracts-carry-extraction-instructions.md`

**Amend in place rather than superseding.** The three decisions the ADR names as
expensive to reverse are all untouched; what changes is one consequence that the ADR
itself flagged as unfinished and that `TODO.md` still listed as open. A whole ADR for
"the derived enum became a coverage check" would outweigh the decision.

Two passages, both of which must change:

- **The Why section**, under "The contract carries the spec": the closing clause "and
  what lets the routing field's permitted values be derived from the targets instead of
  authored twice". The argument for co-locating schema and instructions does not depend on
  it — checking the routing column against real fields at load time already carries it — so
  the clause can simply go, or be replaced by the coverage property, which is a *better*
  example of the same point: only a contract that holds both halves can tell whether a
  bundle's rows are all claimed.
- **The first Consequences bullet**, "The routing field's `enum` is derived, never
  authored." Rewrite it as the opposite, and record *why*, since that reasoning is the
  durable part: filters are an arbitrary column → value conjunction, so a target may not
  constrain the routing column at all and the permitted set is underivable; a set derived
  from only the targets that do mention it would wrongly reject valid rows; and the enum
  never expressed the property that mattered, which is whether a row is *consumed*, not
  whether its routing value is *known*. Coverage is decidable only against data, so it
  moved to extraction time as unclaimed rows.

### `.ai-context/TODO.md`

Under "Submission extraction follow-ups":

- **Delete** the "Assemble the derived routing `enum`" bullet outright.
- **Add — contested rows.** Rows claimed by more than one target. ADR 0004 makes overlap
  deliberately legal, so this is not a bug to fix but a question to answer: is
  *unintentional* overlap worth detecting, given it is as damaging as an unclaimed row —
  the same rows land in two contracts? Note that it falls out of the same per-target
  matching as unclaimed rows (a sum instead of an OR) if the intermediate is kept, and
  that it needs its own throw-vs-warn call.
- **Add — load-time filter parseability.** Check in `_check_filters` that each authored
  filter string parses as its field's Frictionless type, so `{year: "abc"}` fails on the
  YAML rather than producing an empty match at runtime. Needs no backend — it compares a
  string against a Frictionless type — so it sits in `contracts/` beside the existing
  filter-key check. Deferred because the unclaimed-row report already surfaces the
  failure; this only sharpens *where* it is reported. Record the datetime caveat from WP2
  alongside it: string-form matching makes `{date: "2030-01-01"}` claim nothing against a
  datetime column, and a parseability check would not catch that, since the value parses
  fine.
- Leave the existing "Decide how far column tracking goes", "`MapColumnValues` has no
  conflict guard", and "Execution" items alone.

**Dependencies:** WP1 and WP2 — the documents should describe what the branch actually
contains.

**Verification:** prose only, no test run. Re-read the amended ADR and CONTEXT.md entries
end to end and confirm no surviving sentence asserts derivation; `grep -rn "derived"
.ai-context/CONTEXT.md .ai-context/adrs/0004-*.md` is a cheap check.
