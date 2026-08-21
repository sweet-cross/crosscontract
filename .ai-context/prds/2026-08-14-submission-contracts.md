# Submission Contracts PRD

## 1. Overview

Data providers submit results as a **bundle**: one wide CSV holding rows for many
result contracts at once, distinguished by a `variable` column. Today the knowledge
of how to split that bundle lives in hand-written Python dictionaries — the
"extractors" in `cross_back/admin_tools/admin_tools/extractors/` — duplicated in the
backend's `Cross2025ResultProcessor`, carrying `lambda`s that cannot be authored,
reviewed, versioned, or shipped to a user.

This PRD introduces the **Submission contract**: a `CrossContract` that additionally
carries declarative **extraction instructions** describing, per submitted variable,
how to reshape the bundle rows and which result contract to validate them against.
It is authored as a single YAML file and loaded as a pydantic model.

Audience today is the CROSS team, who author these files on behalf of data providers.
Longer term the platform builds a submission endpoint from the stored contract, and
providers may author their own.

**Scope of this PRD: the format, the pydantic models, and their validation.**
Execution (actually applying the instructions to a DataFrame) is deliberately a
follow-on — see §4.7.

A validated, complete example for the CROSS 2025 campaign — all 24 extractors
translated — lives at
[`cross2025_submission.yaml`](./cross2025_submission.yaml) and is the reference the
models must load.

### The boundary that shapes everything else

A submission contract **names** its target contracts; it never **resolves** them.
Extraction is a pure function `submission file → DataFrame`, with `contract` a label
on the output. Validating that output against the target contract happens downstream
and is not this artifact's concern.

The consequence is that column drops and type casts stay authored rather than derived
from the target schema. That redundancy is accepted deliberately: it buys a spec that
loads, validates, and executes with no platform connection.

## 2. Core Requirements

1. **`SubmissionContract` is a `CrossContract`.** It inherits `name`, `title`,
   `description`, `tags`, `tableschema`, and the metadata block. Its `tableschema`
   describes the **submission file itself** and is the single authored source of
   truth for the bundle's shape.
2. **A new `contract_type: Submission`**, mapped onto the existing `General` table
   type via `CONTRACT_TYPE_TO_TABLE_TYPE`. No new schema class (§4.5).
3. **A `project_name` field** naming the CROSS **Project** that extracted data is
   written under (see §5.4).
4. **An `extraction` block** carrying:
   - `routing_column` — the field whose value selects a target (default `variable`).
   - `transformation_profiles` — named, ordered, reusable step lists.
   - `targets` — one entry per submitted variable.
5. **A target** carries `filters` (scalar shorthand resolving against
   `routing_column`, or an explicit column → value mapping), `contract` (the target
   contract **name**), an optional `transformation_profile`, and an optional
   `transformations` list.
6. **Profile-then-target, append-only.** A target's own steps run *after* its
   profile's. Profiles do not compose; there is no `extends`.
7. **Transformations are a discriminated union on `type`**, following the four
   existing `Annotated[..., Field(discriminator="type")]` sites in the package. Three
   new members are required (§5.1); this is the first Build spec to consume the union
   at all.
8. **The routing field's `enum` is derived** from the targets' filters, not authored.
   *Where* that derivation is assembled — a property on the model, a helper on
   `ExtractionInstructions`, or the validator that checks data against the contract —
   is deliberately left open (§5.3).
9. **One target feeds exactly one contract, and no contract is fed twice.** A
   repeated `contract` across targets is a spec error — after the routing column is
   dropped, the merged rows collide on that contract's primary key, which would
   otherwise only surface at insertion time. Repeated *filters* are **not** an error:
   two targets may select the same rows and transform them differently for two
   different contracts. Contract-uniqueness alone catches every case that breaks, so
   it is the only check.
10. **The spec validates standalone.** Structural checks (routing field present and
    well-formed, target contracts unique, profile references resolve, column
    references plausible) require no platform access. Only foreign-key checks on the submission
    schema need a resolver, via the existing `validate_references()` path.

### Definition of done

