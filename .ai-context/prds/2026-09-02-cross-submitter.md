# CrossSubmitter PRD

## 1. Overview

`CrossSubmitter` is the **Data provider**'s entry point to the CROSS platform — the
provider-side mirror of `CrossRegistry`. Where the registry answers *"give me this
variable, resolved and labelled"* for a consumer, the submitter answers *"is my delivered
bundle acceptable?"* for a provider, and later *"submit it"*.

Today a provider who wants to check a bundle before delivering it must assemble the whole
pipeline by hand: build a `CrossClient`, build a `CrossContractResolver` from its
`contracts` service, construct a `SubmissionHandler`, remember to validate the bundle
against its own `SubmissionContract` first, remember to ask for `unclaimed_rows()`, and
only then call `validate_targets`. Every one of those steps is public and works; nothing
composes them, and the two easily-forgotten steps (bundle schema, unclaimed rows) are
exactly the two whose omission fails silently.

`CrossSubmitter` composes them in one call, over a connection it owns. It performs no
validation itself — it sequences steps that already exist and supplies the policy joining
them.

Scope of this PRD is **validation only**. `submit` ships as an explicit
`NotImplementedError` because the `cross_back` platform does not yet expose the endpoint.

Terms used here (**Submitter**, **Submission validation**, **Unclaimed rows**,
**Contract resolver**, **Existing values**) are defined in
[CONTEXT.md](../CONTEXT.md).

## 2. Core Requirements

1. **`CrossSubmitter` is constructed like `CrossRegistry`** — `username` + `password`, or
   an existing `client`; `ValueError` if neither is complete. No `base_url` parameter (an
   existing `CrossClient` is the escape hatch for a non-default host, exactly as for the
   registry).
2. **It builds and privately holds a `CrossContractResolver`** over its client's
   `contracts` service. The resolver is not a constructor parameter and not public.
3. **`validate_submission(contract, df)` runs the three steps in order**, stopping at the
   first that fails:
   1. `contract.validate_data(df, ...)` — the bundle against the submission contract's
      own schema.
   2. `handler.unclaimed_rows()` — raise `UnclaimedRowsError` if any row is unclaimed.
   3. `handler.validate_targets(resolver, ...)` — every target against the contract it
      names.
4. **It returns the per-target validated frames** — `dict[str, pd.DataFrame]`, straight
   from `validate_targets`, so a provider sees what the platform will derive from their
   bundle.
5. **`check_existing_primary_key` and `check_existing_foreign_key` default to `True`**,
   deviating deliberately from the `False` used elsewhere in the package. `lazy=True`
   forwarded unchanged. All three are forwarded to steps 1 and 3.
6. **Extraction runs on the bundle as delivered.** The coerced frame returned by step 1 is
   discarded and never fed to the handler.
7. **`UnclaimedRowsError` carries the unclaimed frame**, not a count.
8. **`submit(contract, df)` raises `NotImplementedError`** with a message naming the
   missing platform endpoint as the reason.
9. **`CrossSubmitter` and `UnclaimedRowsError` are exported** from
   `crosscontract.submission` and from the top-level package.
10. **No lifecycle methods** — no `close()`, no context manager (mirrors `CrossRegistry`;
    `CrossClient` registers its own `atexit` cleanup).

### Explicitly out of scope

- `validate_contract` / `write_contract` for the single-contract case. Already reachable
  as `client.contracts.get(name).validate_dataframe(df)` and `.add_data(df)`; adding them
  here would be a second spelling of a working path. Decided against recording even as a
  TODO.
- Resolving a submission contract **by name** from the platform. Widening the parameter
  from `SubmissionContract` to `SubmissionContract | str` later is backward-compatible, so
  nothing needs reserving now.
- Any `on_unclaimed=` policy knob.
- Giving `CrossRegistry` a `base_url` parameter.

## 3. Edge Cases & Error Handling

The exception type identifies which step broke, without inspection:

