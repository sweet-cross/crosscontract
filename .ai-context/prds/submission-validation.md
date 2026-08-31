# Submission validation PRD

Status: **agreed, not implemented**. Written 2026-08-31, out of a design session whose
outcome is recorded as the 2026-08-31 amendment to
[ADR 0004](../adrs/0004-submission-contracts-carry-extraction-instructions.md).

## 1. Overview

This is **step 2** of the four-step sequence opened in
[validation-architecture.md](./validation-architecture.md): *provide validation for
submission contracts*. Step 1 (the `ContractResolver` signature) and its follow-on (checks
as objects, one derivation) have landed; this consumes both.

A **Submission validation** is two checks at different grains:

1. the delivered **bundle** against the **Submission contract**'s own schema, and
2. each **Target**'s extracted rows against the **Contract** that target names.

Step 1 is an ordinary `BaseContract.validate_data` call and needs no new code. This PRD
covers step 2 only: `SubmissionHandler` gains the ability to validate what it extracts.

Who it is for:

- **Data providers**, validating a bundle in a notebook before submitting it — today they
  can extract per target but have to hand-roll the loop and the contract lookup.
- **`cross_back`**, for step 3b (batch submission through the server), which is the
  consumer whose absence made "leave the loop to the caller" free until now.

Terminology is fixed in the *Submission and extraction* section of
[CONTEXT.md](../CONTEXT.md) — **Submission validation**, **Submission handler**,
**Target**, **Unclaimed rows**, **Contract resolver**, **Existing values**.

## 2. Core Requirements

Done means all of the following.

- **`SubmissionHandler.validate_target(target_name, contract=None, resolver=None, …)`** —
  extract, transform, and validate **one** target, returning the validated (coerced)
  frame. `contract` wins over `resolver` when both are given, so a provider can validate
  against a contract that is not on the platform yet.
- **`SubmissionHandler.validate_targets(resolver, targets=None, …)`** — the same for every
  target, or for a named subset. `targets=None` means all, in declaration order. Returns
  `dict[target_name, pd.DataFrame]`.
- **Failures across targets are collected, never fail-fast.** There is no `fail_fast`
  parameter. This mirrors `lazy=True`, which is the posture every layer below already
  takes within one dataset.
- **`TargetValidationError`** — a new exception holding `dict[target_name,
  SchemaValidationError]`, exposing `to_list()` (each row stamped with its `target`) and
  `to_pandas()`, with a message naming the failing targets.
- **Both methods carry `check_existing_primary_key`, `check_existing_foreign_key`, and
  `lazy`**, with the same names and the same defaults (`False`, `False`, `True`) as
  `BaseContract.validate_data` and `ContractResource.validate_dataframe`. Uniform across
  targets; a caller needing per-target variation loops `validate_target` itself.
- **`ClientContractResolver` becomes public API**, exported from `crosscontract.crossclient`.
  Without it the `resolver` argument has no supplier a user can reach without importing a
  private module path.
- **The handler still resolves nothing on its own.** It never constructs a resolver, never
  imports `crossclient`, and loads and runs with no platform connection.

**Not in scope**, deliberately:

- Validating the bundle (step 1) — the caller's own `validate_data` call.
- Deciding whether a failed bundle stops the run — structural, not a flag: the caller
  simply does not construct the handler.
- **Unclaimed rows** — a bundle-level property, asked for separately, still a report
  nobody acts on.
- Uploading the validated frames (step 3b).
- Checking at authoring time that every target names a contract that exists — see the
  entry added to [TODO.md](../TODO.md).
- Anything in [validation-reporting.md](./validation-reporting.md). `TargetValidationError`
  is additive and changes no existing shape, but it does not resolve that draft either.

## 3. Edge Cases & Error Handling

Failures split into two families, and the split is the design's load-bearing rule:
**data failures are collected, wiring failures raise immediately.** A wiring failure means
the run is misconfigured — nobody's rows are at fault — and folding it into a per-target
data report makes the report unactionable, because the two are fixed by different people
at different times.

