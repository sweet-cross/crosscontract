# WP3 — `SubmissionContract`, `to_contract()`, and column tracking

## Context
**Part of PRD:** [2026-08-14-submission-contracts.md](../../prds/2026-08-14-submission-contracts.md) (§5.3, §3.1, §3.4, §7.4)

The piece that joins the two halves: a `CrossContract` whose `tableschema` describes
the submission file and whose `extraction` block says how to split it. It also owns
the routing invariants (the schema can't see `routing_column`) and `to_contract()`,
which derives the routing field's `enum` from the targets — the mechanism that makes
the spec, not a separately maintained contract, the source of truth.

## Acceptance Criteria
- [ ] `SubmissionContract(CrossContract)` exists with `contract_type` pinned to `Literal["Submission"]`, plus `project: str` and `extraction: ExtractionInstructions`.
- [ ] `routing_column` naming a field absent from `tableschema.fields` raises — with a regression test using the literal string `"variable."` (the real typo in the reference YAML, where a stray period sits inside the value before an inline comment).
- [ ] A routing field that is not `type: string` raises.
- [ ] A routing field that is not `required: true` raises.
- [ ] A routing field carrying an authored `enum` raises (it is derived).
- [ ] `to_contract()` returns a plain `CrossContract` that revalidates cleanly under `extra="forbid"` — `extraction` and `project` stripped, derived `enum` injected into the routing field.
- [ ] **Acceptance test:** `SubmissionContract.from_file()` loads the reference cross2025 YAML, yields 24 targets with unique filters and resolving profile references, and `to_contract()` produces a `variable` enum equal *as a set, exactly* to the 24-entry enum of the legacy `submission_cross2025.yaml`.
- [ ] Round-trip `from_file` → `model_dump` → `model_validate` is stable.
- [ ] `SubmissionContract` is exported from the package's public surface.

## Implementation Details

**Create:**
- `src/crosscontract/contracts/contracts/submission_contract.py`

**Modify:**
- `src/crosscontract/contracts/__init__.py` — export `SubmissionContract`
- `src/crosscontract/__init__.py` — public surface

**Model shape (PRD §5.3):**

```python
class SubmissionContract(CrossContract):
    contract_type: Literal["Submission"] = "Submission"
    project: str
    extraction: ExtractionInstructions

    def to_contract(self) -> CrossContract: ...
```

`project` names the CROSS **Project** the extracted data is written under
(`add_data(..., project_name=...)`). It is inert for extraction itself and replaces the
`Extractor.name` key of the legacy registry, which doubled as the project name.

**Why `to_contract()` exists.** `CrossContract` is `extra="forbid"`, so a stored
`SubmissionContract` would break the backend's existing
`CrossContract.from_server(contract_entry.contract)` call in
`get_contract_validate_dataframe`. Emitting the contract half only keeps the platform
untouched.

### Decision required: `to_contract()` and `contract_type` (PRD §5.3)

`Submission` needs platform acceptance before it can be stored. Until that lands,
`to_contract()` may need to emit `General`. Decide alongside task 01 and keep the two
consistent.

### Decision required: how far column tracking goes (PRD §3.4)

Column references are **order-dependent**: after `rename_columns {timestamp: year}`, a
subsequent `cast_column year` is correct and `cast_column timestamp` is not. Static
checking therefore needs the column set tracked *through* the pipeline, not compared
against the source fields.

- **(a)** Every transformation declares `output_columns(input_columns) -> set[str]`.
  Strongest checking; raises the cost of adding a transformation, cutting against the
  extensibility goal.
- **(b) — recommended.** The method is optional; a transformation that does not
  implement it returns `None`, tracking stops there, and the remainder goes unchecked.
- **(c)** No static checking; rely on runtime failures.

Under (b) the following raise: a `rename_columns` key not in the tracked set; a
`drop_columns` naming an untracked column; a `column_name` not in the tracked set.
Strictness on `drop_columns` is deliberate — it is what removes the
`uploaded_by` / `uploaded_at` wart, which exists today only because `admin_tools`
reads back from the server while the backend reads the raw upload.

**Coordinate with task 02** before finalising: if (b) is adopted, the three new
transformations should implement the hook while they are being written.

**Test fixture.** Copy the reference YAML from
[`.ai-context/prds/cross2025_submission.yaml`](../../prds/cross2025_submission.yaml)
into `src/tests/contracts/contracts/` so tests don't depend on `.ai-context/`. Either
fix the `routing_column: variable.` typo in the copy, or keep it and assert the loader
rejects it, then use a corrected copy for the remaining assertions.

**Tests:** `src/tests/contracts/contracts/` (PRD §7.3, §7.4).

**Dependencies:** requires task 01 (`Submission` contract type) and task 03
(`ExtractionInstructions`).
