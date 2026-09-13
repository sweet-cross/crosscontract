# Submission Contracts — Step 0: `crosscontract` Prerequisites PRD

> **Status:** idea / draft. Written 2026-09-13 while planning server-side
> Submission Contracts in cross_back. To be revised and discussed before
> implementation.

## Feature summary (shared by Steps 0–3)

The CROSS platform (cross_back) replaces its deprecated, hard-coded result
upload (`backend/app/api/routes/result.py`, `Cross2025ResultProcessor`) with
**Submission Contracts** stored on the server. A Submission Contract is this
package's `SubmissionContract`: a spec describing one delivered table (the
**bundle**) and how it splits into **targets**, each validated against an
existing Contract.

**Terminology**
- **Submission Contract** — the stored spec. Belongs to exactly one Project; a
  Project may own several. Has no data table and no Draft/Active lifecycle on
  the server.
- **Submission** — one uploaded bundle for a Submission Contract. A bundle is
  always complete. Several Submissions for the same contract are history, not
  overwrites.

**Agreed decisions (server side)**
1. Submission Contracts get their own `submission_contract` table, carrying
   `allow_submissions` on the row.
2. Only Managers of the owning Project (or system administrators) create and
   delete Submission Contracts and toggle `allow_submissions`. Editing the
   payload is deferred.
3. Targets are checked at creation against the stored Contracts, via
   `crosscontract` and the server's `ContractResolver`.
4. Submitters and Managers of the owning Project may upload when
   `allow_submissions` is true.
5. Uploads are CSV or parquet, one table matching the contract's
   `tableschema`. No Excel, no server-side reshaping.
6. Validation reuses the `CrossSubmitter.validate_submission` sequence —
   bundle schema, unclaimed rows, target validation — with foreign keys and
   dimension granularity checked, and primary keys checked **for uniqueness
   within the bundle only**, never against stored data.
7. The bundle is stored as delivered, serialized to parquet, with a
   `submission` record.
8. Extraction of Submissions into data tables is out of scope.
9. `/result` and its processors are removed; no production data is migrated.

**Sequence**

| Step | Repo | Scope | Depends on |
|---|---|---|---|
| **0** | **`crosscontract`** | **In-frame primary-key check always on; target resolution check for `SubmissionContract`** | — |
| 1 | cross_back | `submission_contract` model + migration; create / list / get / delete; target check at creation | 0 (part B) |
| 2 | cross_back | Managers/admins toggle `allow_submissions` | 1 |
| 3 | cross_back | `submission` model; upload endpoint; validation; parquet storage; removal of `/result` | 0 (part A), 1, 2 |

The server-side PRDs live in cross_back under
`.ai-context/prds/2026-09-13-submission-{1,2,3}-*.md`.

---

## 1. Overview

Two small changes in `crosscontract` that the server-side submission flow
needs, released together before cross_back Step 1/3 bump the dependency.

- **Part A — the in-frame primary-key check is always on.**
  `BaseContract.validate_data(check_existing_primary_key=False)` currently
  drops the primary-key check entirely, including uniqueness within the frame.
  The server wants "unique within the bundle, never compared against stored
  data". The adapter already supports exactly that: per ADR 0006, `None`
  means "do not check", while an empty collection means "check it, with
  nothing to compare against". `validate_data` should pass `[]` instead of
  `None` when the flag is off (or no resolver is given), so `IsValidPrimaryKey`
  always runs; the flag then governs only the comparison with stored values.
- **Part B — a target resolution check for `SubmissionContract`.** Nothing
  today verifies, at authoring time, that the Contracts a Submission
  Contract's targets name actually exist. The server needs one call, analogous
  to `validate_references`, that resolves every target through a
  `ContractResolver` and reports all failures together.

Both serve the data provider too: `CrossSubmitter.validate_submission` gains
in-bundle duplicate detection even with `check_existing_primary_key=False`, and
a provider can check a Submission Contract before posting it.

## 2. Core Requirements

**Part A**
- `BaseContract.validate_data` passes `primary_key_values=[]` when
  `check_existing_primary_key` is `False`, and when no `resolver` is given;
  it passes the resolved stored values when the flag is `True`.