| # | Situation | Behaviour |
|---|---|---|
| 1 | `target_name` names no target | `KeyError` from `ExtractionInstructions.get_target` (existing behaviour, unchanged) |
| 2 | `resolver.resolve(target.contract)` returns `None` | `ValueError` naming the target **and** the contract. Deliberately not `KeyError` — that is already case 1's signal, and a caller catching around a loop must be able to tell them apart |
| 3 | `contract.name != target.contract` | `ValueError`. Validating one target's rows against another's contract can *pass*, so this is silently-wrong-not-a-crash and the library owns it (the ADR 0005 criterion) |
| 4 | Neither `contract` nor `resolver` given to `validate_target` | `ValueError` naming both remedies, in the shape `validate_data` already uses for its own illegal combination |
| 5 | `check_existing_*=True` with a `contract` but no `resolver` | Already handled one layer down — `validate_data` raises naming the contract and both remedies. **Add no guard here**; duplicating it would produce two messages for one mistake |
| 6 | A filter names a column absent from the bundle | `KeyError` from `_mask_target` (existing behaviour, propagates) |
| 7 | A transformation raises (e.g. `cast_column` on unparseable text) | **Propagates immediately, uncollected.** The collection is typed `dict[str, SchemaValidationError]`; widening it to arbitrary exceptions would make the report untyped and would report a spec bug as if it were a data defect. *This is the one case not settled in the design session — flag it in review* |
| 8 | The resolver raises (network, permission, contract has no data yet) | Propagates immediately. `ClientContractResolver.get_data` surfaces `ResourceNotFoundError` for a contract with no stored rows, which is a wiring/state problem, not a row defect |
| 9 | A target claims **no rows** | Validated like any other and returned as an empty frame. No warning, no skip — deliberately the inverse of `release/`'s warn-and-skip, because an empty resource corrupts a published package while an empty target is a submission that legitimately carried nothing this round |
| 10 | The transformed frame carries columns the target contract does not declare (a forgotten `drop_columns`) | `SchemaValidationError` — the base pandera schema is built with `strict=True` — **collected** as a data failure. This is the check that catches spec/schema drift, which ADR 0004 accepts as the cost of not deriving transformations from the target schema |
| 11 | Some targets pass, some fail | `TargetValidationError` raised; the passing frames are **discarded**. All-or-nothing is the right default for a bundle, and a caller wanting partial results loops `validate_target` |
| 12 | Every target fails | Same, with one entry per target |
| 13 | `targets=[]` | Returns `{}`. Empty means empty; `None` means all |
| 14 | A name repeated in `targets` | Collapses in the returned dict; the target is validated once or twice depending on implementation, and neither is observable. No dedupe guard |
| 15 | `lazy=False` | Still one `SchemaValidationError` per target (`validate_dataframe` converts a `SchemaError` to `SchemaErrors` before wrapping), but each is **degraded**: pandera does not attach the frame to a non-lazy error, so `_parse_reference_errors` cannot recover the offending key values. Document on the parameter; do not guard |
| 16 | A target's contract is a **Dimension** | Legal and supported. Star-schema enforcement means its only foreign key is the self-reference, which under `check_existing_foreign_key=True` is checked against stored rows **unioned with** the frame's own — a real check, not a no-op |
| 17 | A bundle carries both a dimension target and a variable target referencing its new members | Out of scope by decision. The variable's rows fail against stored dimension values because nothing has been uploaded yet. This is an **ingestion-sequence** problem, not a validation one, and no ordering of the loop fixes it |
| 18 | The bundle handed to the handler was never validated (step 1 skipped) | Works, and may claim different rows than a coerced bundle would, because filters match `astype(str)`. The handler is **agnostic** by decision; the trap is already documented on `Target.filters` |

## 4. Implementation Decisions & File Paths

### Shape: a primitive plus a loop over it

`validate_targets` delegates to `validate_target` per target and collects; it does no
resolution of its own. This is the same layering `get_target_data` already has over
`extract_target_data` / `transform_target_data`, and it puts the "unknown contract"
failure in exactly one place instead of two.

```python
def validate_target(
    self,
    target_name: str,
    contract: BaseContract | None = None,
    resolver: ContractResolver | None = None,
    check_existing_primary_key: bool = False,
    check_existing_foreign_key: bool = False,
    lazy: bool = True,
) -> pd.DataFrame:
    ...   # get_target_data(target_name) -> contract.validate_data(df, resolver=..., ...)

def validate_targets(
    self,
    resolver: ContractResolver,          # required: the loop cannot know N contracts otherwise
    targets: list[str] | None = None,
    check_existing_primary_key: bool = False,
    check_existing_foreign_key: bool = False,
    lazy: bool = True,
) -> dict[str, pd.DataFrame]:
    ...   # loop validate_target, collect SchemaValidationError, raise TargetValidationError
```

`contract` beats `resolver` when both are given. `resolver` is required on the loop and
optional on the primitive — asymmetric on purpose: the primitive can work entirely from
what the caller holds, the loop cannot.