| Situation | Behaviour |
|---|---|
| Neither `client` nor complete credentials given | `ValueError`, message copied in shape from `CrossRegistry.__init__` |
| Authentication fails | Propagates from `CrossClient.authenticate` (`httpx.HTTPStatusError`); the submitter adds nothing |
| Bundle fails its own schema (step 1) | `SchemaValidationError`; targets never attempted, `unclaimed_rows` never called |
| Bundle has unclaimed rows (step 2) | `UnclaimedRowsError` carrying the frame; targets never attempted |
| A target's data fails (step 3) | `TargetValidationError`, one entry per failing target — every target attempted first |
| A target names a contract the platform doesn't have | `ValueError` from `validate_target`, propagates immediately (wiring error, not a data error). See §6 on why this is not collected |
| A target's `filters` name a column absent from the bundle | `KeyError` from `_mask_target`, propagates. Note this surfaces in **step 2**, not step 3, since `unclaimed_rows()` masks every target |
| Bundle is empty (0 rows) | Steps 1 and 2 pass vacuously; step 3 returns a frame per target, each empty. **Not** an error — `validate_target` documents an empty result as legitimate |
| Contract has no targets | `validate_targets` returns `{}`; step 2 raises `UnclaimedRowsError` for *every* row if the bundle is non-empty. Correct: nothing claims anything |
| A column named by a target's filters exists but the bundle schema doesn't declare it | Step 1 passes (extra columns are not rejected), step 2 works. Acceptable |
| Submission contract carries foreign keys on the bundle schema | Step 1's `check_existing_foreign_key=True` checks them against stored values via the resolver — meaningful, not decoration |
| Same contract read twice for existing values (once in step 1, once per target) | Accepted. No caching in this PRD; `CrossContractResolver` is stateless and each `get_data` is an HTTP round-trip. Flagged in §7 as a known cost, not a defect |
| Provider passes a `CrossContract` that isn't a `SubmissionContract` | Pydantic/type error at `SubmissionHandler` construction. No extra guard added |
| Bundle column widened to `float64` by a missing value, filters authored as `"2030"` | Rows surface as **unclaimed** → `UnclaimedRowsError`. This is the trap documented on `Target.filters`; raising is the correct outcome and makes the trap loud instead of silent |
| Caller wants unclaimed rows as a warning | Not supported by `validate_submission`. Documented escape hatch: build a `SubmissionHandler` and call `unclaimed_rows()` directly |

## 4. Implementation Decisions & File Paths

### Files to create

- **`src/crosscontract/submission/submitter.py`** — `CrossSubmitter`.

### Files to modify

- **`src/crosscontract/submission/exceptions.py`** — add `UnclaimedRowsError`, sibling of
  `TargetValidationError`.
- **`src/crosscontract/submission/__init__.py`** — export `CrossSubmitter`,
  `UnclaimedRowsError`.
- **`src/crosscontract/__init__.py`** — re-export both; add to `__all__`.
- **`src/crosscontract/submission/submission_handler.py`** — docstring only: state that
  `SubmissionHandler` remains offline and that `CrossSubmitter` is the connected
  composition. No behavioural change.
- **`docs/`** — a short usage page if the docs tree covers the registry equivalently
  (check before assuming; not a blocker).

### Why `submission/` and not `crossclient/` or a new package

Decided in [ADR 0007](../adrs/0007-the-submitter-is-the-provider-side-mirror-of-the-registry.md).
Short form: `crossclient/` is the layer *beneath* this one, so a `services/` home inverts
the layering; a top-level `submitter/` package mirroring `registry/` was rejected as a
package for one slim class when `submission/` already names the concept.

**The cost, stated so it is not rediscovered as a bug:** `submission/` becomes the only
domain package importing `crossclient`, so importing it pulls in `httpx`. The import edge
is one-way and cycle-free — verified: `crosscontract/__init__.py` loads `.crossclient`
before `.submission`, and a direct `import crosscontract.submission` runs the parent
`__init__` first.

### Shape

Slim class, three responsibilities: hold the connection, sequence the steps, own the
policy. Per CLAUDE.md house style — no helper functions, no module constants, no
defensive branches. A `SubmissionHandler` is constructed **per call**, not held: the
submitter is stateless across calls, and holding one would tie a connection object to one
bundle.

```python
class CrossSubmitter:
    def __init__(self, username=None, password=None, client=None): ...
    def validate_submission(
        self, contract, df,
        check_existing_primary_key=True,
        check_existing_foreign_key=True,
        lazy=True,
    ) -> dict[str, pd.DataFrame]: ...
    def submit(self, contract, df) -> None:  # raises NotImplementedError
        ...
```

`__init__` is the `CrossRegistry.__init__` branch copied verbatim, plus
`self._resolver = CrossContractResolver(client.contracts)`.

## 5. Data & Schema Changes

No contract, schema, or platform-payload changes. No new pydantic models —
`CrossSubmitter` is a plain class, like `CrossRegistry` and `CrossClient`.

### Input / output contract

| | |
|---|---|
| **Input** | `contract: SubmissionContract` (the object, not a name), `df: pd.DataFrame` (the bundle as delivered) |
| **Output** | `dict[str, pd.DataFrame]` — validated, coerced frames keyed by **target name** (not contract name) |
| **Raises** | `SchemaValidationError` (step 1) · `UnclaimedRowsError` (step 2) · `TargetValidationError` (step 3) · `ValueError`, `KeyError` (wiring) |

### `UnclaimedRowsError`

Mirrors `TargetValidationError`: an exception carrying the data needed to act, not a
formatted string. Holds the unclaimed `pd.DataFrame`; message states the row count and
points at the frame. Placed in `submission/exceptions.py` beside its sibling.

## 6. Related ADRs

- **[ADR 0007 — The Submitter is the provider-side mirror of the Registry](../adrs/0007-the-submitter-is-the-provider-side-mirror-of-the-registry.md)**
  *(written for this work)*. Governs the name, the home, the layering, and the three
  consequences: the submitter validates nothing itself, extraction runs on the raw bundle,
  and the `check_existing_*` defaults deviate deliberately.