- Consequently, for any contract declaring a primary key, `validate_data`
  always rejects null and duplicated key values within the frame.
- Contracts without a primary key are unaffected.
- Foreign-key and granularity behaviour stay exactly as they are (still
  opt-in, `None` when off). This PRD does not change them.
- Docstrings updated wherever they describe "False suppresses the check
  entirely" for the primary key: `BaseContract.validate_data`,
  `SubmissionHandler.validate_target`, `SubmissionHandler.validate_targets`,
  `CrossSubmitter.validate_submission`, and the client's
  `ContractResource.validate_data` (`crossclient/services/contract_resource.py`).
- ADR 0006 amended and `CONTEXT.md` updated (see §6).

**Part B**
- A public method on `SubmissionContract` that takes a `ContractResolver`
  and verifies every target's `contract` resolves. Working name:
  `validate_targets(resolver)`, or an override of `validate_references` —
  see open questions.
- All failing targets are collected and raised together as one `ValueError`
  (matching `validate_references`' error style), naming target and contract.
- A target naming another **Submission** contract is rejected: targets are
  validated as ordinary variables and a Submission contract has no stored
  data.
- Pure: resolves definitions only, never reads stored values.

**Done** when both parts are released on PyPI with tests, updated docstrings,
the ADR amendment and the CHANGELOG entry produced by semantic release.

## 3. Edge Cases & Error Handling

**Part A**

| Case | Behaviour |
|---|---|
| Contract has no primary key | No check derived (`self.schema.primaryKey` is falsy) — unchanged |
| Duplicate key rows in the frame, flag `False` | **Now** raises `SchemaValidationError` (previously passed) |
| Null in a key column, flag `False` | **Now** raises — `IsValidPrimaryKey` includes `IsNotNull`. Stricter than "uniqueness only"; intended, since a null key is never valid |
| Composite primary key | Uniqueness over the column tuple, as with stored values today |
| No resolver at all (`validate_data(df)`) | Also checks in-frame uniqueness now. Existing callers that validated frames with duplicate keys on purpose start failing |
| Flag `True` with resolver | Unchanged: in-frame uniqueness plus comparison with stored values |
| `lazy=False` | Unchanged semantics; first failure may now be a primary-key failure |
| Hierarchical `Dimension` frames | Their `id` primary key is now checked for duplicates even without a resolver — arguably a fix, but visible |
| Submission contract bundle schema | Declares no primary key by rule, so no change at bundle level; the check applies to each target's rows |
| Large frames | One extra uniqueness pass per validation; acceptable, no mitigation planned |
| Tests asserting duplicates pass with the flag off | Must be found and updated or deleted; roughly a dozen tests call `validate_data` with the flag off or defaulted |

**Part B**

| Case | Behaviour |
|---|---|
| All targets resolve | Returns `None` |
| One or several targets do not resolve | One `ValueError` listing all of them |
| Target resolves to a `Submission` contract | Reported as a failure in the same collection |
| Resolver raises (network/DB error) | Propagates unchanged — the caller decides its error policy (as in `validate_references`) |
| Same contract named by two targets | Already rejected by `ExtractionInstructions._check_contract_unique` at parse time; not re-checked |
| Target's transformations would not produce the target contract's columns | **Not** checked — impossible without data. Documented as out of scope |
| Target contract exists but is Draft/Retired on the server | Not a `crosscontract` concern: `ContractResolver` has no status notion. The server decides |

## 4. Implementation Decisions & File Paths

- **Part A reuses the existing `None` / empty-collection distinction** from
  ADR 0006 rather than adding a new flag or a tri-state. It is a one-branch
  change in `validate_data`; the adapter and `IsValidPrimaryKey` are untouched.
- **Part B lives on `SubmissionContract`**, not on `SubmissionHandler`: it is
  a question about the spec, answerable with no bundle, and the handler's scope
  is explicitly "targets against data".

**Files to be modified**
- `src/crosscontract/contracts/contracts/base_contract.py` — `validate_data`
  passes `[]`; docstring
- `src/crosscontract/submission/submission_contract.py` — target resolution
  method
- `src/crosscontract/submission/submission_handler.py` — docstrings
- `src/crosscontract/submission/submitter.py` — docstring; optionally call the
  Part B check in `validate_submission` (open)
- `src/crosscontract/crossclient/services/contract_resource.py` — docstring
- `.ai-context/adrs/0006-validation-is-a-set-of-check-objects.md` — amendment
- `.ai-context/CONTEXT.md` — the "key checks are opt-in" relationship line

**Files to be created**
- None beyond tests.

**Open questions**
1. **Part B API shape.** Override `validate_references(resolver)` on
   `SubmissionContract` (one entry point the server already calls on contract
   creation — `create_contract_db` uses it) or a separate `validate_targets`
   (name clashes with `SubmissionHandler.validate_targets`, which validates
   data). An override keeps the server generic; a distinct name keeps
   "references" meaning foreign keys.
2. **Release type.** Part A makes validation stricter for existing callers.
   `feat:` (minor) or a breaking-change marker? The package is pre-1.0.
3. **Should `CrossSubmitter.validate_submission` run Part B first**, so a
   broken Submission Contract fails as a wiring error before any data is
   touched? Today an unresolved target surfaces as a `ValueError` during
   stage 3.
4. **Split into two PRs?** Parts A and B are independent; cross_back Step 1
   needs only B and Step 3 needs only A.

## 5. Data & Schema Changes

- No model or schema changes.
- **Behavioural contract change (Part A):**

  | `check_existing_primary_key` | resolver | before | after |
  |---|---|---|---|
  | `False` | any | no primary-key check | in-frame not-null + uniqueness |
  | `True` | none | `ValueError` | `ValueError` (unchanged) |
  | `True` | given | in-frame + stored | in-frame + stored (unchanged) |

- **New contract (Part B), sketch:**
  ```
  SubmissionContract.<method>(resolver: ContractResolver) -> None
      raises ValueError  # all unresolved / invalid targets, collected
  ```

## 6. Related ADRs

- **ADR 0006 — validation is a set of check objects.** Part A **amends** the
  section "Why the key checks are opt-in" for the primary key only: in-frame
  uniqueness needs nothing from outside the data, which is the original goal
  the ADR reversed, so it returns for the primary key. Foreign keys stay
  opt-in — an unchecked external reference needs outside values to mean
  anything. The amendment must state the reason (submission bundles validated
  without comparison against stored data) and the consequence (bare
  `validate_data(df)` now rejects duplicate keys).
- **ADR 0004 — submission contracts carry extraction instructions.** Part B
  adds an authoring-time check on the targets those instructions name; targets
  still never resolve at parse time, only when a resolver is handed in.
- **ADR 0005 — one contract resolver supplies definitions and values.** Part B
  uses the definitions half only.
- **ADR 0007 — the submitter is the provider-side mirror of the registry.**
  The server now runs the same sequence as `CrossSubmitter`; keeping their
  primary-key semantics identical is the point of Part A.
- **ADR 0009 — fact data is reported at one granularity per group.** Unchanged;
  granularity stays opt-in.

## 7. Testing Strategy

**Part A** — `src/tests/contracts/contracts/test_validate_data.py`
- Parametrized over flag / resolver combinations (table in §5): duplicates
  rejected, nulls in key rejected, unique frame passes.
- Composite primary key duplicates rejected with the flag off.
- Contract without a primary key: duplicates of any column still pass.
- With the flag on and a resolver: in-frame duplicate and stored collision
  are reported as distinct failures (unchanged, regression guard).
- Sweep existing tests calling `validate_data` / `validate_target(s)` /
  `validate_submission` with the primary-key flag off; update fixtures that
  relied on duplicates passing.
- `src/tests/submission/test_validate_targets.py`: a target with duplicate
  keys fails with `check_existing_primary_key=False`.

**Part B** — `src/tests/submission/test_submission_contract.py`
- All targets resolve → no error (resolver mocked, as in the existing
  submission `conftest.py` helpers `resolver_for` / `resolver_returning`).
- One and several unresolved targets → one `ValueError` naming all.
- Target resolving to a `SubmissionContract` → failure.
- Resolver exception propagates unchanged.
- The method never calls `resolver.get_data`.