`SubmissionContract.from_file(".ai-context/prds/cross2025_submission.yaml")` loads,
and the routing values derived from its targets reproduce the `variable` enum of the
current `submission_cross2025.yaml` **exactly** — all 24 entries, no more, no fewer.
This has been confirmed by hand against the target list and is the acceptance test.

## 3. Edge Cases & Error Handling

All errors below are raised at **model construction / load time** unless marked
*(runtime)*, which flags behaviour the follow-on execution package must implement.

### 3.1 The routing column

| Case | Behaviour |
|---|---|
| `routing_column` names a field absent from `tableschema.fields` | **Raise.** The current annotated example has `routing_column: variable.` — a stray period before an inline comment yields the string `"variable."`. This validator is what catches it. |
| Routing field is not `type: string` | **Raise.** Routing values are compared as strings. |
| Routing field is not `required: true` | **Raise.** A null routing value cannot be routed. |
| Routing field carries an authored `enum` | **Raise.** It is derived; silently overwriting it would hide a real disagreement between author intent and target list. |

### 3.2 Targets and filters

| Case | Behaviour |
|---|---|
| `filters` names a column absent from `tableschema.fields` | **Raise.** |
| Two targets naming the same `contract` | **Raise.** After the routing column is dropped, merged rows collide on the target's primary key. Combining variables (e.g. net demand) is explicitly out of scope; revisit as a deliberate feature. |
| `targets` is empty | **Raise.** A submission contract that extracts nothing is meaningless. |
| `contract` violates `CONTRACT_NAME_PATTERN` | **Raise** (pydantic field pattern). |
| *(runtime)* A routing value in the data matches no target | **Raise.** Because the enum is derived, this surfaces earlier still — as a constraint violation when the bundle is validated against the submission contract itself. |
| *(runtime)* A target's filter matches zero rows | **Warn and skip.** Partial submissions are legitimate; this preserves the current backend's `continue`. |

### 3.3 Profiles

| Case | Behaviour |
|---|---|
| `transformation_profile` names an undefined profile | **Raise.** |
| Both `transformation_profile` and `transformations` given | **Allowed and expected** — this is the append case. |

### 3.4 Transformation references and ordering

The hard one. Column references are **order-dependent**: after
`rename_columns {timestamp: year}`, a subsequent `cast_column year` is correct and
`cast_column timestamp` is not. Static checking therefore requires tracking the column
set *through* the pipeline, not against the source fields.

**Decision required before implementation** (WP3):

- **(a)** Every transformation declares `output_columns(input_columns) -> set[str]`.
  Strongest checking; raises the cost of adding a transformation, which cuts against
  the extensibility goal.
- **(b) — recommended.** The method is optional; a transformation that does not
  implement it returns `None`, and column tracking stops at that point with the
  remainder unchecked. Full checking for the common cases, zero burden on exotic ones.
- **(c)** No static column checking; rely on runtime failures.

Under (b):

| Case | Behaviour |
|---|---|
| `rename_columns` key not in the tracked column set | **Raise.** |
| `drop_columns` naming an untracked column | **Raise.** Strict on purpose — this is what removes the `uploaded_by` / `uploaded_at` wart, which exists today only because `admin_tools` reads back from the server while the backend reads the raw upload. |
| `column_name` of a column transformation not in the tracked set | **Raise.** |
| Tracking stopped by an opaque transformation | **Skip remaining checks silently.** |
| *(runtime)* Rename produces duplicate labels | Already raised by the existing `rename_columns`. |

### 3.5 The new transformations *(runtime)*

| Case | Behaviour |
|---|---|
| `cast_column` to `integer` on a column containing NaN | **Keep the nulls.** The target is the pandas nullable `Int64`, so missing values survive the cast. Whether nulls are permitted is the target contract's business, decided at validation; extraction only reshapes. |
| `cast_column` to `integer` on floats with fractional parts | **Raise.** Silent truncation of `2050.5 → 2050` would corrupt data. |
| `parse_datetime_column` with unparseable values | **Raise** — pandas' own parse error propagates unchanged. It already names the offending value, so no bespoke message is added. |
| `parse_datetime_column` with `format: mixed` | Pass through to pandas as-is; `dayfirst` applies. |
| `drop_rows_by_value` removing every row | Falls through to the "zero rows" case in §3.2 — warn and skip. |
| `map_column_values` mapping a value onto one already present | **Known gap.** The two values merge silently, and on a foreign-key column that means duplicate primary keys downstream. See §5.5 — resolve or record in `TODO.md`, but do not leave it undecided. |

