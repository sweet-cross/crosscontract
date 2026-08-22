# feat: identify extraction targets by name

## Summary

A `Target` had no identifier of its own. In practice it was identified by its
`contract`, which the contract-uniqueness validator happened to enforce — an accident of
that check rather than a design. This branch gives targets a `name`, and uses it to
derive the routing filter when none is authored.

Two problems go away. `contract` is a platform-side resource name that ends up in a URL,
so using it as a spec-local identifier was semantically wrong. More importantly, binding
identity to it cemented contract-uniqueness as an *identity* constraint rather than the
primary-key-collision guard it actually is — which would have made it expensive to relax
if combining several targets into one dataset (netting supply against demand, say) ever
becomes a feature. That combination is **not** implemented here and is not planned as
part of this work; the point is only that identity no longer rides on `contract`.

Base branch is `dev`.

## Changes

**`Target.name`** — required, `min_length=1`, whitespace-stripped, and deliberately
carrying **no pattern and no maximum length**. It is spec-local identification: what an
author calls their own target is their decision, and `"StUpid nAming 0f a V@riable"` is
legal. `contract` keeps `CONTRACT_NAME_PATTERN` and `max_length=100` for the opposite
reason — it names a platform resource that appears in URLs. The constraint is expressed
as `Annotated[str, StringConstraints(...)]`, matching `ValidFieldName` in
`contracts/valid_items.py`, rather than a model-wide `str_strip_whitespace`, which would
also have stripped `filters` values and silently changed row matching.

**Filters derive from the name; the scalar shorthand is gone.** The authoring surface is
now two forms instead of three: omit `filters` and it becomes `{routing_column: name}`,
or write the mapping out and `name` plays no part in routing. The old scalar
`filters: some_value` is rejected. `filters` stays `dict[str, str]` and required on the
model — the before-validator populates it — so the annotation continues to describe the
stored value rather than the input that produced it.

The derivation replaces the scalar branch in the existing
`field_validator("targets", mode="before")`, keeping its shape: it reads `routing_column`
off `info.data` (which is why it is a field validator rather than a model validator — the
value is already validated there), copies rather than mutating the caller's dicts, and
hands unrecognised shapes through so pydantic reports them. Two details are deliberate
and easy to undo by accident: it triggers on the `filters` key being **absent**, not on
its value being `None`, so a half-written `filters:` is rejected rather than silently
derived; and it `.strip()`s the name, because `strip_whitespace` on `Target.name` runs
*after* this validator and the stored name would otherwise differ from the derived
routing value.

**Two independent uniqueness rules.** `_check_name_unique` joins `_check_contract_unique`
as a separate validator with its own message, rather than being folded in. They enforce
different things and have different futures: name-uniqueness is structural and permanent;
contract-uniqueness guards against merged rows colliding on the contract's primary key
and is relaxable. Folding them together would have re-created the coupling this branch
removes.

**Documentation.** ADR 0004's Consequences split the single "one target per contract"
bullet into the two rules, recording explicitly that contract-uniqueness is a guard and
not an identity constraint, and that keeping it distinct is what leaves it relaxable. Its
"filters are mapping-only" bullet now describes the two current authoring forms and notes
the scalar form's removal. `CONTEXT.md`'s **Target** entry leads with the name and covers
the routing-value default — the one place in that vocabulary where an identifier doubles
as data.

## Testing

`src/tests/submission/` — 17 tests, no new dependencies.

- **New:** duplicate target names raise, with a message distinct from the duplicate
  contract one; and `filters` omitted yields `{routing_column: name}`.
- **Rewritten:** `test_filter_raises_validation_error_no_routing_column` previously fed a
  scalar `filters` and no `name`, so its payload was invalid three ways and it passed on
  whichever error happened to land. It now supplies a well-formed target relying on the
  derivation, making the missing `routing_column` the only defect — which is what the
  test claims to check.
- **Updated:** every fixture gains a `name`; `example_submission.yaml` drops the two
  scalar-filter targets in favour of derived ones, keeping the explicit-mapping target so
  the round-trip tests still cover both forms.

## Notes for reviewer

**The `.strip()` in the validator duplicates knowledge that also lives in
`StringConstraints(strip_whitespace=True)`.** They cannot share, because the derivation
runs on raw input before field constraints apply. Without the strip,
`name: "  electricity  "` stores `name == "electricity"` but derives
`filters == {"variable": "  electricity  "}` — a routing value matching no rows, which
only warns and skips at runtime. The docstring says why the duplication exists so nobody
removes it as redundant. The alternative is dropping `strip_whitespace` and accepting
`"   "` as a legal name.

**"A scalar `filters` is rejected" has no test.** It reduces to pydantic refusing a `str`
for `dict[str, str]`, and the project's convention is not to test pydantic's own
behaviour. Flagging it because it *is* a behaviour change from the previous release —
though no authored file uses the old form, so there is nothing to migrate.

**No test pins "`name` has no pattern" either**, for the same reason: it would assert the
absence of a constraint. The reasoning now lives in ADR 0004 and `CONTEXT.md` instead,
which is what stops someone adding `CONTRACT_NAME_PATTERN` to `name` out of symmetry
with `contract`.

**`Target.name`'s field description** was written during WP1, when the derivation did not
exist yet; it has been correct since WP2 landed but is worth reading against the final
behaviour.
