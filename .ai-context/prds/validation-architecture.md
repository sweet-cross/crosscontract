# Validation architecture — agreed design and work packages

Status: agreed, not yet implemented. Written 2026-08-29; revised the same day after a
design review that changed the protocol shape, the `validate_data` defaults, and the
client migration. Terminology lives in the *Validation* section of
[`CONTEXT.md`](../CONTEXT.md).

This is step 1 of a four-step sequence:

1. **Make validation more convenient** ← *this document*
2. Provide validation for submission contracts
3. (a) Improve the validation approach on the server (`cross_back`)
   (b) Use submission contracts for batch submission to the server

A fourth strand was split off while implementing this one — making internal consistency
unconditional at the validator, and the `checks` shape that may replace the boolean
flags. It is *not* step 4 of the sequence above; it is a follow-on to this document. See
**Deferred to a follow-on PRD** below.

Steps 2 and 3a both bind to the signature introduced here, which is why the
signature — not the amount of code — is the expensive part.

---

## The problem

Data validation needs referenced *values*: primary-key values already stored for
the contract, and foreign-key values from the contracts it references. Fetching
them is I/O, so the library cannot do it. Today the caller pre-materializes two
dictionaries and passes them into `TableSchema.validate_dataframe`.

The consequence is that every caller wraps the schema call in a function that
re-derives the same four lines of schema semantics:

```python
fk_contract_name = fk.reference.resource or contract_name   # self-ref -> own table
fk_field_names   = fk.reference.fields                      # referenced side
foreign_key_values[tuple(fk.fields)] = [...]                # keyed by referring side
```

This exists twice today, identically:

- `ContractResource.get_foreign_key_values` —
  [contract_resource.py:317](../../src/crosscontract/crossclient/services/contract_resource.py#L317)
- `cross_back`'s `validate_dataframe_against_contract` —
  `backend/app/api/crud/contract_data.py:21`

Submission execution (step 2) would be the third. Confusing `fk.fields` with
`fk.reference.fields` is silently wrong rather than a crash, so this is knowledge
that belongs to the schema and must not be copy-pasted into consumers.

### What is *not* the problem

- **`resolvers.py` is not dead code.** `ContractResolver` is implemented by
  `DbContractResolver` in `cross_back/backend/app/api/crud/resolvers.py` and used
  at contract creation. It resolves contract *definitions*; the gap is that
  nothing resolves reference *values*.
- **The pandera conversion is not scattered.** It lives in one adapter with one
  entry point. A "Validator class that takes the schema and does the pandera
  conversion" would be `PanderaPandasAdapter` renamed.

---

## The agreed design

### One resolver, one job

`ContractResolver` gains a data lookup. It stays a **single** protocol:

```python
@runtime_checkable
class ContractResolver(Protocol):
    @abstractmethod
    def resolve(self, name: str) -> "BaseContract | None": ...

    @abstractmethod
    def get_data(
        self, name: str, columns: list[str], *, unique: bool = True
    ) -> pd.DataFrame: ...
```

Splitting it into a `resolve`-only protocol and a `get_data`-only one was considered and
rejected. The two lookups are one job seen twice: **a contract cannot answer anything
about the world outside itself**, and these are the two things it must ask — what other
contracts *are*, and what values already *exist* under them. One supplier answers both.
Two protocols would name the split rather than the concept, and every real implementor
would carry both members anyway.

The cost is real and accepted: `validate_references` now asks for a `get_data` it never
calls, and `FakeResolver` grows a stub. In exchange there is one name for one concept —
see **Contract resolver** in [`CONTEXT.md`](../CONTEXT.md).

Four properties of this shape were argued out and should not be re-opened without a
reason:

- **`get_data`, not `get_reference_values`.** The supplier's job is to return columns
  from a contract. Only the caller knows the values are used for reference checking, so
  naming the method for the caller's intent leaks the consumer into the interface.
- **`unique` is keyword-only, and it is a cost hint.** Correctness never depends on it:
  both the primary-key and foreign-key checks build a `set()`, so duplicates are
  harmless. What it buys is wire cost — without it a client-side source downloads every
  row of a dimension over HTTP to build a key set, on exactly the hot path this serves.
  Keyword-only because `get_data(name, cols, True)` is unreadable and collides
  positionally with `ContractService._get_data`'s `filters` parameter.
- **Scope is a documented obligation, not a parameter.** `get_data` must return rows
  *irrespective of the caller's read permissions*. `cross_back` already knows this — its
  integrity reads pass `project_ids=None` deliberately, because a scoped read hides keys
  the caller cannot see, so duplicates land and rows referencing another project's
  dimension value are wrongly *rejected*. The library has no notion of projects and
  never should, so this cannot be parameterized; it is stated in the protocol docstring.
- **Column order is the library's problem, not the supplier's.** `fk.fields` and
  `fk.reference.fields` correspond *positionally* — the model says so twice and enforces
  equal length — but `itertuples` follows the frame's own column order, not the
  requested one. `validate_data` therefore reindexes (`df[columns]`) before
  tuple-ifying. Without it a composite foreign key can silently compare `(a, b)` against
  `(b, a)`. This is not stated as an obligation because the library simply guarantees
  it.

### `@abstractmethod`, not a plain Protocol and not an ABC

`DbContractResolver` **explicitly subclasses** `ContractResolver` rather than
satisfying it structurally. Adding a method to a plain Protocol therefore gives it
an inherited `...` body: it constructs fine, `get_data` returns `None`,
`isinstance` still answers `True`, and the failure surfaces as an `AttributeError`
deep inside validation at data-submission time.

Decorating the protocol members with `@abstractmethod` makes a stale explicit
subclass fail at construction:

```
TypeError: Can't instantiate abstract class Inherits without an implementation
           for abstract method 'get_data'
```

while duck-typed implementors still satisfy the protocol structurally. **That
combination is the point, and it is what a full ABC would take away.** An ABC forces
*every* implementor to inherit. A Protocol with `@abstractmethod` lets each one choose:

- **Real implementors inherit**, and get the construction-time failure.
  `ClientContractResolver` (WP3) does, and `DbContractResolver` already does.
- **Test doubles duck-type**, and skip the ceremony — `FakeResolver` in
  [test_contract_reference_validation.py:6](../../src/tests/contracts/contracts/test_contract_reference_validation.py#L6)
  and `RecordingResolver` in
  [test_validate_data.py](../../src/tests/contracts/contracts/test_validate_data.py)
  both satisfy the protocol without a base class.

Two earlier arguments for this choice were made and have since been overtaken; they are
recorded here so they are not re-proposed. Neither survives:

- *"`FakeResolver` stays untouched."* False once the protocol carried two members — it
  needs a `get_data` stub under either choice.
- *"`ClientContractResolver` should not inherit across a layer boundary."* WP3 decided
  the opposite, on purpose: failing loudly at construction is worth more than avoiding
  the inheritance edge, and `crossclient` already imports from `contracts` anyway.

So `cross_back` should **keep** its explicit base rather than dropping it — inheriting is
now the convention for real implementors, and it is what turns a missed method into a
build-time error instead of an `AttributeError` at data-submission time.

Note also that `ContractResolver` is now exported from `crosscontract.contracts`. It was
reachable only by full module path before, which is what made adding `get_data` cheap.
It is public API from here on, so a further change to it is a breaking change for any
implementor outside these two repositories.

### `BaseContract.validate_data`

```python
def validate_data(
    self,
    df: pd.DataFrame,
    resolver: ContractResolver | None = None,
    check_existing_primary_key: bool = False,
    check_existing_foreign_key: bool = False,
    lazy: bool = True,
) -> pd.DataFrame
```

It owns the whole derivation — PK lookup against `self.name`, FK target names via
`fk.reference.resource or self.name`, referenced columns via `fk.reference.fields`,
keying by `tuple(fk.fields)`, and order-safe tuple-ification
(`df[columns].itertuples(...)`) of the returned frames — then hands materialized values
down to `tableschema.validate_dataframe`, which is unchanged.

**The flags name the *external* half and read in the positive.**
`check_existing_*=True` means "also consult stored values"; `False` means "check what is
in the frame". This replaced an earlier `skip_primary_key_validation` /
`skip_foreign_key_validation` pair, which was abandoned because the two defaults
contradicted each other: `skip_foreign_key_validation=False` with `resolver=None` reads
as "I am checking foreign keys" and then raises for every contract with an external
reference — i.e. for **ValueVariable**, the main contract type in the model. The
positive polarity fixes that at the name rather than at the exception: a caller reading
their own call site can see what they did and did not ask for, so a silently weaker
validation is no longer silent.

`cross_back` already names it this way (`check_primary_key` / `check_foreign_keys`) and
inverts at the boundary; this deletes that inversion.

**The resolver is optional.** `BaseContract` exists for use *outside* the CROSS platform,
where there is nothing to pass — requiring one would make the method unusable for the
audience the class exists to serve. A null-object resolver is not a workaround: after
WP1, an empty frame means "the referenced table is empty" and fails every row, so `None`
is the only safe way to say "I have no source". Requesting either check without a
resolver raises from `validate_data`, which is the only place that knows the contract
name *and* the parameter names, and can therefore name the remedy.

**`backend` is deliberately absent.** It has one legal value and the schema layer
already defaults it; add it if a second backend ever lands.

**The parameter is `resolver`, not `references`** — one concept, one word, matching
`validate_references` and the **Contract resolver** entry in the glossary.

**Why this lives on the contract and not the schema.** Both reference validation
and data validation are, in substance, checks on a *schema*. What a contract adds
is a **name** and **policy defaults**. The name is load-bearing here: the
primary-key lookup targets the contract's own table, and a self-referencing
foreign key (`resource: None`) does too. `TableSchema` has no name, so only a
contract can drive a resolver. This is the same reason `validate_references` lives
on `BaseContract`, and it is what makes `validate_data` a real method rather than
passthrough for symmetry.

`validate_references` stays where it is. Its `enforce_star_schema` default is
genuine contract-level policy — `False` on `BaseContract`, `True` on
`CrossContract` — and cannot move to the schema, because `Submission` and
`General` both resolve to the same plain `TableSchema` class.

### The flags are orthogonal to the resolver — structurally, not by rule

`resolver=None` must **not** mean "check nothing". Schema-only validation is a real mode
that the client relies on today and offline callers need. Under `skip_*` this had to be
defended as a rule; under `check_existing_*` it is structural — the flags only ever
named the existing-values half, so what can be established from the frame alone is
outside their reach by construction.

What "the frame alone" *should* establish:

| | `check_existing_*=False` | `check_existing_*=True` |
|---|---|---|
| **primary key** | non-null + uniqueness **within the frame** | the above, plus no collision with stored keys |
| **foreign key**, self-referencing | integrity against the frame's own rows | the above, plus stored rows |
| **foreign key**, external | not checked | checked against the referenced contract |

**The validator does not yet deliver the left column, and WP2 does not change that.**
`check_existing_*=False` currently maps onto `skip_*=True`, which suppresses the check
entirely — so in-frame primary-key uniqueness and self-referencing foreign keys go
unchecked. That is exactly the client's behaviour today, so nothing regresses; the name
is the specification and the validator is brought up to it separately. See
*Deferred to a follow-on PRD* below.

### Client-side defaults are unchanged

`ContractResource.validate_dataframe` performs no data fetch by default
([contract_resource.py:220](../../src/crosscontract/crossclient/services/contract_resource.py#L220)),
deliberately, to avoid network calls. The platform re-validates authoritatively on
ingest. Relaxing this is a **later** decision, gated on the architecture landing first.

WP3 must prove *that* property — **no data fetch** — rather than "the same checks run".
The two came apart when the flags were renamed: the follow-on PRD will deliberately
change which checks run by default, while the no-network guarantee has to survive it.
The client's own parameters are renamed to match the library's, so the two stop speaking
opposite polarities.

---

## Rejected alternatives

- **A stateful `ContractValidator(schema)`.** Its one real benefit was caching the
  built pandera schema across calls. Submission validates one frame per target
  against a *different* contract each time, so the cache never hits. `CrossContract`
  is already the object that holds a schema and gets passed around.
- **A "lookup plan" returned by the contract** (`contract.reference_lookups()`),
  with the caller doing the fetching. Async-agnostic, but leaves the wrapper
  function in place on every consumer, which is the thing this work exists to
  remove.
- **An async path in the library.** `crosscontract` has zero `async def` / `await` and
  stays that way. `cross_back`'s reads are async, and bridging them to a synchronous
  `get_data` is its own business — whether by prefetching into a snapshot (the pattern
  `DbContractResolver.prefetch_for` already uses for `resolve`) or by dispatching onto
  the running loop from the worker thread `validate_dataframe` is already called in.
  That choice does not reach this design and is out of scope here. Worth knowing when it
  is made: a prefetch must know target names *and* columns up front, so it re-derives
  part of what this work centralizes; an on-demand bridge does not.
- **A `ReferenceValues` parameter object.** It described the *output* of
  resolution with no story about who produces it. The resolver is that story.

---

## Work packages

### WP1 — Distinguish "no existing values supplied" from "the referenced table is empty"

**Depends on:** nothing. Land first.
**PR:** own PR, `fix:`.

`_get_foreign_key_check` at
[pandera_adapter.py:538](../../src/crosscontract/contracts/schema/adapters/pandera_adapter.py#L538)
tests truthiness, which merges two different situations:

- `None` — nothing supplied for an external FK and not skipped. Genuinely *cannot*
  validate. `ValueError` is correct and is documented behaviour on
  `TableSchema.validate_dataframe`; **keep it**.
- `[]` — the referenced table exists and is empty. Every referring row *does*
  fail. This is a validation result, not an inability, and must raise
  `SchemaValidationError`.

Distinguishing `None` from `[]` is the entire fix. It keeps the documented
contract intact rather than breaking it. Note `ContractResource.get_foreign_key_values`
currently writes `[]` unconditionally, including when the referenced contract has
no rows, so this is reachable today.

Two things were checked and are worth recording, because they bound the change:

- **It is a one-site fix.** `_check_reference_inputs([])` already passes (`[]` is a
  list, and `all()` over an empty list is `True`), so there is no second guard to touch.
- **The distinction matters for external foreign keys only.**
  `_get_primary_key_check` has the same truthiness shape but no equivalent bug: for a
  primary key, `[]` and `None` genuinely mean the same thing — in-frame uniqueness runs
  either way. Self-referencing foreign keys are likewise unaffected, since the in-frame
  values are the valid set.

**Verification:** tests for both arms — external FK with `None` still raises
`ValueError`; external FK with `[]` raises `SchemaValidationError` whose
`to_list()` names the failing rows. Pin the surprising half of that second arm too: a
row whose foreign-key value is **null** still passes against an empty referenced table
(SQL semantics, `is_null_row`), so an empty table fails only the non-null rows. Existing
self-reference tests unchanged.

### WP2 — `ContractResolver.get_data` + `BaseContract.validate_data` ⟵ critical path

**Depends on:** WP1 (builds on corrected semantics).
**PR:** with WP3, `feat:` — a protocol with no implementor is dead code.

Carries the architectural risk: this signature is what step 2 consumes and what
step 3a binds to. Everything else in this document is mechanical.

Contains the `get_data` addition to `ContractResolver`, the `@abstractmethod`
decoration, the scope obligation docstring, and `validate_data` with its derivation.

**Verification:**
- A dict-backed fake resolver proves the derivation — include a case where
  `fk.fields` and `fk.reference.fields` **differ**, which is where a direction
  error hides.
- A **composite** foreign key whose supplier returns the requested columns in a
  different order still validates. The `df[columns]` reindex is what makes this pass;
  without it the failure is silent rather than loud, which is why it needs its own test.
- A stale explicit subclass raises `TypeError` at construction.
- `FakeResolver` gains a `get_data` stub. It keeps working untouched at runtime —
  nothing calls `isinstance`, and mypy does not cover `src/tests/` — but it no longer
  satisfies the protocol structurally, and the stub is what keeps that honest.
- Requesting either check with `resolver=None` raises a `ValueError` naming the contract
  and both remedies — unconditionally on the flag-plus-`None` combination, not only when
  the schema happens to have keys to fetch.
- With both flags `False` and no resolver, `get_data` is never called.

### WP3 — Migrate the client onto it

**Depends on:** WP2.
**PR:** with WP2.

The first real consumer, and the proof the design holds. If the client cannot be
expressed cleanly as a `ContractResolver` plus a `validate_data` call, the
design is wrong — better to find that here than in `cross_back`.

- **A `ClientContractResolver` adapter, not a promoted `_get_data`.**
  `ContractService._get_data(name, columns, filters, unique)` is nearly the protocol
  already, but promoting it would make data readable by name straight off the service,
  and the client's shape is deliberate: users hold a `ContractResource` and read through
  it. `_get_data` stays private. The adapter wraps a `ContractService` and is the
  client-side implementor of the protocol, mirroring `DbContractResolver` on the server.
- **The adapter carries `resolve` too**, because the protocol is one piece:
  `self._service.get(name).contract`, with `ResourceNotFoundError` mapped to `None`.
  That is the bill for the single-protocol decision — and also its dividend, since it
  makes `validate_references` runnable client-side against the live platform before
  `create()`, which nothing can do today.
- Scope for WP3: no underscore on the class name, no top-level export, no convenience
  property on `CrossClient`. `ContractResource.validate_dataframe` constructs one
  internally. Exposing it is a one-line follow-up if wanted.
- `ContractResource.validate_dataframe` routes through `contract.validate_data`, passing
  `check_existing_primary_key=False` / `check_existing_foreign_key=False` explicitly —
  the same no-network behaviour under the new polarity;
  `get_primary_key_values` / `get_foreign_key_values` collapse.
- Its own parameters are renamed to match, so the client and the library stop speaking
  opposite polarities. Breaking, and acceptable on 0.x.
- Fix the `ContractResource.validate_dataframe` docstring, which documents
  "Default is False" for two flags that both default to `True`. Under the rename the
  defaults genuinely are `False`, so the fix is to say what `False` means.

**Verification:** the existing `test_contract_resource.py` suite passes with its mocks
re-pointed, and a test proves the default call performs **no data fetch**. That is the
property that must hold — not "the same checks run", which the follow-on PRD will
deliberately change.

### WP4 — Record the decision

**Depends on:** WP2 landing (write once the shape is real).
**PR:** own PR, `docs:`.

- **ADR 0005** — why **one** resolver rather than two protocols; why the derivation
  lives in the library; why scope is an unparameterized obligation; why the flags name
  the existing-values half rather than being `skip_*`; why the resolver is optional; why
  `validate_data` sits on the contract; and why `None` ≠ `[]` for external foreign keys
  *only*.
- **The handoff section** for the follow-on PRD — see *Deferred to a follow-on PRD*. The
  deliverable is the written handoff, not the planning session.
- **`CONTEXT.md`** — **done**, ahead of WP2. A *Validation* section now defines
  **Well-formedness**, **Reference validation**, **Data validation**, **Contract
  resolver**, and **Existing values**, organized by what each check must fetch from
  outside the contract: nothing, other contracts' definitions, or stored values. Two
  ambiguities are flagged there — the three validations have no distinct names in code
  (`validate_structural_integrity` / `validate_references` / `validate_dataframe` at
  three layers), and "reference" is load-bearing twice, which is why the inputs to data
  validation are **existing values** and never "reference values".

---

## Critical path and grouping

```
WP1 ──▶ WP2 ──▶ WP3
                 └──▶ WP4 (concurrent)
```

| PR | Contents | Conventional commit |
|---|---|---|
| 1 | WP1 | `fix:` |
| 2 | WP2 + WP3 | `feat:` |
| 3 | WP4 | `docs:` |

## Deferred to a follow-on PRD

Two requirements were agreed while implementing WP2 and deliberately **not** folded into
it. That planning session has since been held, and the result is
[check-based-validation.md](check-based-validation.md), which supersedes the notes below
and answers the open question in favour of retiring the `None`-arm `ValueError`.

- **Internal consistency should be unconditional.** In-frame primary-key uniqueness and
  self-referencing foreign keys ought to be checked *always*, whatever the flags say —
  the flags govern only whether **existing values** are additionally consulted. This
  belongs at the validator and does not touch `validate_data`, which merely passes values
  or does not.
- **The open question, left open on purpose.** Either `skip_primary_key_validation` /
  `skip_foreign_key_validation` change meaning to cover only the existing-values
  comparison, or they disappear from the validator entirely with presence-or-absence of
  values as the instruction. The second retires WP1's `None`-arm `ValueError` and drops
  two public parameters from `TableSchema.validate_dataframe`; WP1's `[]` semantics
  survive either way.
- **The shape already visible.** Whether the boolean pair becomes `checks: list[Check]`.
  What forces it is per-check granularity: a foreign key has three states — self-
  referencing and checkable in-frame, external and needing values, or not checked
  externally — and two booleans cannot carry that. A schema mixing self-referencing and
  external foreign keys is where the boolean version has no correct answer.

Why deferred rather than absorbed: WP2's value is the *signature* that `cross_back` and
submission both bind to. Renaming the flags once, now, is cheap; changing what the
validator does underneath them is a separate blast radius, and doing both at once would
make WP2 impossible to review against its own acceptance criteria.

## Out of scope

- Async anything in `crosscontract`.
- Step 2's submission validation (consumes WP2's signature; separate PRD).
- Step 3a's `cross_back` rework, including dropping its explicit protocol base.
- Relaxing the client's no-fetch default — deliberate, and gated on this landing.

## Known follow-ups noticed while designing this

- The adapter's `ValueError` for an external foreign key with no supplied values —
  `Cannot validate foreign key ('region_id',) as no referenced values are provided.` —
  names neither the contract, nor the target, nor the remedy. The flag rename means
  `validate_data` no longer routes callers into it (its own guard fires first, with a
  better message), so this now only affects direct `TableSchema.validate_dataframe`
  callers. Lower priority than when it was first noted, and possibly moot depending on
  how the follow-on PRD resolves the `None` arm.
- `BaseContract.validate_references` skips `target == self.name`
  ([base_contract.py:150](../../src/crosscontract/contracts/contracts/base_contract.py#L150)),
  but `_validate_self_reference` already raises at construction if any FK spells
  the contract's own name. The branch is unreachable on a constructed, unmutated
  contract — the model is not frozen and has no `validate_assignment`, so it is
  defensive against post-construction assignment only. Decide whether to keep it.
- `contracts/schema/validation/` holds only `validate_dataframe` while reference
  validation lives in `contracts/contracts/base_contract.py`. Since both are
  checks on a schema, the package looks lopsided. Not worth moving now — it is a
  public method on a public class and the move buys nothing until step 3a.