### 3.6 Serialization and platform interaction

| Case | Behaviour |
|---|---|
| Derived routing `enum` | Assembled from the targets, never authored. The assembly site is an open decision (§5.3); nothing in this scope depends on which is chosen. |
| Round-trip `from_file` → `model_dump` → revalidate | Must be stable. |
| YAML anchors in an authored file | Expand at load; re-dumping loses the sharing. Documented behaviour, not a bug. The reference example is deliberately anchor-free. |
| A `contract_type: Submission` payload sent to a platform that does not yet accept it | Adding the literal in this repo is inert for existing contracts. When the platform begins accepting submission contracts is its own rollout question, and errors would surface only on new submissions. Out of scope — see §4.7. |

## 4. Implementation Decisions & File Paths

### 4.1 Where submission lives

A new top-level `submission/` package, peer to `release/`, holding **all three parts**:
`SubmissionContract`, the extraction models, and — when it lands — the code that
executes them.

`release/` is the precedent and the exact mirror. This feature is repeatedly described
as the ingress counterpart of ADR 0003, and `release/data_package/` keeps its spec
models (`release_specification.py`), its orchestrator (`create_data_package.py`) and its
resolvers together at top level rather than under `contracts/`. Egress specs do not live
in `contracts/`; ingress specs should not either.

Three consequences settled this:

- **§4.7 already puts execution top-level**, peer to `release/`. Housing the spec models
  under `contracts/` would guarantee the submission concept ends up split across two
  packages.
- **`contracts/` describes what a dataset looks like.** Extraction is a process, not a
  structure. `transformations/` also stays pure — only transformations, no spec models.
- **The import graph rewards it.** `transformations/fetch/fetch_spec.py` already imports
  `CONTRACT_NAME_PATTERN` out of `contracts`, so `transformations → contracts` exists at
  package level. Extraction living under `contracts/` and importing `transformations`
  would close that cycle, avoidable only by the leaf-import convention. From
  `submission/`, both edges run one way and no convention is needed.

`SubmissionContract` lives here too. That it *is* a `CrossContract` is expressed by
inheritance, not by file location — `CrossDataPackageReleaseSpec` names contracts
without living among them. The public surface re-exports from `crosscontract/__init__.py`
either way, so the physical module is invisible to users.

### 4.2 Files to create

```
src/crosscontract/submission/__init__.py
src/crosscontract/submission/submission_contract.py                 # SubmissionContract
src/crosscontract/submission/extraction/__init__.py
src/crosscontract/submission/extraction/target.py                   # Target
src/crosscontract/submission/extraction/extraction_instructions.py  # ExtractionInstructions
src/crosscontract/transformations/transformation/union.py           # TransformationUnion
.ai-context/adrs/0004-submission-contracts-carry-extraction-instructions.md
```

`union.py` as its own module mirrors `contracts/schema/field_descriptors/`, which
splits the classes (`descriptors.py`) from the union (`field_descriptors.py`).

### 4.3 Files to modify

```
src/crosscontract/transformations/transformation/column_transformations.py
    + cast_column / CastColumn, parse_datetime_column / ParseDatetimeColumn
src/crosscontract/transformations/transformation/dataframe_transformations.py
    + drop_rows_by_value / DropRowsByValue
src/crosscontract/transformations/transformation/__init__.py       # exports
src/crosscontract/transformations/__init__.py                      # re-exports
src/crosscontract/contracts/contracts/cross_contract.py            # ContractType, CONTRACT_TYPE_TO_TABLE_TYPE
src/crosscontract/__init__.py                                      # public surface
.ai-context/CONTEXT.md                                             # new terms, resolve "General"
.ai-context/TODO.md                                                # deferred items
```

No new transformation modules: `cast_column` and `parse_datetime_column` are
column-scoped and join `column_transformations.py`; `drop_rows_by_value` changes row
cardinality and joins `dataframe_transformations.py`.

