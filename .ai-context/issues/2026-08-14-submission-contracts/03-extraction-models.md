# WP2 — `Target` and `ExtractionInstructions` in `submission/extraction/`

## Context
**Part of PRD:** [2026-08-14-submission-contracts.md](../../prds/2026-08-14-submission-contracts.md) (§4.1, §5.2, §3.2, §3.3)

The declarative half of a submission contract: which rows go to which target contract,
and the ordered transformations applied on the way. These models are the ingress
mirror of `FetchSpecMixin` — they carry a contract **name** and deliberately never
resolve it, keeping the whole spec loadable and executable with no platform
connection.

## Acceptance Criteria
- [ ] `Target` and `ExtractionInstructions` exist, both `extra="forbid"`.
- [ ] Scalar `filters` normalises to `{routing_column: value}`; the mapping form passes through unchanged.
- [ ] Duplicate scalar filters across targets raise.
- [ ] Mapping filters where one target's dict is a subset of another's raise (subset containment is the overlap test).
- [ ] `filters` naming a column absent from the parent's `tableschema.fields` raises — *(deferred to task 04 if the parent schema isn't reachable from here; see notes)*.
- [ ] Two targets naming the same `contract` raise.
- [ ] An empty `targets` list raises (`min_length=1`).
- [ ] A `transformation_profile` naming an undefined profile raises.
- [ ] A defined-but-unreferenced profile **warns**, does not raise.
- [ ] A profile with zero steps is accepted.
- [ ] Resolution order is asserted explicitly: profile steps first, then the target's own `transformations`.
- [ ] `contract` is validated against `CONTRACT_NAME_PATTERN` with `max_length=100`.

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
    filters: str | dict[str, str]           # normalised to dict by the parent
    contract: str                           # CONTRACT_NAME_PATTERN, max_length=100
    transformation_profile: str | None = None
    transformations: list[TransformationUnion] = []

class ExtractionInstructions(BaseModel):
    routing_column: str = "variable"
    transformation_profiles: dict[str, list[TransformationUnion]] = {}
    targets: list[Target]                   # min_length=1
```

Scalar-`filters` normalisation needs `routing_column`, which lives on the parent — so
it is an `ExtractionInstructions`-level `@model_validator(mode="after")`, **not** a
field validator on `Target`. Same for the uniqueness and overlap checks, which are
cross-target.

`filters` is typed scalar-or-mapping from the start even though every current case is
scalar: it costs nothing now and means multi-column matching later is not a breaking
change to authored YAML. The name deliberately matches `FetchSpecMixin.filters` —
the same concept (a row allow-list keyed by column) in the egress direction.

Reference `TransformationUnion` through a module-level alias here rather than inline,
so narrowing the admissible set per Build spec later stays a one-line change (PRD §4.4).

**Note on the filter-column check.** Validating that a `filters` key names a real
field requires the submission `tableschema`, which lives on `SubmissionContract`. If
it cannot be reached from `ExtractionInstructions`, move that criterion to task 04 and
say so in the module docstring rather than dropping it.

**Tests:** `src/tests/submission/extraction/` (PRD §7.2).

**Dependencies:** requires task 02 (`TransformationUnion`). Blocks task 04.
