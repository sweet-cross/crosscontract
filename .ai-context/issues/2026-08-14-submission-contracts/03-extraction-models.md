# WP2 — `Target` and `ExtractionInstructions` in `submission/extraction/`

## Context
**Part of PRD:** [2026-08-14-submission-contracts.md](../../prds/2026-08-14-submission-contracts.md) (§4.1, §5.2, §3.2, §3.3)

The declarative half of a submission contract: which rows go to which target contract,
and the ordered transformations applied on the way. These models are the ingress
mirror of `FetchSpecMixin` — they carry a contract **name** and deliberately never
resolve it, keeping the whole spec loadable and executable with no platform
connection.

## Acceptance Criteria
- [x] `Target` and `ExtractionInstructions` exist, both `extra="forbid"`.
- [x] Scalar `filters` normalises to `{routing_column: value}`; the mapping form passes through unchanged.
- [x] Repeated filters across targets are **accepted** when the targets name different contracts — the same rows may feed two contracts through different transformations.
- [x] `filters` naming a column absent from the parent's `tableschema.fields` raises — *(deferred to task 04 if the parent schema isn't reachable from here; see notes)*.
- [x] Two targets naming the same `contract` raise. This is the only uniqueness check: it catches every case that breaks (identical targets, and different variables feeding one contract) without forbidding legitimate fan-out.
- [x] An empty `targets` list raises (`min_length=1`).
- [x] A `transformation_profile` naming an undefined profile raises.
- [x] `contract` is validated against `CONTRACT_NAME_PATTERN` with `max_length=100`.

## Implementation Details

**Create:**
- `src/crosscontract/submission/extraction/__init__.py`
- `src/crosscontract/submission/extraction/target.py` — `Target`
- `src/crosscontract/submission/extraction/extraction_instructions.py` — `ExtractionInstructions`

`submission/` is a top-level package, peer to `release/`, holding the submission
contract, the extraction models, and later the code that executes them (PRD §4.1).
`transformations/` stays pure — no spec models are added there.

**Imports are unconstrained here.** Because `submission/` sits outside `contracts/`,
importing `crosscontract.transformations` wholesale is safe — the leaf-import
convention the earlier `contracts/extraction/` layout required no longer applies, since
`transformations → contracts` and `submission → transformations` both run one way.

**Model shapes (PRD §5.2):**

```python
class Target(BaseModel):
    filters: dict[str, str]                 # bare value expanded by the parent
    contract: str                           # CONTRACT_NAME_PATTERN, max_length=100
    transformation_profile: str | None = None
    transformations: list[TransformationUnion] = []

class ExtractionInstructions(BaseModel):
    routing_column: str = "variable"        # declared before `targets`
    transformation_profiles: dict[str, list[TransformationUnion]] = {}
    targets: list[Target]                   # min_length=1
```

`filters` is **mapping-only**. A bare value is accepted as authoring shorthand for
`{routing_column: value}` and expanded on load, so the field type describes the value
that is actually stored rather than the input that produced it — no consumer has to
narrow a union whose other arm is unreachable. The shorthand is documented in the
field's `description=`, which is also what a generated JSON Schema shows. This matches
`FetchSpecMixin.filters`, the same concept in the egress direction, which is likewise
mapping-only. (Its values are lists rather than scalars; the symmetry is in the shape,
not the value type.)

The expansion needs `routing_column`, which lives on the parent — so it is an
`ExtractionInstructions`-level `@field_validator("targets", mode="before")`, **not** a
field validator on `Target`. A *field* validator rather than a model validator so that
`info.data` already carries the validated, defaulted `routing_column`; a
`mode="before"` model validator would run before defaults are applied and force the
`"variable"` default to be duplicated. It must copy rather than mutate the incoming
dicts, and hand unexpected shapes straight through for pydantic to report.

The contract-uniqueness check is cross-target and works on validated values, so it is a
separate `@model_validator(mode="after")`.

Reference `TransformationUnion` through a module-level alias here rather than inline,
so narrowing the admissible set per Build spec later stays a one-line change (PRD §4.4).

**Note on the filter-column check.** Validating that a `filters` key names a real
field requires the submission `tableschema`, which lives on `SubmissionContract`. If
it cannot be reached from `ExtractionInstructions`, move that criterion to task 04 and
say so in the module docstring rather than dropping it.

**Tests:** `src/tests/submission/extraction/` (PRD §7.2).

**Dependencies:** requires task 02 (`TransformationUnion`). Blocks task 04.