### 4.4 Extensibility contract for transformations

The stated priority is that adding a transformation later is cheap. It reduces to
**one class plus one union entry**, subject to rules that keep authored YAML sane:

1. `type: Literal["snake_case"]` discriminator, matching the pure function's name.
2. `extra="forbid"` (inherited from `BaseTransformation`).
3. Pure `df -> df`; the input frame is not mutated.
4. Every field carries `description=`.
5. Optionally implement `output_columns` (§3.4 option (b)).

`CONTEXT.md` already forbids a transformation *registry*; the discriminated union is
the sanctioned dispatch. `TransformationUnion` is defined centrally and referenced by
`ExtractionInstructions` through its own alias, so narrowing the admissible set per
Build spec later stays a one-line change.

### 4.5 No `SubmissionSchema` — resolved

`Submission` gets **no schema class of its own**. It is mapped onto the existing
`General` table type through `CONTRACT_TYPE_TO_TABLE_TYPE` in `cross_contract.py`, so
`SubmissionContract.tableschema` validates as a plain `TableSchema`.

This is what the contract-type/table-type split is for. A contract type says what the
contract is *for*; a table type selects the schema that backs it. The submission bundle
genuinely is a standard flat table with a primary key and foreign keys, so it needs a
distinct contract type and no distinct schema. Minting an empty `SubmissionSchema`
purely to satisfy a discriminator would have made "one contract type, one schema class"
a standing rule, and every later contract-type distinction would have paid the same
tax.

The `RoutingFieldDescriptor` alternative was also **not** taken. It would have let the
schema self-validate and removed `extraction.routing_column` from the authored YAML,
but it widens the change into `field_descriptors/` for a concept that belongs to
extraction rather than to the schema. The routing invariants of §3.1 therefore land on
`SubmissionContract` (WP3), the only layer that can see both the schema and
`routing_column`.

### 4.6 Work packages

| WP | Content | Depends on |
|---|---|---|
| **WP0** | `ContractType` gains `Submission`; `CONTRACT_TYPE_TO_TABLE_TYPE` maps it to `General` | — |
| **WP1** | Three transformations + `TransformationUnion` | — |
| **WP2** | `Target`, `ExtractionInstructions` + validators | WP1 |
| **WP3** | `SubmissionContract`, column tracking | WP0, WP2 |
| **WP4** | `CONTEXT.md` terms, ADR 0004, `TODO.md` entries | WP3 |

Critical path is **WP1 → WP2 → WP3**; WP0 runs in parallel. WP1 carries the most
architectural weight: it establishes the union pattern that `DataInstructions` in the
release spec is already documented as waiting for.

### 4.7 Explicitly out of scope

- **Execution.** Applying a submission contract to a DataFrame. It joins `submission/`
  alongside the spec models — a pipeline, not a schema conversion.
- **Bundle file reading.** Excel-to-CSV normalisation stays upstream; the models
  assume a long CSV matching `tableschema`.
- **`delete_filter`.** The legacy `Extractor.delete_filter` deletes server data. It is
  deliberately excluded from a user-authorable artifact.
- **Combining variables into one contract.** Deferred; §3.2 raises on it today.
- **Platform-side acceptance** of `contract_type: Submission`, and migrating the three
  existing extractor modules. Cross-repo; record in `TODO.md`.

## 5. Data & Schema Changes

### 5.1 New transformation models

| `type` | Fields | Module |
|---|---|---|
| `cast_column` | `column_name: str`, `to_type` | `column_transformations.py` |
| `parse_datetime_column` | `column_name: str`, `format: str | None = None`, `dayfirst: bool = False` | `column_transformations.py` |
| `drop_rows_by_value` | `column_name: str`, `values: list[Any]` | `dataframe_transformations.py` |

`to_type` **reuses the Frictionless field-type literals** already used by
`contracts/schema/fields/` (`string`, `integer`, `number`, `datetime`, …) rather than
a parallel pandas-dtype vocabulary. `parse_datetime_column`'s `format` defaults to
`None`, letting pandas infer: an explicit default would misparse silently whenever it
did not match, and there is no one right incoming format — this `format` describes the
*incoming* form, while the contract's `DateTimeField.format` describes the *canonical
stored* form, so they legitimately differ per submission (cross2025 uses `mixed` +
`dayfirst`).

