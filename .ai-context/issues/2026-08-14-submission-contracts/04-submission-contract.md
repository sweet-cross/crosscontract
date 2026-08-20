# WP3 — `SubmissionContract` and column tracking

## Context
**Part of PRD:** [2026-08-14-submission-contracts.md](../../prds/2026-08-14-submission-contracts.md) (§5.3, §3.1, §3.4, §7.4)

The piece that joins the two halves: a `CrossContract` whose `tableschema` describes
the submission file and whose `extraction` block says how to split it. It also owns
the routing invariants, because the schema cannot see `routing_column` — that lives one
layer up.

## Acceptance Criteria
- [ ] `SubmissionContract(CrossContract)` exists with `contract_type` pinned to `Literal["Submission"]`, plus `project_name: str` and `extraction: ExtractionInstructions`.
- [ ] `routing_column` naming a field absent from `tableschema.fields` raises — with a regression test using the literal string `"variable."` (the real typo in the reference YAML, where a stray period sits inside the value before an inline comment).
- [ ] A routing field that is not `type: string` raises.
- [ ] A routing field that is not `required: true` raises.
- [ ] A routing field carrying an authored `enum` raises (it is derived).
- [ ] **Acceptance test:** `SubmissionContract.from_file()` loads the reference cross2025 YAML, yields 24 targets with unique filters and resolving profile references, and the routing values derived from those targets equal *as a set, exactly* the 24-entry enum of the legacy `submission_cross2025.yaml`.
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
    contract_type: Literal["Submission"] = Field(  # type: ignore[assignment]
        default="Submission",
        description="The type of the contract.",
    )
    project_name: str = Field(
        description="CROSS Project the extracted data is written under."
    )
    extraction: ExtractionInstructions
```

Notes on the shape:

- Inheriting `CrossContract` (rather than composing `BaseContract, CrossMetaData` as a
  sibling) keeps the metadata block, `from_file`, the server methods, and
  `validate_references`'s `enforce_star_schema=True` default — which is the correct
  behaviour here, since the submission foreign keys all point at dimensions.
- `contract_type` narrows the inherited `ContractType`, so it carries the same
  `# type: ignore[assignment]` the schema subclasses use. It must **not** be
  `exclude=True`: unlike `table_type`, it is authored and serialized, not injected.
- `project_name` names the CROSS **Project** the extracted data is written under
  (`add_data(..., project_name=...)`). The name matches the existing `ContractService`
  keyword rather than shortening to `project`. It is inert for extraction itself and
  replaces the `Extractor.name` key of the legacy registry, which doubled as the
  project name.
- No overrides of `to_server()` / `from_server()`. Whether the platform stores the
  extraction block whole is the platform's concern; nothing here needs to assume it.

### Deferred: where the derived routing enum is assembled

The routing field's `enum` is derived from the targets rather than authored, so
something must assemble it before data is validated against the submission contract.
**Where that lives is deliberately left open** — a property on the model, a helper on
`ExtractionInstructions`, or the future validator that checks data against the
contract. It is not needed to land this task and no `to_contract()` method is written
here.

The acceptance test above is therefore phrased against the derived *values*, not
against any particular method, and passes whichever site is eventually chosen.

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

**Dependencies:** requires task 01 (`Submission` contract type and `SubmissionSchema`)
and task 03 (`ExtractionInstructions`).