**Rejected:** a `contracts: dict[str, BaseContract]` parameter on the loop (the caller then
writes `{t.contract: resolver.resolve(t.contract) …}`, which is the loop we are supplying);
a `validate_targets` accepting a `CrossClient` (inverts the layering and puts platform
knowledge inside `submission/`); putting the method on `SubmissionContract` (the handler
imports the contract, so the reverse edge is a real module cycle, and the bundle lives on
the handler).

### Return type keyed by target name

`dict[str, pd.DataFrame]`, keyed by **target name, not contract name**. Contract-uniqueness
is a relaxable guard (ADR 0004) while a target's name is its identity, so a contract-keyed
result would silently collapse two entries if that guard were ever relaxed.

The frames are post-coercion — the ones step 3b uploads — so the loop's work is not thrown
away.

### Files to create

- **`src/crosscontract/submission/exceptions.py`** — `TargetValidationError`. A plain
  `Exception`, **not** a subclass of `SchemaValidationError`: that class exists to wrap and
  parse a pandera exception, this one holds a mapping and parses nothing, so inheriting
  would give it a constructor it cannot honour and an `.errors` meaning something else.
  Its own module rather than beside the handler, matching
  `contracts/schema/exceptions/` and `crossclient/exceptions/`.
- **`src/tests/submission/test_validate_targets.py`** — see §7.

### Files to modify

- **`src/crosscontract/submission/submission_handler.py`** — the two methods. The class
  docstring currently states "There is deliberately no method that runs every target"; that
  paragraph must be rewritten, not merely appended to.
- **`src/crosscontract/submission/__init__.py`** — export `TargetValidationError`.
- **`src/crosscontract/__init__.py`** — export `TargetValidationError` alongside
  `SchemaValidationError`. A caller cannot write `except` against a name they cannot import.
- **`src/crosscontract/crossclient/services/__init__.py`** and
  **`src/crosscontract/crossclient/__init__.py`** — export `ClientContractResolver`.
  Promoting it to public API carries the same breaking-change obligation ADR 0005 recorded
  for `ContractResolver` itself.
- **`.claude/CLAUDE.md`** — the `submission/` architecture section lists only
  `submission_contract.py` and `extraction/`; it is already missing `submission_handler.py`
  and should gain both it and the validation surface.

Not touched: `contracts/`, the adapter, the check classes, `registry/`, `release/`. This
feature is composition of things that already exist.

There is **no docs page** for `submission/` in `mkdocs.yml` at all — a pre-existing gap,
not created by this work, and not closed by it.

## 5. Data & Schema Changes

**No pydantic model changes.** `SubmissionContract`, `ExtractionInstructions`, and `Target`
are untouched; no field is added, no validator changes. **No platform or database change** —
nothing new is sent to or read from the CROSS platform beyond calls the `ContractResolver`
protocol already defines.

### Input contract

| Parameter | Type | Meaning |
|---|---|---|
| `target_name` / `targets` | `str` / `list[str] \| None` | Which targets. `None` = all, declaration order |
| `contract` | `BaseContract \| None` | Primitive only. Wins over the resolver |
| `resolver` | `ContractResolver \| None` (required on the loop) | Supplies target contracts *and* existing values — one object, two jobs, per ADR 0005 |
| `check_existing_primary_key` | `bool = False` | Pass-through to `validate_data` |
| `check_existing_foreign_key` | `bool = False` | Pass-through to `validate_data` |
| `lazy` | `bool = True` | Pass-through to `validate_data` |

### Output contract

- `validate_target` → `pd.DataFrame`, the coerced frame for that target.
- `validate_targets` → `dict[str, pd.DataFrame]`, keyed by target name.

### `TargetValidationError`

```python
TargetValidationError(errors: dict[str, SchemaValidationError])
    .errors      -> dict[str, SchemaValidationError]
    .to_list()   -> list[dict]   # each row of each sub-error, plus a "target" key
    .to_pandas() -> pd.DataFrame # pd.DataFrame(self.to_list())
```

`to_list()` is the wire-relevant one: `cross_back` serialises `SchemaValidationError.to_list()`
into a 422 body today, and this keeps that shape with one extra column so a submitter reads
the same table and now knows which target each row came from. `to_pandas()` exists because
the notebooks use it interactively and a provider validating a bundle is exactly that
audience.

## 6. Related ADRs