### 5.2 New extraction models

```python
class Target(BaseModel):                    # submission/extraction/target.py
    filters: str | dict[str, str]           # normalised to dict by the parent
    contract: str                           # CONTRACT_NAME_PATTERN, max_length=100
    transformation_profile: str | None = None
    transformations: list[TransformationUnion] = []

class ExtractionInstructions(BaseModel):    # submission/extraction/extraction_instructions.py
    routing_column: str = "variable"
    transformation_profiles: dict[str, list[TransformationUnion]] = {}
    targets: list[Target]                   # min_length=1
```

Both `extra="forbid"`. Scalar-`filters` normalisation needs `routing_column`, which
lives on the parent — so it is an `ExtractionInstructions`-level
`@model_validator(mode="after")`, not a field validator on `Target`.

`filters` is typed as scalar-or-mapping from the start even though every current case
is scalar: it costs nothing now and means multi-column matching later is not a
breaking change to authored YAML. The name matches `FetchSpecMixin.filters`, which is
the same concept (a row allow-list keyed by column) in the egress direction.

### 5.3 `SubmissionContract`

```python
class SubmissionContract(CrossContract):    # submission/submission_contract.py
    contract_type: Literal["Submission"] = Field(  # type: ignore[assignment]
        default="Submission",
        description="The type of the contract.",
    )
    project_name: str
    extraction: ExtractionInstructions
```

**Why inherit `CrossContract` rather than compose as a sibling.** `CrossContract` is
itself `BaseContract, CrossMetaData`, so a sibling was a live option. Inheriting wins
on two counts: it keeps `validate_references`'s `enforce_star_schema=True` default,
which is the correct behaviour here — the submission foreign keys all point at
dimensions — and it keeps the contract usable wherever the client already accepts a
`CrossContract`.

Two details on the `contract_type` override: it narrows the inherited `ContractType`,
so it carries the same `# type: ignore[assignment]` the schema subclasses use; and it
must **not** be `exclude=True`. Unlike `table_type`, which is injected and would break
re-validation if it reappeared, `contract_type` is authored and serialized.

**No `to_server()` / `from_server()` overrides.** Whether the platform stores the
extraction block whole, or only the contract half, is the platform's concern; nothing
in this package needs to assume either.

**Where the derived routing `enum` is assembled is left open.** Something must inject
it before data is validated against the submission contract, but that site — a property
on the model, a helper on `ExtractionInstructions`, or the future validator — is not
needed to land WP3, and no `to_contract()` method is written. The acceptance test
(§7.4) is phrased against the derived *values* so it holds whichever site is chosen.

### 5.4 The `project_name` field

`project_name` names the CROSS **Project** the extracted data is written under —
`add_data(..., project_name=...)` in `ContractService`. The field takes the client's
own keyword rather than shortening to `project`, so the authored YAML and the call site
use one word. It is inert for extraction
itself and exists so the eventual submission endpoint has the ownership binding
without a second lookup. It replaces the `Extractor.name` key of the legacy registry
(`cross2022`, `cross2025`, `nuclear2025`), which doubled as the project name.

### 5.5 Behavioural gap in `MapColumnValues`

Two separate problems, one resolved and one open.

**Resolved.** `default_value` no longer collides with "keep original": the sentinel is
the field's default, `apply()` is a pure delegation, and a serializer omits the key when
the sentinel is in place so the spec still round-trips.

**Open.** `MapColumnValues` has no conflict guard: mapping a value onto one already
present in the column merges the two silently, and on a foreign-key column that produces
duplicate primary keys downstream, breaking the sum invariant of ADR 0001. Either add an
`on_conflict` option or record it in `TODO.md` — but decide, rather than leaving it
silent. This is a correctness question about the transformation itself; there are no
legacy specifications whose migration it would affect.

### 5.6 Terminology to add to `CONTEXT.md`