- **[ADR 0005 — One Contract resolver supplies definitions and values](../adrs/0005-one-contract-resolver-supplies-definitions-and-values.md)**.
  The submitter holds exactly one `ContractResolver` and uses it for both purposes.
  Also the source of the caveat that a client-side **Data validation** sees only what the
  caller may read, and is therefore advisory — the platform re-validates on ingest. The
  submitter must not claim otherwise in its docstrings.
- **[ADR 0006 — Validation is a set of check objects](../adrs/0006-validation-is-a-set-of-check-objects.md)**.
  Key checks are opt-in, and `False` suppresses a check *entirely* rather than only its
  stored-value half. This is precisely why requirement 5 flips the defaults to `True`:
  under ADR 0006's semantics the `False` default would silently skip primary-key
  uniqueness within the bundle's own target data.
- **[ADR 0004 — Submission contracts carry extraction instructions](../adrs/0004-submission-contracts-carry-extraction-instructions.md)**.
  Target overlap is deliberately legal, so `validate_submission` must not treat a row
  claimed twice as an error. Only *un*claimed rows raise. The still-open contested-rows
  question in `TODO.md` stays open and stays answerable, because the handler continues to
  report rather than act.
- **[ADR 0001 — Dimensions are strict trees](../adrs/0001-dimensions-are-strict-trees.md)**.
  Indirect: duplicate primary keys reaching the platform break the **Sum invariant**,
  which is the concrete harm requirement 5 guards against.

**Wiring vs. data failures.** `validate_targets` already distinguishes these — an
unresolvable contract escapes immediately while data failures are collected. The submitter
inherits that distinction untouched: a broken *setup* fails loud and early, a broken
*dataset* is reported in full.

## 7. Testing Strategy

Tests live in **`src/tests/submission/test_submitter.py`**, mirroring the source layout.

### Fixtures and mocks

Follow the existing seams — no new infrastructure:

- **Client**: patch `crosscontract.crossclient.crossclient.CrossClient.authenticate` as
  `src/tests/crossclient/conftest.py` does, then pass the client via `client=`.
- **Resolver**: the `Mock(spec=ContractResolver)` pattern from
  `src/tests/submission/test_validate_targets.py`. Inject by assigning `_resolver` on a
  constructed submitter — the constructor takes no resolver by design, and reaching for
  the private attribute in a test is the accepted cost of that decision. Prefer stubbing
  `client.contracts` where it reads more naturally.
- **Contract + bundle**: reuse `src/tests/submission/example_submission.yaml` and the
  inline `SubmissionContract` fixtures already in `test_validate_targets.py` rather than
  authoring a fourth submission contract.

### Unit tests

**Construction**
- Credentials build a `CrossClient` (patched `authenticate`); `client=` is used as given.
- Neither → `ValueError`.
- `_resolver` is a `CrossContractResolver` over `client.contracts`.
- No `close`/`__enter__` on the class (guards against a well-meaning future addition).

**Sequencing — the core of the suite**
- Happy path: returns `dict[str, pd.DataFrame]` keyed by target name.
- Bundle fails → `SchemaValidationError`, **and** `unclaimed_rows` / `validate_targets`
  were never called (assert on spies — the ordering guarantee is the feature).
- Unclaimed rows present → `UnclaimedRowsError` whose frame equals the expected rows, and
  `validate_targets` never called.
- Target data fails → `TargetValidationError` with one entry per failing target.
- Unresolvable target contract → `ValueError` propagates, not collected.

**Forwarding**
- Defaults: assert `validate_data` and `validate_targets` each receive
  `check_existing_primary_key=True`, `check_existing_foreign_key=True`, `lazy=True`.
- Explicit `False`/`False`/`False` reaches both steps.

**Raw-bundle guarantee (regression test for the subtlest decision)**
- Bundle with an integer-typed column containing a missing value, so step 1's coercion
  would widen it to `float64` and break `astype(str)` filter matching. Assert the run
  succeeds and every target claims its rows — i.e. the coerced frame was discarded. This
  is the test that fails loudly if someone later "optimises" by feeding step 1's output
  into the handler.

**Edge cases**
- Empty bundle → steps 1–2 pass, per-target empty frames, no raise.
- Contract with no targets + non-empty bundle → `UnclaimedRowsError` for every row.
- `submit` → `NotImplementedError`, message mentions the platform endpoint.

**Exports**
- `from crosscontract import CrossSubmitter, UnclaimedRowsError` works.

**`UnclaimedRowsError`** (in `src/tests/submission/test_exceptions.py`, beside
`TargetValidationError`'s tests)
- Carries the frame; message states the row count.

### Not tested

No live-platform integration test. Every platform interaction is `CrossContractResolver`,
already covered in `src/tests/crossclient/`; duplicating it here would test `httpx`, not
the submitter.

### Coverage note

`SubmissionHandler` tests must stay HTTP-free. ADR 0007 records that the package layout no
longer enforces this — it is now convention, and this suite is where a violation would
first show up as an unexpected import.
