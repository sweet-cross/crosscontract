# Give contracts a resolver and let them validate their own data

## Summary

Every consumer that validates a DataFrame against a contract re-derives the same few
lines of schema semantics to build the reference values first — which contract to read,
which columns, how to key the result. That logic existed twice already (here and in
`cross_back`) and submission execution would have been the third, and confusing
`fk.fields` with `fk.reference.fields` is silently wrong rather than a crash.

This branch moves that derivation into the library behind `BaseContract.validate_data`,
extends `ContractResolver` so one object answers both questions a contract cannot answer
about itself — what other contracts *are*, and what values already *exist* under them —
and migrates the client onto it. It also fixes a reachable bug where an empty referenced
table produced a confusing `ValueError` instead of a validation failure.

## Changes

**Fix: an empty referenced table is a validation result, not an inability**
- `_get_foreign_key_check` tested truthiness, merging "nothing supplied" (`None`) with
  "the referenced table exists and is empty" (`[]`). It now tests the parameter, so `[]`
  produces a `SchemaValidationError` naming the failing rows while `None` still raises
  `ValueError` as documented. Reachable today: `get_foreign_key_values` wrote `[]`
  unconditionally.

**`ContractResolver` gains a data lookup**
- One protocol carries `resolve` and `get_data`, both `@abstractmethod`, so a real
  implementor that misses one fails at construction rather than as an `AttributeError`
  during data submission. Test doubles still satisfy it structurally.
- The protocol says nothing about access control. How an implementation resolves
  permissions is its own business — the client issues an HTTP read and the platform
  answers it or refuses — so neither the docstring nor the signature mentions it.
- Exported from `crosscontract.contracts`; it was previously reachable only by full
  module path.

**`BaseContract.validate_data`**
- Owns the whole derivation: primary key against `self.name`, foreign-key targets via
  `fk.reference.resource or self.name`, columns via `fk.reference.fields`, keyed by
  `tuple(fk.fields)`, and order-safe tuple-ification.
- `check_existing_primary_key` / `check_existing_foreign_key` read in the positive and
  default to `False`; they govern whether stored values are fetched, nothing else.
- `resolver` is optional, so a `BaseContract` used off-platform validates without one.
  Requesting a check without a resolver raises, naming the contract and both remedies.

**The client migrated onto it**
- New `ClientContractResolver` wrapping a `ContractService`, mirroring
  `DbContractResolver` on the server. `_get_data` stays private — users read through a
  `ContractResource`, not by name off the service.
- `ContractResource.get_primary_key_values` and `get_foreign_key_values` are gone; their
  logic now lives in `validate_data`. `validate_dataframe` still fetches nothing by
  default.

**Documentation**
- `CONTEXT.md` gains a *Validation* section: **Well-formedness**, **Reference
  validation**, **Data validation**, **Contract resolver**, **Existing values**, plus
  **Check** / **Standard check** / **Additional check**.
- ADR 0005 records the design; two PRDs and a task breakdown for the follow-on work.

## Testing

- New `test_validate_data.py` (13 cases) covering the derivation, including one where
  `fk.fields` and `fk.reference.fields` differ — the direction error this work exists to
  prevent — and a composite foreign key whose resolver returns columns in a different
  order, which is silently wrong without the reindex.
- New `test_resolver.py` (7 cases). The one that matters: only `ResourceNotFoundError`
  becomes `None`; permission and server errors propagate, so a refused request is never
  reported as a missing contract.
- WP1's two arms plus the surprising half — a null foreign-key value still passes against
  an empty referenced table — in both the adapter and `validate_dataframe` suites.
- `test_contract_resource.py`: three tests that mocked the now-moved orchestration were
  deleted rather than re-pointed; four added, including one proving the default call
  performs no data fetch.
- Also removed four never-collected test methods in `test_foreign_key.py` that called a
  `ForeignKeys.get_pandera_checks` which does not exist, plus a duplicated test.
- `pytest`, `ruff` and `mypy` all pass.

## Notes for reviewer

**A deliberate gap.** `check_existing_*=False` reads as "do not consult other contracts",
but today it maps onto `skip_*=True`, which suppresses the check *entirely* — so a
`Dimension` validated through `validate_data` does not get its self-referencing foreign
key checked, and no contract gets uniqueness checking within the frame. That matches the
client's previous behaviour, so nothing regressed. The name is the specification and the
validator is brought up to it in
[check-based-validation.md](../../.ai-context/prds/check-based-validation.md); renaming
once now is cheaper than letting `cross_back` and the submission handler bind to `skip_*`
and churning them later. It is stated in `validate_data`'s docstring so it is not read as
a bug.

**`CONTEXT.md` runs ahead of the code in one place.** The new *Validation* section states
that a **Data validation** runs every **Standard check** its **Schema** requires and that a
caller can only add strictness, never remove it. That is not true today — it is the far
side of the deliberate gap above. It is written in the present tense because the validator
rework in [check-based-validation.md](../../.ai-context/prds/check-based-validation.md)
lands next and makes it true; until then ADR 0005's Consequences section records the gap.
Read the two together rather than as a contradiction.

**`ClientContractResolver` inherits the protocol deliberately** — inheriting makes a
missed method fail at construction. That reverses an earlier note saying `cross_back`
should drop its explicit base; the PRD now records inheriting as the convention for real
implementors, with test doubles staying duck-typed.

**Breaking, and intended on 0.x:** `ContractResource.validate_dataframe`'s parameters are
renamed from `skip_*` to `check_existing_*`, and its polarity flips.
`ContractResource.get_primary_key_values` / `get_foreign_key_values` are removed.
`ContractResolver` becoming public means further changes to it affect implementors
outside this repository.

**Worth extra scrutiny:** the `df[columns]` reindex in `_get_existing_values`. It looks
redundant, and it is what stops a composite foreign key comparing `(a, b)` against
`(b, a)` when a supplier returns columns in its own order.

**Not done here:** `cross_back` still needs the version bump and its own migration; the
validator-level rework has its own PRD and tasks.