**Submission contract**, **Extraction instructions**, **Transformation profile**,
**Target**, **Routing column**. Also resolve the flagged ambiguity on **General**: it
stays legacy, and new submission contracts use `Submission` rather than deepening the
dependency on a type whose deprecation is undecided.

## 6. Related ADRs

- **[ADR 0003 — Release is a contract → Frictionless adapter](../adrs/0003-release-is-a-contract-to-frictionless-adapter.md).**
  The direct structural precedent. Release holds *specification models* that name what
  to fetch without resolving it, and pushes correctness into places it cannot be
  violated. This PRD is the ingress mirror: `Target.contract` names a contract exactly
  as `FetchSpecMixin.contract` does, and the derived `enum` and derived column-drop
  rules are the same "correct by construction" move. ADR 0003 also notes
  `DataInstructions` is the extension point awaiting transformations — WP1 supplies
  the union it has been waiting for.
- **[ADR 0002 — Contract metadata follows Frictionless, with deviations](../adrs/0002-metadata-follows-frictionless-with-deviations.md).**
  `SubmissionContract` adds `project_name` and `extraction`, which are **not**
  Frictionless keys. This is a deliberate deviation of the kind ADR 0002 governs, and
  one the ADR 0004 stub should record.
- **[ADR 0001 — Dimensions are strict trees](../adrs/0001-dimensions-are-strict-trees.md).**
  Not directly governing, but the reason §3.5's `map_column_values` conflict gap
  matters: silently merging two dimension members on a foreign-key column breaks the
  sum invariant downstream.
- **ADR 0004 (to be written, WP4)** — *Submission contracts carry extraction
  instructions*: records the named-not-resolved boundary, append-only profiles with no
  composition, and the `Submission` contract type.

## 7. Testing Strategy

Tests mirror the source tree under `src/tests/`, with YAML fixtures alongside them
(the existing `src/tests/contracts/simple_contract.yaml` sets the pattern).

### 7.1 Unit — transformations (`src/tests/transformations/transformation/`)

- Per new transformation: YAML fragment → model → `apply` on a small fixture frame;
  assert the output frame and that the input is **unmutated**.
- Union dispatch: a list of raw dicts differing only in `type` validates to the right
  classes; an unknown `type` raises.
- Error paths from §3.5: integer cast over NaN, integer cast over fractional floats,
  unparseable datetimes — each asserting the *message* names the offending column.

### 7.2 Unit — extraction models (`src/tests/submission/extraction/`)

- Scalar `filters` normalises to `{routing_column: value}`; mapping form passes through.
- Every raise in §3.2 and §3.3 has a test: unknown filter column, duplicate target
  contract, empty targets, dangling profile reference. Repeated filters across targets
  with distinct contracts are accepted.

### 7.3 Unit — `SubmissionContract` (`src/tests/submission/`)

- Routing-column invariants from §3.1, including a regression test using the literal
  string `"variable."` — the real typo in the current annotated example.
- Column tracking (§3.4, option (b)): a rename-then-cast chain validates; a
  cast naming the pre-rename column raises; an opaque transformation stops tracking
  without raising.
- Round-trip `from_file` → `model_dump` → `model_validate` is stable.

### 7.4 Integration — the reference example

The acceptance test, using
[`cross2025_submission.yaml`](./cross2025_submission.yaml) as the fixture (copied into
`src/tests/submission/` so tests don't depend on `.ai-context/`):

1. It loads as a `SubmissionContract`.
2. 24 targets, all contracts unique, all profile references resolve.
3. The **set** of routing values derived from the targets equals the 24-entry enum of
   the legacy `submission_cross2025.yaml` exactly. The derivation dedupes, since
   repeated filters across targets are legal — assert the set, never the count against
   the number of targets.
4. Full round-trip `from_file` → `model_dump` → `model_validate` is stable.

Fix the `routing_column: variable.` typo in the fixture copy — or keep it, and assert
the loader rejects it, then use a corrected copy for the rest.

### 7.5 Not tested here

Execution behaviour marked *(runtime)* in §3 belongs to the follow-on execution
package. The transformation-level runtime errors in §7.1 **are** in scope, because the
transformations themselves ship in WP1.