- **[ADR 0004 — Submission contracts carry their extraction instructions](../adrs/0004-submission-contracts-carry-extraction-instructions.md)**
  — *amended 2026-08-31 by this work.* The "no method runs every target" consequence is
  withdrawn and the decision it was protecting (collect vs. abort) is made here. Its second
  decision — extraction *names* target contracts and never resolves them — **stands**, and
  this PRD complies: the primitive takes a contract, the loop takes a caller-supplied
  resolver, and nothing in `submission/` constructs one or imports `crossclient`.
- **[ADR 0005 — One contract resolver supplies definitions and stored values](../adrs/0005-one-contract-resolver-supplies-definitions-and-values.md)**
  — complied with by using the single protocol for both jobs rather than adding a
  contract-lookup parameter beside a values parameter; by keeping the resolver optional on
  the primitive; and by reusing the `check_existing_*` names and polarity rather than
  inventing a third spelling. Its "silently wrong rather than a crash" criterion is what
  justifies the contract-name mismatch guard (edge case 3).
- **[ADR 0006 — Validation is a set of check objects, derived in one place](../adrs/0006-validation-is-a-set-of-check-objects.md)**
  — complied with by adding **no checks**. Every check this feature runs is derived by
  `PanderaAdapter._derive_checks` from the target contract's own schema; this layer supplies
  values (via the resolver) and never checks. The opt-in key semantics carry through
  unchanged: with both flags `False`, a target's primary key and external foreign keys are
  not checked, and that is the documented default, not a gap.
- **[ADR 0001 — Dimensions are strict trees](../adrs/0001-dimensions-are-strict-trees.md)**
  — relevant only via edge case 16: a dimension target's hierarchy checks run regardless of
  the flags, because they need nothing from outside the frame.

## 7. Testing Strategy

**No network in any test.** The resolver is a duck-typed double, following the
`RecordingResolver` pattern in
[test_validate_data.py](../../src/tests/contracts/contracts/test_validate_data.py) — it
satisfies the protocol structurally without inheriting, and records its calls so a test can
assert *that nothing was fetched* as well as what was.

New file **`src/tests/submission/test_validate_targets.py`**, reusing the existing
`contract` fixture shape from
[test_submission_handler.py](../../src/tests/submission/test_submission_handler.py)
(two profiles, targets with and without their own transformations) plus small target
contracts built the way `_contract()` builds them there.

### Unit tests

**Happy path**

- One target validates and returns a coerced frame (assert a dtype actually changed, not
  just that no exception was raised).
- `validate_targets` with `targets=None` returns one entry per target, keyed by target name.
- A named subset validates only those targets — assert the resolver was **not** asked for
  the others' contracts.
- With both flags `False`, the resolver receives `resolve` calls and **no `get_data` calls**.
  This is the "no unexpected fetch" property and deserves its own test.

**Collection**

- Two of three targets fail → `TargetValidationError` with exactly those two keys.
- `to_list()` rows each carry a `target` key and the union matches the per-target errors.
- `to_pandas()` returns a frame with one row per `to_list()` entry.
- The message names the failing targets.

**Wiring failures raise immediately** (one test each, asserting no `TargetValidationError`)

- Unknown target name → `KeyError`.
- Resolver returns `None` → `ValueError` naming target and contract.
- Mismatched `contract` → `ValueError`.
- Neither `contract` nor `resolver` → `ValueError`.
- Wiring failure on target 2 of 3 → raises immediately; do **not** assert on whether
  target 3 ran, so the test does not pin an implementation detail.

**Edge cases**

- **A target claiming no rows validates and returns an empty frame** — the one behaviour
  in this design asserted from reasoning rather than observation (does `strict=True` +
  `coerce=True` hold on zero rows?). Write it first; if it fails, the design needs
  revisiting, not the test.
- A forgotten `drop_columns` (extra column) is a collected `SchemaValidationError`, not an
  exception escaping the loop.
- `targets=[]` returns `{}`.
- `contract=` beats `resolver=`: pass a contract that validates and a resolver whose
  contract would fail, assert it passes and the resolver's `resolve` was never called.
- `lazy=False` still yields one `SchemaValidationError` per failing target.

### Integration-ish

- `ClientContractResolver` is importable from `crosscontract.crossclient`, and
  `TargetValidationError` from both `crosscontract` and `crosscontract.submission` — cheap
  import tests that fail loudly if an `__init__` export is forgotten.

### Coverage

The repository runs `coverage`; this feature should land at 100% of its own new lines. Every
branch above is reachable without a platform connection, so there is no excuse for a
`pragma: no cover` in the new code.
