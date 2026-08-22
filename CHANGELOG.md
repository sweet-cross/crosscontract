# CHANGELOG

## v0.16.0 (2026-08-22)

### Features


- **identify extraction targets by name** ([`c71a035`](https://github.com/sweet-cross/crosscontract/commit/c71a035614b250fe0ac3f8fe5fce6af747fcf6b8))

  # feat: identify extraction targets by name

  ## Summary

  A `Target` had no identifier of its own. In practice it was identified by its `contract`, which the contract-uniqueness validator happened to enforce — an accident of that check rather than a design. This branch gives targets a `name`, and uses it to derive the routing filter when none is authored.

  Two problems go away. `contract` is a platform-side resource name that ends up in a URL, so using it as a spec-local identifier was semantically wrong. More importantly, binding identity to it cemented contract-uniqueness as an *identity* constraint rather than the primary-key-collision guard it actually is — which would have made it expensive to relax if combining several targets into one dataset (netting supply against demand, say) ever becomes a feature. That combination is **not** implemented here and is not planned as part of this work; the point is only that identity no longer rides on `contract`.

  Base branch is `dev`.

  ## Changes

  **`Target.name`** — required, `min_length=1`, whitespace-stripped, and deliberately carrying **no pattern and no maximum length**. It is spec-local identification: what an author calls their own target is their decision, and `"StUpid nAming 0f a V@riable"` is legal. `contract` keeps `CONTRACT_NAME_PATTERN` and `max_length=100` for the opposite reason — it names a platform resource that appears in URLs. The constraint is expressed as `Annotated[str, StringConstraints(...)]`, matching `ValidFieldName` in `contracts/valid_items.py`, rather than a model-wide `str_strip_whitespace`, which would also have stripped `filters` values and silently changed row matching.

  **Filters derive from the name; the scalar shorthand is gone.** The authoring surface is now two forms instead of three: omit `filters` and it becomes `{routing_column: name}`, or write the mapping out and `name` plays no part in routing. The old scalar `filters: some_value` is rejected. `filters` stays `dict[str, str]` and required on the model — the before-validator populates it — so the annotation continues to describe the stored value rather than the input that produced it.

  The derivation replaces the scalar branch in the existing `field_validator("targets", mode="before")`, keeping its shape: it reads `routing_column` off `info.data` (which is why it is a field validator rather than a model validator — the value is already validated there), copies rather than mutating the caller's dicts, and hands unrecognised shapes through so pydantic reports them. Two details are deliberate and easy to undo by accident: it triggers on the `filters` key being
  **absent**, not on its value being `None`, so a half-written `filters:` is rejected rather than silently derived; and it `.strip()`s the name, because `strip_whitespace` on `Target.name` runs
  *after* this validator and the stored name would otherwise differ from the derived routing value.

  **Two independent uniqueness rules.** `_check_name_unique` joins `_check_contract_unique` as a separate validator with its own message, rather than being folded in. They enforce different things and have different futures: name-uniqueness is structural and permanent; contract-uniqueness guards against merged rows colliding on the contract's primary key and is relaxable. Folding them together would have re-created the coupling this branch removes.

  **Documentation.** ADR 0004's Consequences split the single "one target per contract" bullet into the two rules, recording explicitly that contract-uniqueness is a guard and not an identity constraint, and that keeping it distinct is what leaves it relaxable. Its "filters are mapping-only" bullet now describes the two current authoring forms and notes the scalar form's removal. `CONTEXT.md`'s **Target** entry leads with the name and covers the routing-value default — the one place in that vocabulary where an identifier doubles as data.

  ## Testing

  `src/tests/submission/` — 17 tests, no new dependencies.

  - **New:** duplicate target names raise, with a message distinct from the duplicate
    contract one; and `filters` omitted yields `{routing_column: name}`.
  - **Rewritten:** `test_filter_raises_validation_error_no_routing_column` previously fed a scalar `filters` and no `name`, so its payload was invalid three ways and it passed on whichever error happened to land. It now supplies a well-formed target relying on the derivation, making the missing `routing_column` the only defect — which is what the test claims to check.
  - **Updated:** every fixture gains a `name`; `example_submission.yaml` drops the two scalar-filter targets in favour of derived ones, keeping the explicit-mapping target so
    the round-trip tests still cover both forms.

  ## Notes for reviewer

  **The `.strip()` in the validator duplicates knowledge that also lives in `StringConstraints(strip_whitespace=True)`.** They cannot share, because the derivation runs on raw input before field constraints apply. Without the strip, `name: " electricity "` stores `name == "electricity"` but derives `filters == {"variable": " electricity "}` — a routing value matching no rows, which only warns and skips at runtime. The docstring says why the duplication exists so nobody removes it as redundant. The alternative is dropping `strip_whitespace` and accepting `" "` as a legal name.

  **"A scalar `filters` is rejected" has no test.** It reduces to pydantic refusing a `str` for `dict[str, str]`, and the project's convention is not to test pydantic's own behaviour. Flagging it because it *is* a behaviour change from the previous release — though no authored file uses the old form, so there is nothing to migrate.

  **No test pins "`name` has no pattern" either**, for the same reason: it would assert the absence of a constraint. The reasoning now lives in ADR 0004 and `CONTEXT.md` instead, which is what stops someone adding `CONTRACT_NAME_PATTERN` to `name` out of symmetry with `contract`.

  **`Target.name`'s field description** was written during WP1, when the derivation did not exist yet; it has been correct since WP2 landed but is worth reading against the final behaviour.



## v0.15.0 (2026-08-21)

### Features


- **add extraction instructions and the submission contract** ([`3680600`](https://github.com/sweet-cross/crosscontract/commit/3680600c4bcee211383c102caff23e5dc975c896))

  # feat: add extraction instructions and the submission contract

  ## Summary

  Completes the submission-contract feature: the declarative models that describe how a delivered bundle is split (`Target`, `ExtractionInstructions`), the `SubmissionContract` that binds them to a schema, and the language and decision record that keep the design findable once the planning documents are gone.

  A submission bundle is one wide file carrying rows for many datasets at once. Until now the knowledge of how to split it lived in hand-written Python dictionaries that could not be authored, reviewed or versioned. This branch makes that knowledge a YAML artifact that loads, validates standalone, and round-trips.

  Base branch is `dev`. The transformations and the `Submission` contract type landed earlier; this branch is the ingress spec on top of them.

  ## Changes

  **`submission/` becomes a real package.** `submission_contract.py` moves out of `contracts/contracts/` (history preserved via `git mv`), and `submission/extraction/` is added alongside it. The package now owns the contract, the spec models, and — when it lands — the code that executes them. `SubmissionContract` is exported from `crosscontract/__init__.py`.

  **`Target`** carries `filters` (mapping-only; a bare value is accepted as authoring shorthand and expanded on load), a `contract` **name** validated against `CONTRACT_NAME_PATTERN`, an optional `transformation_profile`, and its own `transformations`. It names its target contract and never resolves it.

  **`ExtractionInstructions`** holds the required `routing_column`, the reusable `transformation_profiles`, and a non-empty `targets` list. Three validators:

  - a `field_validator("targets", mode="before")` that expands scalar `filters` into `{routing_column: value}`. It is a *field* validator rather than a model validator so `info.data` already carries the validated `routing_column`; it copies rather than mutating the caller's dicts, and hands unrecognised shapes straight through so pydantic
    reports them.
  - contract-uniqueness across targets. Repeated *filters* are deliberately allowed — the same rows may feed two contracts through different transformations — because a repeated contract is the only case that actually breaks: after the routing column is dropped the
    merged rows collide on that contract's primary key.
  - every `transformation_profile` reference resolves to a defined profile.

  **`SubmissionContract(CrossContract)`** adds `project_name`, `extraction`, and `contract_type` pinned to `Literal["Submission"]`, plus two model validators: the routing

  column must exist in the tableschema, be `required`, be `type: string`, and carry no authored `enum` (it is derived); and every key of every target's `filters` must name a field in the tableschema.

  **Documentation.** `CONTEXT.md` gains a **Submission and extraction** section defining
  *Submission contract*, *Extraction instructions*, *Transformation profile*, *Target* and
  *Routing column*, three new **Relationships** bullets for the ingress path, and an updated
  **Table type** entry — the mapping is no longer the identity. The
  **General** ambiguity is resolved in place: "General is legacy" is true of the *contract type* only, since `Submission` maps onto the General *table type*, which outlives it. `ADR 0004` records the three decisions that are expensive to reverse. `CLAUDE.md` gains the `submission/` architecture entry.

  **The PRD and its task files are deleted.** They were planning artifacts; their durable content is now in ADR 0004 and `CONTEXT.md`.

  ## Testing

  `src/tests/submission/` — 16 tests, no new dependencies.

  - **Extraction models** (8): valid construction, scalar-`filters` expansion, an invalid contract name, omitted and empty `targets`, duplicate contracts, an undefined profile reference, and a missing `routing_column` — the last one pinning that the before-validator hands input through so pydantic reports the real error rather than
    failing on raw data first.
  - **`SubmissionContract`** (6): each routing-column invariant separately, plus a filter
    key naming a column absent from the tableschema.
  - **Round-trip** (2): `example_submission.yaml` → model → YAML file → model, and the same through JSON, asserting model equality. Both hops go through an actual file, so the dump
    is proven serializable rather than merely re-validatable.

  `example_submission.yaml` is purpose-built and deliberately small, but covers what can silently break: both `filters` forms, a profile shared by two targets, a target appending its own steps after a profile, and a `map_column_values` with `default_value` omitted — the `KEEP_ORIGINAL` sentinel, which has no serialized form and is nested inside a contract here for the first time.

  ## Notes for reviewer

  **Nothing derives the routing enum yet.** The format's central claim is that the routing field's permitted values come from the targets rather than being authored — the contract
  *rejects* an authored `enum` for exactly that reason. But no code assembles the derived set. Where it belongs (a property on the contract, a helper on the instructions, or the validator that checks data against the contract) was deliberately left open, and it is recorded for follow-up. Worth confirming you're happy shipping the rejection without the derivation.

  **The cross2025 acceptance test was dropped on purpose.** `.ai-context/prds/cross2025_submission.yaml` was written to drive design discussion, not as a fixture; this is all new work with no legacy specification to match, so pinning the models to one hand-written file would have measured that file rather than the format. If the PRD directory goes, decide whether that YAML goes with it.

  **Deferred, recorded for planning rather than fixed here:** column tracking through a transformation pipeline (the `output_columns` hook was never added, so adopting it now means retrofitting all six transformations), the `MapColumnValues` `on_conflict` guard, and the execution package itself.

  **Minor:** the module is `extraction_instruction.py` (singular) while the class is `ExtractionInstructions` (plural).

  ---------

  Co-authored-by: Copilot Autofix powered by AI <175728472+Copilot@users.noreply.github.com>



## v0.14.0 (2026-08-21)

### Features


- **Submission contract I - Initial contract and transformations** ([`fd55e43`](https://github.com/sweet-cross/crosscontract/commit/fd55e4328ce8c336d0bdebe30d75cffce2dfd9dd))

  # feat: add the Submission contract type and the first transformation union

  ## Summary

  Lays the two independent foundations for submission contracts (PRD `2026-08-14-submission-contracts.md`, WP0 and WP1): a `Submission` contract type, and the vocabulary of transformations plus the discriminated union that authored extraction specs will dispatch on. Neither half depends on the other — `Submission` is inert until something emits it, and the three new transformations are additive. The one behavioural change is to `MapColumnValues.default_value` (below); no authored specs exist yet, so nothing in the wild changes meaning.

  The union is the higher-leverage half: no discriminated union over transformations had ever been defined, and `DataInstructions` in the release spec is documented as an extension point waiting for one. This PR supplies it.

  Base branch is `dev`.

  ## Changes

  **`Submission` contract type (WP0).** `ContractType` gains `"Submission"`, and `CONTRACT_TYPE_TO_TABLE_TYPE` maps it onto the existing `General` table type. No new schema class: the submission bundle is a standard flat table with a primary key and foreign keys, so it needs its own contract type but not its own schema. This is the first entry that makes the mapping non-identity, and the comment above the table was rewritten accordingly — including the note that the relation is many-to-one, so a `table_type` no longer determines a `contract_type`.

  **Three new transformations (WP1).** Each is a pure function plus a thin `BaseTransformation` subclass whose `apply()` is a single delegating call:

  - `cast_column` / `CastColumn` — `to_type` is a `CastableType` literal spelled with the Frictionless field-type vocabulary (`integer`, `number`, `string`, `boolean`), not pandas dtype strings, so a bad value fails at load rather than at execution. Integer and number casts target the pandas nullable `Int64` / `Float64`, so fractional floats raise rather than truncating and nulls survive the cast. `datetime` is deliberately
  *not* a member: including it would let a spec validate at load and then fail at `apply()` time, which is precisely what the literal exists to prevent. The pure function keeps a dedicated branch raising a pointer to `parse_datetime_column`, since it is the obvious thing a direct caller tries. The literal is declared locally rather than imported from `contracts/schema/fields/`, because `contracts/` imports from this
    package and the reverse import would be circular.
  - `parse_datetime_column` / `ParseDatetimeColumn` — `format` defaults to `None` (pandas infers); `format: mixed` and `dayfirst` pass through. Parse errors propagate
    from pandas unchanged.
  - `drop_rows_by_value` / `DropRowsByValue` — boolean-mask filter, copied before it is returned so callers do not inherit a slice and the `SettingWithCopyWarning` that comes with it. The original index is preserved deliberately and pinned by tests.

  **`TransformationUnion`.** New `transformation/union.py` holding `Annotated[... , Field(discriminator="type")]` over all six transformations, following the house idiom and the `field_descriptors/` split of classes from union. It imports the leaf modules rather than the package `__init__`, which re-exports it — going through `__init__` would be circular. Exported from both `transformation/` and `transformations/`, along with the four new symbols that were previously reachable only from the leaf module.

  **`MapColumnValues` serialization.** `default_value` now defaults to the `KEEP_ORIGINAL` sentinel directly, so `apply()` is a pure delegation instead of translating `None` into the sentinel — which is what previously made "map unmapped entries to `None`" unreachable from a spec. Because the sentinel has no serialized form and would crash the JSON encoder, the field carries `exclude=True` and a `mode="wrap"` serializer re-adds the key only when it holds a real value. Omission is therefore the default path, which is exactly what "keep the original values" means on reload. Three cases now round-trip: omitted → keep original, explicit `null` → `None` is the fallback, explicit value → that value.

  **Test restructure.** Function tests and spec tests for a transformation now live in the same file and class, so `test_transformation_specs.py` is deleted and its union-and-discrimination tests move to a new `test_union.py`. Two principles are applied throughout: don't re-test pandas, and test spec pass-through by patching the underlying function. `MapColumnValues` is the deliberate exception — its default handling is involved enough to be worth exercising end to end.

  That file's two chained-application tests (`test_ordered_application` and `test_rename_after_drop_raises_on_missing_column`) are dropped rather than moved. There is no function yet that applies a list of specs to a DataFrame, so a hand-rolled `for` loop over `apply()` tests the test rather than the package. They return as integration tests once that function exists.

  **Docs.** PRD and task files updated as decisions were settled: §4.5 (no `SubmissionSchema`), §5.3 (`SubmissionContract` shape and the deferred routing-enum question), §5.4 (`project` renamed `project_name` to match the existing `ContractService` keyword), §3.5 and §5.1 (integer casts keep nulls; datetime parse errors come from pandas; the `format` default). WP0's task file is deleted, per the convention of removing a task description once it lands. `CLAUDE.md` gains a section on implementing only what was asked, as simply as possible.

  **Housekeeping.** Removed two stale PR descriptions from `.github/PRs/`, and wrapped four over-long `description=` strings in `_standards/frictionless/fields.py`.

  ## Testing

  Suite reported green by the author.

  - `test_union.py` — discriminator resolution parametrized over all six members, `extra="forbid"` through the union, and rejection of an unknown `type`.
  - `test_column_transformations.py` — cast success matrix and error cases (kept deliberately broad, since type casting is sensitive and the behaviour is worth documenting), datetime wiring and kwarg pass-through, and a three-case round-trip test for `MapColumnValues` across both the python and JSON dump paths. The two halves of the `datetime` decision are pinned separately: the spec rejects it at load, while a direct call to `cast_column` still gets the pointer to `parse_datetime_column`.
  - `test_dataframe_transformations.py` — per-transformation success and error cases plus
    a patched pass-through test for each spec.
  - `test_contract_types.py` — `contract_type: Submission` resolving to `TableSchema`, and the pre-instantiated-schema pass-through parametrized over `General` and `Submission`, which is the branch that breaks if the lookup ever regresses to comparing
    `contract_type` against `table_type` directly.

  ## Notes for reviewer

  **`submission_contract.py` lands as a draft and is finished in WP3.** It composes `BaseContract, CrossMetaData` as a sibling and has `extraction` commented out behind a TODO. The design settled later on inheriting `CrossContract` — for `validate_references`'s `enforce_star_schema=True` default, which is correct here since the submission foreign keys all point at dimensions, and to stay usable wherever a `CrossContract` is accepted. PRD §5.3 and the WP3 task file record that shape.

  Until then the class is deliberately inert: it is exported from nowhere, has no tests, and — because it is not a `CrossContract` — has no `to_server()`, so `ContractService.create()` cannot accept it. Nothing can reach it by accident. It carries drafted docstrings so the file reads as intended rather than as an orphan; the class docstring states the `Submission` → `General` mapping as a design fact rather than as something this class performs, since `_inject_table_type` only runs on `CrossContract`. That sentence can take its stronger form once WP3 changes the base.

  **The `output_columns` hook was not implemented.** WP1's task file noted that adding it while the transformations were being written is cheap and retrofitting is not. It went in without. If WP3 adopts option (a) or (b) for column tracking, the cost is now retrofitting all six rather than writing three — recorded in the WP3 task file.

  **Still open, tracked in the WP4 task file:** `MapColumnValues` has no `on_conflict` guard, so mapping a value onto one already present in the column merges the two silently. On a foreign-key column that produces duplicate primary keys downstream, breaking the sum invariant of ADR 0001.

  **Worth extra scrutiny:** the `exclude=True` plus wrap-serializer pattern on `MapColumnValues.default_value` is the only place in the package where a field is hidden from the standard serializer and reinstated by hand. An earlier attempt using only a wrap serializer crashed inside `handler(self)`, because the handler serializes the sentinel before the callback can drop it; `exclude=True` is what keeps the handler away from it. `model_json_schema()` emits a `PydanticJsonSchemaWarning` about the non-serializable default and omits it — the resulting schema is correct, but the warning is visible.


### Refactoring


- **decouple `contract_type` from `table_type` via an explicit mapping** ([`abb7a91`](https://github.com/sweet-cross/crosscontract/commit/abb7a91961d91dc966874a51fc92fef77419ac34))

  # refactor: decouple `contract_type` from `table_type` via an explicit mapping

  ## Summary

  `CrossContract._inject_table_type_to_schema` established the schema discriminator by copying the contract type straight into the tableschema (`schema_copy["table_type"] = contr_type`). That made the two vocabularies string-identical by construction: a contract type could never map onto an existing schema, and the identity was implicit in an assignment rather than stated anywhere. This branch replaces that assignment with an explicit `CONTRACT_TYPE_TO_TABLE_TYPE` table, so adding a contract type that reuses `DimensionSchema` (or any other) becomes a one-line dict entry.

  The mapping is the identity today, so **behaviour is unchanged** apart from the wording of one error message (below). This is a refactor that opens a door, not a fix.

  ## Changes

  - Added a `TableType` literal alias alongside `ContractType`. The two carry identical members today; declaring them separately is the statement that they are different
    vocabularies that happen to coincide.
  - Added `CONTRACT_TYPE_TO_TABLE_TYPE: dict[ContractType, TableType]` as the single place relating the two. Both the discriminator injection and the mismatch check now
    read from it.
  - An unmapped `contract_type` is no longer rejected inside the before-validator. The helper returns the data untouched so the `Literal`-typed `contract_type` field raises pydantic's own `literal_error` at `loc=("contract_type",)`, preserving field
    anchoring for callers that inspect `.errors()`.
  - **Reworded the mismatch error** to name the expected table type. It previously read `Mismatch between contract_type 'X' and tableschema.table_type 'Y'`, which silently assumed the two vocabularies are equal; it now reads `... contract_type 'X', which maps to table_type 'Z', and the provided tableschema.table_type 'Y'`. This is the
    only observable change on the branch.
  - Documented the design in the helper docstring and added the missing `Raises:`
    section.
  - Recorded the branches that still key schema behaviour off a contract type in
    `.ai-context/TODO.md` — `from_server` / `to_server`, plus
    `CrossRegistry.add_variable`.
  - Added a **Table type** term to `.ai-context/CONTEXT.md` and updated the **Contract type** entry, since this change splits one concept into two. `CLAUDE.md`'s
    "maps 1:1" note was updated to point at the mapping table.

  ## Testing

  New tests, none run in this session (per the repo's no-automatic-validation rule):

  - `TestContractTypeToTableTypeMapping` — three guards: every `ContractType` member has a mapping; every mapped value is a `table_type` some schema class actually declares; and the `TableType` alias itself still matches the schema union. The latter two read the tags off `AnyTableSchema`'s members rather than off `TableType`, so a mapping pointing at a table type no schema can resolve fails here instead of at runtime.
  - `test_instantiated_subclass_schema_mismatch_raises_value_error` — covers the subclass direction of the mismatch check, which had no coverage. Note this passes on `dev`
    too; it is a regression guard, not new behaviour.
  - Updated the two mismatch-message assertions for the reworded error.

  **Please run `uv run pytest` and `uv run mypy src/crosscontract/` before merging.**

  ## Notes for reviewer

  - **Two identical literal definitions.** `ContractType` and `TableType` list the same four members. That is deliberate, but it reads as duplication and invites someone to alias one to the other later, which would re-introduce the coupling. The mapping
    tests are the guard against that.
  - **The unknown-contract-type path produces two validation errors**, not one: the `literal_error` on `contract_type`, plus a discriminator error on `tableschema` because no `table_type` was injected. This is unchanged from `dev` (which produced a `union_tag_invalid` there instead), and is now stated in the helper docstring and in
    the test docstring so nobody tightens the assertion to an error count.
  - **`refactor:` rather than `fix:`.** The mapping is the identity, so no input changes its outcome; the only observable delta is the error-message wording. Under PSR a `refactor:` prefix does not bump the version, which is the right outcome for a change with no user-visible behaviour. The branch name still says `fix/` — harmless,
    since the squash-commit message comes from this title.
  - **`uv.lock` carries an incidental one-line change** syncing `crosscontract` to `0.13.1` to match `pyproject.toml`; it was picked up by a `uv run` during the
    session and is unrelated to the logic here.



## v0.13.1 (2026-08-20)

### Bug fixes


- **deprecate the construction-time `filters` argument on `CrossDataVariable`** ([`56a24eb`](https://github.com/sweet-cross/crosscontract/commit/56a24eb1a65950554f94d9b2ec7b9434925f6bbe))

- **deprecate the construction-time `filters` argument on** ([`56a24eb`](https://github.com/sweet-cross/crosscontract/commit/56a24eb1a65950554f94d9b2ec7b9434925f6bbe))


### Code style


- **apply sweet-cross branding to docs** ([`5357f0d`](https://github.com/sweet-cross/crosscontract/commit/5357f0d01ef3380c4929c9a24fca587c9786f3e5))

  Match the docs theme to sweet-cross.ch: brand palette (red/orange/yellow/ green gradient, white/black header per scheme), Space Grotesk/IBM Plex Sans/JetBrains Mono fonts, logo/favicon, gradient stripe under the header, navigation.indexes so section titles link to their overview page, and a wider content column (80rem) to match the data-model docs.


### Chores


- **planning submission contract** ([`b462914`](https://github.com/sweet-cross/crosscontract/commit/b462914fe1fc4011cdf51840105a01b561f5d160))





## v0.13.0 (2026-08-07)

### Features


- **scope data writes and deletes to a project** ([`767e3a1`](https://github.com/sweet-cross/crosscontract/commit/767e3a1e8ffb2ebc3dae8cd1b4bd2a1d2dde789d))

  # feat: scope data writes and deletes to a project

  ## Summary The CROSS platform now owns submitted data by project and requires a caller to act on behalf of one project when writing or deleting data. This adds an optional `project_name` parameter to the client's data-write and data-delete paths (`ContractService._add_data`/`_delete_data` and `ContractResource.add_data`/`delete_data`), so callers who belong to more than one project can say which one they're acting for. Callers with exactly one project membership are unaffected — the platform infers it as before.

  Alongside `project_name`, `delete_data` gains a `confirm_delete_all` flag that authorizes clearing every row the resolved project owns under a contract, without dropping the storage table. This closes a gap the project change otherwise opened: the existing `filters`-required guard on `delete_data` pointed users at `drop_data()` for a full wipe, but `drop_data()` now destroys every project's data and requires the contract to be `Retired` — not the scoped, `Active`-only operation a project owner actually wants.

  ## Changes
  - `ContractService._add_data` accepts `project_name: str | None = None`,
    sent as a query parameter on the POST (previously the method sent no
    `params` at all). Omitted from the query string when `None`; sent when
    `""` — the guard is `is not None`, not truthiness, since an omitted parameter means "infer the project" and a falsy-but-not-None value must
    not be silently reinterpreted that way.
  - `ContractService._delete_data` accepts `project_name` (same omission rule)
    and `confirm_delete_all: bool = False`. The empty-`filters` guard now
    reads `if not filters and not confirm_delete_all`, and its message no longer points at `drop_data()`. The client parameter `confirm_delete_all`
    is mapped to the platform's `delete_all` query key in exactly this one
    place, so the client and wire vocabularies can differ without a rename
    leaking through the resource → service boundary. The flag is sent only
    when `filters` is empty: combining the two is allowed and resolves as "filters win", enforced client-side by dropping the flag rather than by assuming how the platform orders the two — the fallout of guessing that
    wrong is every row the project owns.
  - `ContractResource.add_data` and `delete_data` gain the same parameters, both keyword-only, and forward to the service unchanged. `delete_data`'s existing `Active`-status check still runs first, ahead of the empty-filter
    check and ahead of `confirm_delete_all` — an unfiltered delete on a
    non-`Active` contract still can't reach the platform.
  - `drop_data()` docstring rewritten to state plainly that it is a
    decommissioning operation restricted to administrators, crossing every
    project, as distinct from the newly-scoped `delete_data`.
  - No client-side project resolution, validation, or default project was
    added — `project_name` is an opaque pass-through string; the platform
    remains the sole authority on which project a caller may act under.
  - `docs/client/index.md`: new "Projects" section, and the removal-operations
    table grows a Scope column and a third row for the unfiltered
    `confirm_delete_all` form.
  - `notebooks/client_tutorial.ipynb`: one markdown cell added ahead of the
    `add_data` example, noting when `project_name` is needed. Code cells unchanged — the parameter is optional, so the existing calls stay valid.
  - `.ai-context/CONTEXT.md`: added a **Project** entry to the ubiquitous language, noting that a contract itself belongs to no project (only its
    rows do) and that reads are not scoped the way writes are.
  - `.claude/CLAUDE.md`: tightened the docstring convention to explicitly ban
    rST double-backtick literals and field markers (matching the sibling `cross_back` repo's rule) and to require `Args`/`Returns`/`Raises` on every
    applicable docstring. Existing double-backtick usage elsewhere in the package is pre-existing and out of scope; tracked in `.ai-context/TODO.md`
    for a dedicated sweep.

  ## Testing
  - New `respx`-backed tests in `test_contracts_service.py` covering, for both `_add_data` and `_delete_data`: `project_name` present when set, absent when `None`, and present-but-empty when `""` (guards the truthiness-vs-
  `is not None` distinction); `_add_data`'s `project_name` landing in the query string and not the multipart body; `confirm_delete_all` mapping to the wire key `delete_all` (and `confirm_delete_all` itself never reaching the wire, where it would be swept up as a bogus filter); the empty-filters guard raising with no filters and no confirmation, issuing a request with confirmation, and `delete_all` being dropped when filters are also given.
  - New delegation tests in `test_contract_resource.py` asserting non-default `project_name` / `confirm_delete_all` values actually reach the service — the three pre-existing pinned assertions only pinned the default (`None`
    / `False`) case, which would still pass if the parameter were accepted
    and silently dropped.
  - A parametrized test pinning that the `Active`-status check fires ahead of
    `confirm_delete_all`, so the widest deletion the client offers stays
    behind the same local gate as a filtered one. The pre-existing status test only covered the filtered call, which would keep passing if the
    ordering were inverted.
  - Full suite, `ruff check`, `ruff format --check`, and `mypy` all green.

  ## Notes for reviewer
  - `drop_data()` was deliberately left without its own confirmation
    parameter: it's already an admin-only route, so the extra ceremony
    wasn't judged to buy anything. Its service-level counterpart
    `_drop_data_table` now carries the same "every project, `Retired`,
    admin-only" framing as the public method, so the two layers no longer
    describe the operation differently.
  - `_delete_data`'s empty-filters rule is mirrored client-side (raising
    before any request when `filters` is empty and `confirm_delete_all` is `False`), which duplicates a rule the platform also enforces. This was a deliberate choice — the rule is stated in the platform's own 400 response,
    so both sides enforce one rule rather than two that can drift, and it
    saves a round trip on an obvious mistake. By contrast, no client-side guard was added against filter keys that shadow reserved query parameters
    (e.g. a contract column literally named `project_name`) — that would require copying a platform constant the platform doesn't expose, and the
    platform already rejects the realistic collision with a fast 404.




### Documentation


- **data pakcage release** ([`9302679`](https://github.com/sweet-cross/crosscontract/commit/9302679cbdc5d0964860d515eda1a32c9b876c72))


### Chores


- **action update** ([`8c24cb0`](https://github.com/sweet-cross/crosscontract/commit/8c24cb0614faf86a1973d64080fd2973600e7519))



## v0.12.2 (2026-06-18)

### Bug fixes


- **Filter model scenario dimension** ([`e799f66`](https://github.com/sweet-cross/crosscontract/commit/e799f6621177faadd351f54ba456bef6a31f426d))

  ## Pull request overview

  This PR introduces a safeguard in the data-package release pipeline to *prune* sensitive/non-hierarchical dimensions (model/scenario catalogs) down to only the rows referenced by released fact data, reducing the risk of shipping full catalogs unintentionally.

  **Changes:**
  - Add `PRUNE_DIMENSIONS` and `_filter_pruned_dimensions()` to restrict `dim_model` / `dim_scenario` rows to referenced keys before FK cleanup.
  - Wire `_filter_pruned_dimensions()` into `resolve_resources()` ahead of `_drop_dangling_foreign_keys()`.
  - Add unit + wiring tests covering single-key and composite-key pruning behavior and edge cases.

  ### Reviewed changes

  Copilot reviewed 2 out of 2 changed files in this pull request and generated 6 comments.

  | File | Description | | ---- | ----------- | | `src/crosscontract/release/data_package/_resolve_resource.py` | Adds pruned-dimension filtering logic and integrates it into resource resolution. | | `src/tests/release/data_package/test_resolve_resource.py` | Adds test fixtures and coverage for pruning behavior and end-to-end wiring via `resolve_resources()`. |



## v0.12.1 (2026-06-17)

### Bug fixes


- **Include refernced resource in data package** ([`2120961`](https://github.com/sweet-cross/crosscontract/commit/2120961f0a0548988ca9a1a3ff7471c7e3cd5dba))

  ## Pull request overview

  This PR updates the data package release pipeline to automatically include resources referenced via foreign keys (e.g., dimensions) so exported Frictionless data packages are self-contained by default. It also adds an opt-out flag to skip reference resolution while pruning now-dangling foreign keys to keep the descriptor Frictionless-compliant.

  **Changes:**
  - Add `resolve_references` flag (default `True`) to `create_data_package()` / `resolve_resources()` and wire it through.
  - Implement referenced-resource collection and pruning of dangling foreign keys in released schemas.
  - Expand test coverage for referenced resource inclusion and foreign-key pruning behavior.

  ### Reviewed changes

  Copilot reviewed 6 out of 7 changed files in this pull request and generated 2 comments.

  <details> <summary>Show a summary per file</summary>

  | File | Description | | ---- | ----------- | | uv.lock | Updates locked metadata (markers) and bumps local package version to 0.12.0. | | pyproject.toml | Extends mypy exclude list to include `main_dev.py`. | | src/crosscontract/release/data_package/create_data_package.py | Adds `resolve_references` parameter and forwards it to `resolve_resources`. | | src/crosscontract/release/data_package/_resolve_resource.py | Adds referenced-resource resolution + foreign key pruning logic; updates resolver API. | | src/tests/release/data_package/test_resolve_resource.py | Adds tests for collecting referenced resources and pruning dangling foreign keys; expands resolve_resources tests. | | src/tests/release/data_package/test_create_data_package.py | Updates mocks and adds coverage to ensure `resolve_references` is passed through. | | src/tests/release/data_package/conftest.py | Adds `make_dimension` fixture for dimension-like registry variables. | </details>



## v0.12.0 (2026-06-16)

### Features


- **Data package** ([`6108ca8`](https://github.com/sweet-cross/crosscontract/commit/6108ca81ad48764db97f077fef1f559b8dd82b30))

  ## Pull request overview

  Adds a new “release/data_package” pipeline that exports CROSS contracts + fetched data as a Frictionless Data Package (zip on disk), backed by a new internal `_standards.frictionless` Pydantic mirror of the upstream Frictionless schemas.

  **Changes:**
  - Introduces permissive Frictionless descriptor/schema models under `crosscontract._standards.frictionless` plus shared internal helpers under `crosscontract._helpers`.
  - Implements data package release spec models + resolver/writer functions and wires a new public entry point `create_data_package`.
  - Refactors metadata models (`Contributor`/`Source`/`License`) and contract metadata list handling to align with the new standards layer, and adds/updates tests accordingly.

  ### Reviewed changes

  Copilot reviewed 54 out of 60 changed files in this pull request and generated 11 comments.

  <details> <summary>Show a summary per file</summary>

  | File | Description | | ---- | ----------- | | uv.lock | Bumps local package version in lockfile. | | src/crosscontract/transformations/fetch/fetch_spec.py | Makes `FetchSpecMixin` require `contract` and adds `format` for release output. | | src/crosscontract/release/data_package/release_specification.py | Adds release spec models for packages/resources and validation rules. | | src/crosscontract/release/data_package/create_data_package.py | Adds orchestrator to load spec, resolve resources, and write package zip. | | src/crosscontract/release/data_package/_resolve_resource.py | Adds fetch/build/resolve logic to turn registry variables into Frictionless resources. | | src/crosscontract/release/data_package/_resolve_package.py | Adds zip writer that emits data files + datapackage descriptors. | | src/crosscontract/release/data_package/__init__.py | Re-exports new release spec + `create_data_package`. | | src/crosscontract/release/__init__.py | Updates public release exports to new adapter surface. | | src/crosscontract/contracts/contracts/base_contract.py | Renames identifier pattern constant to `CONTRACT_NAME_PATTERN`. | | src/crosscontract/contracts/contracts/cross_contract.py | Switches contributors/licenses to `OptionalNonEmptyList`; renames DataSource→Source. | | src/crosscontract/contracts/contracts/metadata_models.py | Re-bases curated metadata models on `_standards.frictionless` leaf models. | | src/crosscontract/contracts/schema/schema.py | Updates YAML/JSON reader import to new `_helpers` module. | | src/crosscontract/contracts/utils.py | Removes old YAML/JSON reader (now in `_helpers`). | | src/crosscontract/release/data_package/data_resource.py | Removes retired bespoke release descriptor class. | | src/crosscontract/release/data_package/data_package.py | Removes retired bespoke package descriptor class. | | src/crosscontract/_helpers/_pydantic.py | Adds `OptionalNonEmptyList` validator helper. | | src/crosscontract/_helpers/_io.py | Adds YAML/JSON read + dump helpers used across codebase. | | src/crosscontract/_helpers/__init__.py | Exposes internal helper utilities. | | src/crosscontract/_standards/frictionless/fields.py | Adds permissive Frictionless field models + constraints. | | src/crosscontract/_standards/frictionless/table_schema.py | Adds permissive Frictionless TableSchema model with normalization/dispatch. | | src/crosscontract/_standards/frictionless/metadata.py | Adds composable Frictionless metadata models and validators/serializers. | | src/crosscontract/_standards/frictionless/descriptors.py | Adds `DataResource`/`DataPackage` descriptor compositions. | | src/crosscontract/_standards/frictionless/__init__.py | Exposes Frictionless standard models internally. | | src/crosscontract/_standards/__init__.py | Declares `_standards` internal package. | | src/tests/transformations/fetch/test_fetch_spec.py | Updates tests for new required `contract` field (one case still missing it). | | src/tests/release/data_package/conftest.py | Adds fixtures for package/resource spec and mock registry variables. | | src/tests/release/data_package/test_resolve_resource.py | Adds unit tests for resource fetch/build/resolve behavior. | | src/tests/release/data_package/test_resolve_package.py | Adds unit tests for zip writer and descriptor round-tripping. | | src/tests/release/data_package/test_release_specification.py | Adds tests for spec validation (e.g., unique resource names). | | src/tests/release/data_package/test_create_data_package.py | Adds orchestrator tests (incl. end-to-end with fake registry). | | src/tests/release/data_package/__init__.py | New test package marker. | | src/tests/release/__init__.py | New test package marker. | | src/tests/release/data_package/test_data_resource.py | Removes tests for retired bespoke descriptor class. | | src/tests/release/data_package/test_data_package.py | Removes tests for retired bespoke package class. | | src/tests/contracts/test_utils.py | Removes tests tied to deleted `contracts.utils.read_yaml_or_json_file`. | | src/tests/contracts/contracts/test_metadata_models.py | Updates tests for DataSource→Source and new License validation message. | | src/tests/conftest.py | Updates factory comment/pattern reference (still mentions retired class in comment). | | src/tests/_standards/frictionless/test_table_schema.py | Adds coverage for standards TableSchema normalization/dispatch. | | src/tests/_standards/frictionless/test_metadata.py | Adds coverage for standards metadata blocks. | | src/tests/_standards/frictionless/test_descriptors.py | Adds coverage for standards resource/package composition + round-trip. | | src/tests/_standards/frictionless/__init__.py | New test package marker. | | src/tests/_standards/__init__.py | New test package marker. | | src/tests/_helpers/test_pydantic.py | Adds coverage for `OptionalNonEmptyList`. | | src/tests/_helpers/test_io.py | Adds coverage for YAML/JSON read + dump helpers and formatting. | | src/tests/_helpers/__init__.py | New test package marker. | | main_dev.py | Adds a dev script (currently includes hardcoded credentials). | | .claude/CLAUDE.md | Updates architecture docs to include `_standards` and release adapter. | | .ai-context/TODO.md | Updates TODOs for release adapter follow-ups and removes obsolete items. | | .ai-context/prds/2026-06-14-release-data-package-adapter.md | Adds PRD describing the release adapter feature. | | .ai-context/prds/.gitignore | Removes ignore pattern. | | .ai-context/issues/2026-06-14-release-data-package-adapter/01-spec-models.md | Adds implementation task note. | | .ai-context/issues/2026-06-14-release-data-package-adapter/02-adapter-build-helpers.md | Adds implementation task note. | | .ai-context/issues/2026-06-14-release-data-package-adapter/03-adapter-orchestration.md | Adds implementation task note. | | .ai-context/issues/2026-06-14-release-data-package-adapter/04-retire-and-wire-exports.md | Adds implementation task note. | | .ai-context/issues/2026-06-14-release-data-package-adapter/05-unit-tests.md | Adds implementation task note. | | .ai-context/issues/2026-06-14-release-data-package-adapter/06-integration-tests.md | Adds implementation task note. | | .ai-context/issues/.gitignore | Removes ignore pattern. | | .ai-context/CONTEXT.md | Updates glossary/context for the new release adapter approach. | | .ai-context/adrs/0003-release-is-a-contract-to-frictionless-adapter.md | Adds ADR formalizing the new release adapter design. | | .ai-context/adrs/0002-metadata-follows-frictionless-with-deviations.md | Clarifies two-layer metadata approach (curated vs faithful mirror). | </details>

  Co-authored-by: Copilot Autofix powered by AI <175728472+Copilot@users.noreply.github.com>



## v0.11.1 (2026-06-12)

### Bug fixes


- **Transformations** ([`2176fc7`](https://github.com/sweet-cross/crosscontract/commit/2176fc75a4bc1e05cfceba0f662c7470625a8749))

  ## Pull request overview

  Adds a new `crosscontract.transformations` package to support declarative fetch-shaping and pandas DataFrame transformations, with accompanying unit tests and supporting documentation updates.

  **Changes:**
  - Introduces declarative fetch specs (`FetchSpecMixin`, `ColumnAggregation`, `LevelKeepSpec`) that serialize into the raw shapes expected by `CrossDataVariable.get_data`.
  - Adds transformation specs + pure functions for common DataFrame operations (map values, rename columns, drop columns).
  - Adds a comprehensive pytest suite for the new transformation/fetch behavior and strengthens an existing aggregation equivalence test.

  ### Reviewed changes

  Copilot reviewed 16 out of 20 changed files in this pull request and generated 2 comments.

  <details> <summary>Show a summary per file</summary>

  | File | Description | | ---- | ----------- | | uv.lock | Updates lock metadata (including editable project version and marker normalization). | | src/crosscontract/transformations/__init__.py | Exposes the new transformations public API surface. | | src/crosscontract/transformations/fetch/__init__.py | Re-exports fetch-spec types. | | src/crosscontract/transformations/fetch/aggregation_spec.py | Adds validated aggregation directive models (including dict disambiguation). | | src/crosscontract/transformations/fetch/fetch_spec.py | Adds `FetchSpecMixin.get_data_kwargs` shaping logic. | | src/crosscontract/transformations/transformation/__init__.py | Re-exports transformation specs and pure functions. | | src/crosscontract/transformations/transformation/base.py | Introduces a strict base model for transformation specs (`extra='forbid'`). | | src/crosscontract/transformations/transformation/column_transformations.py | Adds `map_column_values` + `MapColumnValues` spec. | | src/crosscontract/transformations/transformation/dataframe_transformations.py | Adds `rename_columns`/`drop_columns` + corresponding specs. | | src/tests/transformations/__init__.py | Creates tests package for transformations. | | src/tests/transformations/fetch/__init__.py | Creates fetch tests package. | | src/tests/transformations/fetch/test_aggregation_spec.py | Tests `ColumnAggregation` parsing/dumping and validation. | | src/tests/transformations/fetch/test_fetch_spec.py | Tests `FetchSpecMixin.get_data_kwargs` output shapes and validation. | | src/tests/transformations/transformation/__init__.py | Creates transformation tests package. | | src/tests/transformations/transformation/test_colum_transformations.py | Tests `map_column_values` behavior and edge cases. | | src/tests/transformations/transformation/test_dataframe_transformations.py | Tests `rename_columns` / `drop_columns` behavior and errors. | | src/tests/transformations/transformation/test_transformation_specs.py | Tests spec/application parity + discriminator union behavior. | | src/tests/registry/test_data_variable.py | Adds regression test ensuring empty `keep` matches plain `level`. | | src/crosscontract/contracts/contracts/metadata_models.py | Expands `License` docstring attribute documentation. | | .ai-context/CONTEXT.md | Documents terminology for “Transformation” vs “Build spec”. | </details>



## v0.11.0 (2026-06-10)

### Features


- **Data package** ([`0a924e6`](https://github.com/sweet-cross/crosscontract/commit/0a924e64dc2b8c06bdf9af908148b60369c18e87))

  ## Pull request overview

  This PR introduces a Frictionless Data Package release artifact (`CrossDataPackage`) alongside existing data-resource support, and tightens validation/serialization to better match Frictionless wire formats.

  **Changes:**
  - Add `CrossDataPackage` model with `to_descriptor()` and `to_file()` for JSON/YAML emission.
  - Strengthen Frictionless-related constraints (contract `name` pattern; data-resource `path` validation; omit `None` fields in descriptors).
  - Add comprehensive tests + vendored Frictionless `data-package.json` schema for compliance checks.

  ### Reviewed changes

  Copilot reviewed 13 out of 14 changed files in this pull request and generated 5 comments.

  <details> <summary>Show a summary per file</summary>

  | File | Description | | ---- | ----------- | | uv.lock | Bumps locked package version to 0.10.3. | | src/tests/release/data_package/test_data_resource.py | Expands resource descriptor/path/metadata tests (includes new path constraint cases). | | src/tests/release/data_package/test_data_package.py | Adds end-to-end tests for data-package descriptor + file output + schema validation. | | src/tests/release/data_package/data-package.json | Adds Frictionless Data Package JSON Schema fixture used by tests. | | src/tests/contracts/contracts/test_contracts.py | Adds tests for updated Frictionless-compatible contract name constraints. | | src/tests/conftest.py | Pins factory `name` to a Frictionless-legal lowercase value for release tests. | | src/crosscontract/release/data_package/data_resource.py | Tightens `path` constraints and excludes `None` fields in `to_descriptor()`. | | src/crosscontract/release/data_package/data_package.py | Introduces `CrossDataPackage` model and JSON/YAML serialization. | | src/crosscontract/release/data_package/__init__.py | Exports `CrossDataPackage` from the subpackage. | | src/crosscontract/release/__init__.py | Re-exports `CrossDataPackage` at `crosscontract.release` level. | | src/crosscontract/contracts/contracts/cross_contract.py | Normalizes empty optional metadata lists to `None` prior to serialization. | | src/crosscontract/contracts/contracts/base_contract.py | Introduces `FRICTIONLESS_NAME_PATTERN` and applies it to contract `name`. | | .ai-context/TODO.md | Captures an open design decision around `tags` vs Frictionless `keywords`. | </details>

  <details> <summary>Comments suppressed due to low confidence (2)</summary>

  **src/tests/release/data_package/test_data_resource.py:154**
  * This call line exceeds the repo’s ruff line-length limit (E501). Wrap the arguments across lines to avoid lint failures in tests.
  **src/tests/release/data_package/test_data_resource.py:144**
  * This test function definition exceeds the repo’s ruff line-length limit (E501). Please wrap the parameters onto multiple lines to keep lint passing. </details>



## v0.10.3 (2026-06-10)

### Bug fixes


- **Data resource** ([`778c70a`](https://github.com/sweet-cross/crosscontract/commit/778c70a188bb93800582c91b659c2f184cfb777b))

  ## Pull request overview

  This PR introduces a new “release” surface area to represent a Frictionless-style **Data Resource** (a `CrossContract` bound to a physical data file) and adds initial tests/docs for it.

  **Changes:**
  - Add `CrossDataResource` model under `crosscontract.release`, including computed `profile` and path/format validation.
  - Add pytest coverage for `CrossDataResource` and a shared `contract_factory` fixture for release tests.
  - Update internal context docs to define “Data Resource / Data specification / Data Package” terminology; bump lockfile version.

  ### Reviewed changes

  Copilot reviewed 7 out of 8 changed files in this pull request and generated 4 comments.

  <details> <summary>Show a summary per file</summary>

  | File | Description | | ---- | ----------- | | `uv.lock` | Updates locked package version to `0.10.2`. | | `src/crosscontract/release/data_package/data_resource.py` | Adds the `CrossDataResource` model (contract + file-binding metadata). | | `src/crosscontract/release/data_package/__init__.py` | Exports `CrossDataResource` from the data_package submodule. | | `src/crosscontract/release/__init__.py` | Exports `CrossDataResource` as the release package public API. | | `src/tests/conftest.py` | Adds a root-level `contract_factory` fixture for tests outside `crossclient/`. | | `src/tests/release/test_data_resource.py` | Adds tests for `CrossDataResource` construction, profile computation, and validation. | | `.ai-context/CONTEXT.md` | Documents release/distribution terminology and intended behavior. | </details>



## v0.10.2 (2026-06-10)

### Bug fixes


- **Metadata extension** ([`6f29341`](https://github.com/sweet-cross/crosscontract/commit/6f29341977c80bc748b814ddc6fcfe4151bd6e68))

  ## Pull request overview

  This PR extends the contract metadata model to support Frictionless-aligned provenance/licensing fields by introducing dedicated Pydantic models and wiring them into `CrossMetaData`, along with tests and documentation updates.

  **Changes:**
  - Add `Contributor`, `DataSource`, and `License` Pydantic models (strict `extra="forbid"`) and document intentional Frictionless deviations.
  - Extend `CrossMetaData` with `contributors`, `sources`, and `licenses` fields.
  - Add unit tests and update docs/reference pages to include the new metadata models.

  ### Reviewed changes

  Copilot reviewed 9 out of 10 changed files in this pull request and generated 3 comments.

  <details> <summary>Show a summary per file</summary>

  | File | Description | | ---- | ----------- | | uv.lock | Updates locked editable package version metadata. | | src/tests/crossclient/conftest.py | Updates test factory to build valid nested `licenses` metadata. | | src/tests/contracts/contracts/test_metadata_models.py | Adds tests for new metadata models and validation behavior. | | src/crosscontract/contracts/contracts/metadata_models.py | Introduces new metadata Pydantic models (`Contributor`, `DataSource`, `License`). | | src/crosscontract/contracts/contracts/cross_contract.py | Adds new metadata fields to `CrossMetaData` and imports models. | | docs/reference/contracts.md | Exposes `metadata_models` in the API reference. | | docs/contracts/metadata.md | Documents new metadata fields and Frictionless relationship/deviations. | | .claude/CLAUDE.md | Updates repository guidance to include the new vendored Frictionless schema file. | | .ai-context/adrs/0002-metadata-follows-frictionless-with-deviations.md | Adds ADR clarifying Frictionless alignment and deliberate departures. | | .ai-context/additional_info/tabular-data-resource.json | Adds vendored upstream Frictionless schema reference. | </details>


### Chores


- **Claude setup** ([`60eaff8`](https://github.com/sweet-cross/crosscontract/commit/60eaff8579ad0f631df111c77cb28f576a3a917a))



## v0.10.1 (2026-06-05)

### Bug fixes


- **parquet for data upload** ([`7499ea6`](https://github.com/sweet-cross/crosscontract/commit/7499ea6fe2fb6ddfcfa27a3e30a5ecd02c1f122f))

  ## Pull request overview

  This PR updates the CrossClient contract data upload path to send DataFrames as Parquet instead of CSV, aligning uploads with the existing Parquet-based download path and improving fidelity/efficiency for typed data interchange.

  **Changes:**
  - Switch `ContractService._add_data()` upload serialization from CSV to Parquet (multipart file upload).
  - Set Parquet filename and MIME type for the uploaded payload.
  - Remove a stale CSV-related comment in the Parquet-based `_get_data()` path.





## v0.10.0 (2026-05-22)

### Features


- **delete contract data with client** ([`6bb9767`](https://github.com/sweet-cross/crosscontract/commit/6bb97676b8249c0c62620874e4732d5dced7739c))

  ## Pull request overview

  Adds a client-side API for deleting a *filtered subset* of contract data (row-level deletes) via the crossclient SDK, complementing the existing full-table `drop_data()` behavior.

  **Changes:**
  - Introduced `ContractService._delete_data()` to call `DELETE /contract/{name}/data` with equality filters encoded as query parameters (including repeated params for list values).
  - Added `ContractResource.delete_data()` as the public entry point, with a local guard requiring cached status to be `"Active"`.
  - Added pytest coverage for service- and resource-level delete behavior; updated `uv.lock` to reflect the current package version.

  ### Reviewed changes

  Copilot reviewed 4 out of 5 changed files in this pull request and generated 3 comments.

  <details> <summary>Show a summary per file</summary>

  | File | Description | | ---- | ----------- | | uv.lock | Updates locked editable package version to 0.9.0. | | src/crosscontract/crossclient/services/contract_service.py | Adds `_delete_data()` implementation and filter typing/serialization. | | src/crosscontract/crossclient/services/contract_resource.py | Adds `delete_data()` public method with status guard and typed filters. | | src/tests/crossclient/contracts/test_contracts_service.py | Adds tests validating query-param encoding and error propagation for `_delete_data()`. | | src/tests/crossclient/contracts/test_contract_resource.py | Adds tests validating `delete_data()` delegation and non-Active status behavior. | </details>

  Co-authored-by: Copilot Autofix powered by AI <175728472+Copilot@users.noreply.github.com>


### Documentation


- **warn against skip-ci token in PR titles and bodies** ([`eadbdc5`](https://github.com/sweet-cross/crosscontract/commit/eadbdc5bd0a2a9248bd05850f1236d477ad91b2f))

  GitHub scans the squash-merge commit message (PR title plus body) for the built-in skip-ci token and suppresses downstream workflows when it finds one. A prior PR re-introduced that token in its description while explaining the fix, breaking check_pr_main on the next dev to main PR. Add a note to the workflow header so future contributors avoid the same trap.


### Chores


- **replace [skip ci] with custom [skip release] marker** ([`effae1d`](https://github.com/sweet-cross/crosscontract/commit/effae1d75b037e66b271381a3dcdcf4b802420a9))

  GitHub's [skip ci] token suppresses both push and pull_request workflow runs whose head commit carries it. That broke check_pr_main on dev to main PRs whose head was the PSR version-bump commit.

  Switch to a custom [skip release] marker that PSR writes into its bump commit message and that release_dev_branch.yml explicitly checks. GitHub does not recognize this token, so dev to main PRs run check_pr_main normally, but Release Dev Branch still skips itself on PSR's own commits and avoids re-running the full test matrix.



## v0.9.0 (2026-05-08)



### Features


- **Add colors** ([`b060520`](https://github.com/sweet-cross/crosscontract/commit/b060520a890513f102099fc0e2fb7009848bc477))

  ## Pull request overview

  Adds optional `color` support to dimension contracts across the schema template, registry dimension wrappers, tests, and documentation to enable downstream visualization use-cases (e.g., plotting).

  **Changes:**
  - Extend the rigid `DimensionSchema` template with an optional `color` field (hex format constraints) and document it.
  - Add `color_map` to registry-side dimension variables, mirroring `label_map` behavior and introducing caching.
  - Add/extend tests to include the `color` field in dimension fixtures and verify `color_map` behavior.

  ### Reviewed changes

  Copilot reviewed 5 out of 5 changed files in this pull request and generated 4 comments.

  <details> <summary>Show a summary per file</summary>

  | File | Description | | ---- | ----------- | | src/crosscontract/registry/variables/base_dimension.py | Adds cached `color_map` accessor and clears its cache alongside existing caches. | | src/crosscontract/contracts/schema/subschemas/dimension.py | Adds `color` field to the rigid Dimension schema template and updates its docstring. | | src/tests/registry/test_dimensions.py | Updates dimension test fixtures to include `color` and adds a new `TestColorMap` suite. | | src/tests/contracts/schema/subschemas/test_dimension_schema.py | Verifies `color` is present in schema fields when loading a Dimension contract from YAML. | | docs/contracts/contract_types.md | Updates Dimension contract documentation to include `color` in the field list (table format). | </details>



## v0.8.7 (2026-04-28)



### Bug fixes


- **skip unparseable commits in changelog template** ([`d754da6`](https://github.com/sweet-cross/crosscontract/commit/d754da6dbdcb15ba8a3be88b6a18cec0a9f98534))

  Fixing error in change logs

- **improve changelog messages** ([`58a44b0`](https://github.com/sweet-cross/crosscontract/commit/58a44b05b07509365b6c67676d0606acdb45c48b))

  Getting changelog from the PR commit messages



## v0.8.6 (2026-04-28)



### Bug fixes


- **versioning on dev** ([`55c7889`](https://github.com/sweet-cross/crosscontract/commit/55c7889601a64872ba9f524b2835604be1465bda))

- **Registry identify dimensions** ([`5808b99`](https://github.com/sweet-cross/crosscontract/commit/5808b99cdb0c5478c6aa94ae3850ba45de4cd4f7))

  ## Pull request overview

  This PR updates the registry layer to identify and wrap contracts based on their declared contract/schema type (Dimension vs FlexibleDimension vs data variable), rather than relying on name prefixes like `dim_`. It also introduces a registry-side abstraction for dimensions that supports both hierarchical and non-hierarchical dimension contracts.

  **Changes:**
  - Add `CrossBaseVariable` / `CrossBaseDimension` and a new `CrossFlexibleDimension` wrapper; make `CrossDimension` inherit from the new dimension base.
  - Update `CrossRegistry.add_variable()` to decide wrappers using `ContractResource.is_dimension` and `contract.contract_type`, and to hydrate FKs with both dimension types.
  - Update tests and tutorial notebook to use `parent_id` and to cover flexible dimensions + flexible-dimension FK behavior; bump lock version.

  ### Reviewed changes

  Copilot reviewed 12 out of 14 changed files in this pull request and generated 2 comments.

  <details> <summary>Show a summary per file</summary>

  | File | Description | | ---- | ----------- | | uv.lock | Bumps package version to 0.8.5 in the lockfile. | | src/crosscontract/registry/registry.py | Switches contract discovery/filtering and variable loading to type-based logic; adds `get_contract_overview`. | | src/crosscontract/registry/variables/base_variable.py | Introduces shared registry-side base with common contract/data access. | | src/crosscontract/registry/variables/base_dimension.py | Introduces shared dimension base and `label_map` for all dimension types. | | src/crosscontract/registry/variables/flexible_dimension.py | Adds wrapper for non-hierarchical (flexible) dimensions. | | src/crosscontract/registry/variables/dimension.py | Moves hierarchical dimension wrapper onto the new dimension base; updates to `parent_id`. | | src/crosscontract/registry/variables/data_variable.py | Allows dimensions to be either hierarchical or flexible; prevents hierarchical aggregation on flexible dimensions. | | src/crosscontract/registry/variables/__init__.py | Exposes the new variable/dimension wrapper types. | | src/crosscontract/registry/__init__.py | Re-exports the new types from `crosscontract.registry`. | | src/tests/registry/conftest.py | Updates test ContractResource mocks to include `is_dimension`. | | src/tests/registry/test_registry.py | Updates registry tests for contract-type filtering and flexible dimension behavior. | | src/tests/registry/test_dimensions.py | Updates dimension fixtures/schema to use `parent_id` and explicit `primaryKey`. | | src/tests/registry/test_data_variable.py | Adds coverage for aggregation rejection on flexible dimensions; updates fixtures. | | notebooks/registry_tutorial.ipynb | Clears outputs and updates example code to use `parent_id`. | </details>


### Chores


- **new actions with dev branch** ([`487d9cf`](https://github.com/sweet-cross/crosscontract/commit/487d9cf7271e854661d8b129d5faf35a388eaba3))



## v0.8.5 (2026-04-28)



### Bug fixes


- **introduce contract types at the client level** ([`9c7b548`](https://github.com/sweet-cross/crosscontract/commit/9c7b548c42816ab14ac378cb880784d0ee15ac6f))

  ## Pull request overview

  This PR updates the CrossClient contract surface to carry `contract_type` through client resources and adds optional server-side filtering by contract type when listing contracts.

  **Changes:**
  - Parse contract responses via a centralized `ContractResource.from_response()` payload shape (including `name`, `status`, and `contract_type`).
  - Add `contract_type` filtering to `ContractService.get_list()` and corresponding tests.
  - Introduce `.claude/` repository guidance/config files.

  ### Reviewed changes

  Copilot reviewed 6 out of 7 changed files in this pull request and generated 5 comments.

  <details> <summary>Show a summary per file</summary>

  | File | Description | | ---- | ----------- | | `uv.lock` | Updates locked editable package version to `0.8.4`. | | `src/crosscontract/crossclient/services/contract_service.py` | Adds optional `contract_type` query filtering and switches to `ContractResource.from_response()` parsing. | | `src/crosscontract/crossclient/services/contract_resource.py` | Adds response payload validation, persists `contract_type`, and adds `is_dimension` helper. | | `src/tests/crossclient/contracts/test_contracts_service.py` | Updates expected response payloads and adds query-param assertions for filtering. | | `src/tests/crossclient/contracts/test_contract_resource.py` | Refactors resource construction around server-style payloads; adds `is_dimension` tests. | | `.claude/settings.local.json` | Adds Claude local permissions config. | | `.claude/CLAUDE.md` | Adds repository workflow/architecture guidance for Claude. | </details>



## v0.8.4 (2026-04-20)



### Bug fixes


- **refernce validation at the BaseContract using resolver** ([`04c12fd`](https://github.com/sweet-cross/crosscontract/commit/04c12fd0d3e70693dacb1d829bb6ff4a16a0b1a9))

  ## Pull request overview

  Adds reference validation to `BaseContract` using a resolver abstraction, and provides tests to verify existence/field integrity checks plus optional star-schema enforcement (default on for `CrossContract`).

  **Changes:**
  - Introduce `ContractResolver` protocol for resolving referenced contracts by name.
  - Add `BaseContract.validate_references(...)` with aggregated error reporting and optional star-schema enforcement.
  - Add `CrossContract.validate_references(...)` wrapper that defaults `enforce_star_schema=True`, plus comprehensive unit tests.

  ### Reviewed changes

  Copilot reviewed 4 out of 4 changed files in this pull request and generated 3 comments.

  | File | Description | | ---- | ----------- | | `src/crosscontract/contracts/contracts/base_contract.py` | Implements resolver-based reference validation with optional star-schema checks and aggregated errors. | | `src/crosscontract/contracts/contracts/cross_contract.py` | Adds a `validate_references` override that enables star-schema enforcement by default. | | `src/crosscontract/contracts/contracts/resolvers.py` | Introduces `ContractResolver` protocol used by contract reference validation. | | `src/tests/contracts/contracts/test_contract_reference_validation.py` | Adds tests covering pass/fail cases, aggregation, and star-schema behavior for `BaseContract`/`CrossContract`. |



## v0.8.3 (2026-04-20)



### Bug fixes


- **Flexible dimension** ([`c0a8378`](https://github.com/sweet-cross/crosscontract/commit/c0a8378ef3b4e7ad73f27b337e989a53780ff31a))

  ## Pull request overview

  This PR introduces a new “FlexibleDimension” schema type by adding a reusable base dimension schema, plus a mechanism for schema subclasses to enforce mandatory field presence/type.

  **Changes:**
  - Added `BaseDimensionSchema` and refactored `DimensionSchema` to inherit shared dimension invariants.
  - Added `FlexibleDimensionSchema` with mandatory-field validation support in `TableSchema`.
  - Added/updated tests for base-dimension invariants and flexible-dimension mandatory fields.

  ### Reviewed changes

  Copilot reviewed 9 out of 10 changed files in this pull request and generated 6 comments.

  <details> <summary>Show a summary per file</summary>

  | File | Description | | ---- | ----------- | | src/tests/contracts/schema/subschemas/test_flexible_dimension.py | New tests for mandatory field enforcement and inherited dimension invariants. | | src/tests/contracts/schema/subschemas/test_base_dimension.py | New tests validating abstract base behavior, primary key requirement, and self-only foreign keys. | | src/crosscontract/contracts/schema/subschemas/value_variable.py | New module location for `ValueVariableSchema` (module naming change). | | src/crosscontract/contracts/schema/subschemas/flexible_dimension.py | Adds `FlexibleDimensionSchema` and declares mandatory fields. | | src/crosscontract/contracts/schema/subschemas/dimension.py | Switches `DimensionSchema` to inherit from `BaseDimensionSchema` and uses `deepcopy` for template injection. | | src/crosscontract/contracts/schema/subschemas/base_dimension.py | Introduces shared validators for dimension-like schemas. | | src/crosscontract/contracts/schema/subschemas/__init__.py | Updates exports/imports to new module layout and adds new schemas to `__all__`. | | src/crosscontract/contracts/schema/schema.py | Adds `MandatoryField` and a `TableSchema` validator enforcing subclass mandatory fields. | | src/crosscontract/contracts/schema/reference/primary_key.py | Adds a `fields` convenience property to `PrimaryKey`. | | src/crosscontract/contracts/schema/__init__.py | Exports `FlexibleDimensionSchema` at the package level. | </details>



## v0.8.2 (2026-04-16)



### Bug fixes


- **other category naming** ([`2ca46d7`](https://github.com/sweet-cross/crosscontract/commit/2ca46d78e689b8b7892b37fc2b4cffb10a9e7005))

  ## Pull request overview

  Updates the dimension “other” category naming convention and related validation messaging across Pandera checks, tests, and documentation.

  **Changes:**
  - Switch “other” sibling ID convention for non-root levels from `other_<parent_id>` to `<parent_id>_other`.
  - Rename Pandera dimension check `name=` prefixes from `DimensionError` to `DimensionCheck`.
  - Update docs/tests to reflect the new naming and check labeling.

  ### Reviewed changes

  Copilot reviewed 4 out of 4 changed files in this pull request and generated 5 comments.

  | File | Description | | ---- | ----------- | | `src/crosscontract/contracts/schema/adapters/_pandera_dimension_checks.py` | Updates Pandera check names and changes `_check_other_entries` expected sibling ID format. | | `src/tests/contracts/schema/adapters/pandera/test_integration_dimension_schema.py` | Adjusts integration test data and error filtering to match new naming/check prefix. | | `src/tests/contracts/schema/adapters/pandera/test_dimension_check.py` | Updates unit tests for `_check_other_entries` to the new `<parent_id>_other` convention. | | `docs/contracts/contract_types.md` | Updates dimension contract docs for the “other” naming rule and id character description. |



## v0.8.1 (2026-04-16)



### Bug fixes


- **allow capital letters for dimension ids (to allow for iso codes)** ([`4496e6a`](https://github.com/sweet-cross/crosscontract/commit/4496e6a2c2b977d0e6201f22bb207193e4ed454b))



## v0.8.0 (2026-04-16)



### Features


- **from_/to_server methods for CrossContract** ([`73af93a`](https://github.com/sweet-cross/crosscontract/commit/73af93a56c657d67579f012354e8c36b7184dc55))

  ## Pull request overview

  Adds explicit server/request serialization helpers for `CrossContract` and updates the crossclient contract service/resource flow to use them, ensuring Dimension contracts can round-trip cleanly with server payloads.

  **Changes:**
  - Introduce `CrossContract.to_server()` and `CrossContract.from_server()` to normalize request/response payloads (notably stripping `tableschema` for Dimension contracts).
  - Update `ContractService` to use these helpers when creating and fetching contracts.
  - Adjust `ContractResource.refresh()` behavior (and tests) to refresh both contract details and status.

  ### Reviewed changes

  Copilot reviewed 5 out of 5 changed files in this pull request and generated 4 comments.

  <details> <summary>Show a summary per file</summary>

  | File | Description | | ---- | ----------- | | `src/crosscontract/contracts/contracts/cross_contract.py` | Adds `to_server()` / `from_server()` with Dimension-specific `tableschema` handling. | | `src/crosscontract/crossclient/services/contract_service.py` | Uses new (de)serialization helpers for create/get/list; docstring typo fix. | | `src/crosscontract/crossclient/services/contract_resource.py` | `refresh()` now consumes a `ContractResource` from the service and updates status. | | `src/tests/crossclient/contracts/test_contract_resource.py` | Updates refresh tests to mock `ContractService.get()` returning a `ContractResource`; adds status refresh assertion. | | `src/tests/contracts/contracts/test_contracts.py` | Adds roundtrip tests for `to_server()`/`from_server()`. | </details>



## v0.7.0 (2026-04-02)



### Features


- **28 feature contract types** ([`9386f51`](https://github.com/sweet-cross/crosscontract/commit/9386f51693fbdd5971e600bf701a5cbe4185a7f6))

  ## Pull request overview

  Adds contract “type” support to the contracts layer by introducing a discriminator-based `TableSchema` union and routing logic in `CrossContract`, with accompanying schema subclasses and tests.

  **Changes:**
  - Introduce `contract_type` on `CrossContract` and inject `table_type` into `tableschema` for discriminator-based schema selection.
  - Add `DimensionSchema` / `ValueVariableSchema` subclasses and export them from the schema package.
  - Add a new test suite validating contract-type routing and the injection helper behavior.

  ### Reviewed changes

  Copilot reviewed 9 out of 9 changed files in this pull request and generated 4 comments.

  <details> <summary>Show a summary per file</summary>

  | File | Description | | ---- | ----------- | | `src/crosscontract/contracts/contracts/cross_contract.py` | Adds `contract_type`, discriminated `tableschema` union, and pre-validation injection helper. | | `src/crosscontract/contracts/schema/schema.py` | Adds `table_type` discriminator field to `TableSchema`. | | `src/crosscontract/contracts/schema/subschemas/dimension_schema.py` | Adds `DimensionSchema` specialization with `table_type="Dimension"`. | | `src/crosscontract/contracts/schema/subschemas/value_variable_schema.py` | Adds `ValueVariableSchema` specialization with `table_type="ValueVariable"`. | | `src/crosscontract/contracts/schema/subschemas/__init__.py` | Exposes new subschemas via package exports. | | `src/crosscontract/contracts/schema/__init__.py` | Re-exports `DimensionSchema` and `ValueVariableSchema`. | | `src/tests/contracts/contracts/test_contract_types.py` | New tests for contract type routing and `_inject_table_type_to_schema`. | | `src/tests/crossclient/conftest.py` | Sets `contract_type="General"` default for the crossclient `CrossContractFactory`. | | `.vscode/launch.json` | Changes shared pytest debug launch config to target a single test. | </details>



## v0.6.0 (2026-03-15)



### Features


- **Flexible aggregation** ([`52e919b`](https://github.com/sweet-cross/crosscontract/commit/52e919bc80f9a6b6cebcdcdea753088312161a74))

  Introduce more flexible aggregations allowing to aggregation at different levels. Fixed typing errors

  Co-authored-by: Copilot Autofix powered by AI <175728472+Copilot@users.noreply.github.com>



## v0.5.0 (2026-03-14)



### Features


- **Registry refinements** ([`0af990f`](https://github.com/sweet-cross/crosscontract/commit/0af990fc65da267ae3fcffa54a64652237a18bfb))

  ## Pull request overview

  Refines the `CrossRegistry`/variable APIs and documentation to make registry usage more convenient (contract overview listing, improved dimension handling, and new docs/tutorial content).

  **Changes:**
  - Added `CrossRegistry.contract_overview` and expanded docs/tutorial coverage for the registry.
  - Changed `CrossDataVariable.dimensions` to be keyed by the foreign key column name (e.g., `"region"`) and updated related tests.
  - Exported `CrossRegistry` at the package top level and added new MkDocs pages/notebook.

  ### Reviewed changes

  Copilot reviewed 11 out of 11 changed files in this pull request and generated 9 comments.

  <details> <summary>Show a summary per file</summary>

  | File | Description | | ---- | ----------- | | src/crosscontract/registry/registry.py | Adds `contract_overview`; refines `add_variable` behavior and return typing/docs. | | src/crosscontract/registry/data_variable.py | Changes dimension storage semantics (keyed by FK column), adds `__repr__`, updates labeling/aggregation lookup. | | src/crosscontract/__init__.py | Re-exports `CrossRegistry` from the top-level package. | | src/tests/registry/test_registry.py | Adds coverage for `contract_overview`; updates dimension expectations to `"region"`. | | src/tests/registry/test_data_variable.py | Adds `__repr__` test; updates dimension expectations; adjusts dimension-add semantics tests. | | notebooks/registry_tutorial.ipynb | New tutorial notebook demonstrating `CrossRegistry` usage. | | mkdocs.yml | Adds CrossRegistry section to docs navigation. | | docs/registry/index.md | New CrossRegistry overview page. | | docs/reference/registry.md | New API reference page for registry-related classes. | | docs/index.md | Adds CrossRegistry to package overview. | | docs/about.md | Updates About page text. | </details>



## v0.4.0 (2026-03-13)



### Features


- **Introduce registry** ([`2c18cb1`](https://github.com/sweet-cross/crosscontract/commit/2c18cb1a07dc95bba99071f3607897f92d9d7263))

  ## Pull request overview

  Introduces a new `crosscontract.registry` module to provide a higher-level registry abstraction over CROSS contracts/resources, including support for lazy loading, dimensions, and common data operations.

  **Changes:**
  - Added `CrossRegistry`, `CrossBaseVariable`, `CrossDataVariable`, and `CrossDimension` implementations.
  - Added comprehensive pytest coverage for registry behavior, dimensions, and data variables (filters, aggregation, titles).
  - Expanded public exports in `crossclient` and `contracts.schema` / `contracts.schema.fields`.

  ### Reviewed changes

  Copilot reviewed 14 out of 14 changed files in this pull request and generated 5 comments.

  <details> <summary>Show a summary per file</summary>

  | File | Description | | ---- | ----------- | | src/crosscontract/registry/registry.py | Implements the new registry with lazy loading and FK hydration. | | src/crosscontract/registry/base_variable.py | Adds shared variable base (lazy data caching, contract helpers). | | src/crosscontract/registry/data_variable.py | Adds data variable operations: filters, aggregation, title relabeling. | | src/crosscontract/registry/dimension.py | Adds dimension helpers for label maps and ancestor maps. | | src/crosscontract/registry/__init__.py | Exposes the new registry API via package exports. | | src/crosscontract/crossclient/__init__.py | Exposes additional crossclient service types publicly. | | src/crosscontract/contracts/schema/__init__.py | Re-exports commonly used schema types at the package level. | | src/crosscontract/contracts/schema/fields/__init__.py | Exposes `BaseField` in the fields package exports. | | src/tests/registry/conftest.py | Adds shared fixture for creating mocked contract resources. | | src/tests/registry/test_registry.py | Adds tests for registry init/add/get and dunder behavior. | | src/tests/registry/test_dimensions.py | Adds tests for dimension label/ancestor maps and caching. | | src/tests/registry/test_data_variable.py | Adds tests for data variable filtering, aggregation, titles, FK handling. | | src/tests/registry/test_base_variable.py | Adds tests for base variable properties and lazy data caching. | | .claude/worktrees/eager-chebyshev | Adds a worktree/subproject pointer file (likely unintended). | </details>

  <details>



## v0.3.0 (2026-03-08)



### Features


- **validation returns validated dataframe** ([`ae6a389`](https://github.com/sweet-cross/crosscontract/commit/ae6a3896abdf2ce3a46fa2b848b449a321ff281f))



## v0.2.3 (2026-03-08)



### Bug fixes


- **correct format in csv upload for datetime fields** ([`9501a14`](https://github.com/sweet-cross/crosscontract/commit/9501a14685e90b176982c6cf51d6bd043898b453))

  ## Pull request overview

  This PR fixes datetime formatting for CSV uploads in the crossclient by formatting datetime columns according to the contract’s `DateTimeField.format` before sending data to the API.

  **Changes:**
  - Add `_prepare_dataframe_csv_upload()` to format datetime columns (per TableSchema) prior to CSV serialization.
  - Update `ContractResource.add_data()` to upload the prepared DataFrame instead of the raw input.
  - Add unit tests covering `_prepare_dataframe_csv_upload()` for datetime vs non-datetime schemas.

  ### Reviewed changes

  Copilot reviewed 3 out of 3 changed files in this pull request and generated 3 comments.

  | File | Description | | ---- | ----------- | | `src/crosscontract/crossclient/services/contract_resource.py` | Adds DataFrame pre-processing for datetime columns and uses it in `add_data()`. | | `src/crosscontract/crossclient/services/contract_service.py` | Minor formatting change (blank line) in `_add_data()`. | | `src/tests/crossclient/contracts/test_contract_resource.py` | Adds tests for the new CSV-preparation behavior and imports `TableSchema`. |


### Chores


- **rename action** ([`ba3822a`](https://github.com/sweet-cross/crosscontract/commit/ba3822a13175809738a1e814ab8beba0d3a06d09))



## v0.2.2 (2026-03-05)



### Bug fixes


- **publishing** ([`c49159d`](https://github.com/sweet-cross/crosscontract/commit/c49159da933ab30c12a0e5e5b40f2bffd2fd6b89))



## v0.2.1 (2026-03-05)



### Bug fixes


- **docs** ([`937b76f`](https://github.com/sweet-cross/crosscontract/commit/937b76f8fbf30d4615cdb0178bfc8f72ca66e4ce))


### Chores


- **add PyPI-test publish workflow** ([`c852441`](https://github.com/sweet-cross/crosscontract/commit/c85244124aa00a697521ba3b9c1e30577a80fdfa))



## v0.2.0 (2026-03-05)



### Features


- **Pandera adapter with foreign key checks** ([`e1ab1c5`](https://github.com/sweet-cross/crosscontract/commit/e1ab1c52e125dc7da515b3066e9366269c6d83b2))

  ## Pull request overview

  This PR enhances the Pandera adapter/validation layer to support primary key uniqueness and foreign key integrity checks (including self-references), and consolidates DataFrame validation under a new `validate_dataframe` entrypoint.

  **Changes:**
  - Add PK/FK (incl. self-reference) validation checks to `PanderaPandasAdapter` and expose corresponding parameters through `TableSchema.to_pandera_schema`.
  - Replace the old `validate_pandas_dataframe` module with a new `schema.validation.validate_dataframe` function and re-route `TableSchema.validate_dataframe` through it.
  - Add/adjust tests for reference validation and backend-selection error paths.

  ### Reviewed changes

  Copilot reviewed 8 out of 8 changed files in this pull request and generated 7 comments.

  <details> <summary>Show a summary per file</summary>

  | File | Description | | ---- | ----------- | | src/crosscontract/contracts/schema/adapters/pandera_adapter.py | Adds PK/FK Pandera checks and schema conversion options to enforce relational constraints. | | src/crosscontract/contracts/schema/schema.py | Extends `to_pandera_schema` to pass PK/FK validation parameters; routes validation via the new `validate_dataframe`. | | src/crosscontract/contracts/schema/validation/validate_dataframe.py | New unified validation entrypoint with backend selection and SchemaValidationError wrapping. | | src/crosscontract/contracts/schema/validation/__init__.py | Exports `validate_dataframe` for package-level access. | | src/crosscontract/contracts/schema/validation/validate_pandas_dataframe.py | Removed legacy validation function/module. | | src/tests/contracts/schema/test_schema.py | Updates default Pandera schema name expectation and adds unsupported-backend test. | | src/tests/contracts/schema/adapters/test_integration_pandera_references.py | New integration tests covering PK/FK checks using the adapter directly. | | src/tests/contracts/contracts/validation/test_pandas_validation.py | Updates tests to use `validate_dataframe` instead of the removed legacy function. | </details>

  * pandera adapter: include primary key checks

  * tests for primary key validation

  * pandera: foreign key check

  refactor of dataframe_validation

  * Update src/crosscontract/contracts/schema/adapters/pandera_adapter.py

  Co-authored-by: Copilot <175728472+Copilot@users.noreply.github.com>

  * Update src/tests/contracts/contracts/validation/test_pandas_validation.py

  * Update src/crosscontract/contracts/schema/schema.py

  * allow for non-lazy evaluation and associated error parsing in pandera SchemaError (singular) in pandera error parsing (non-lazy evaluation).

  * testing

  * typing

  * copilote comments

  ---------


### Refactoring


- **Pandera adapter** ([`b6ba131`](https://github.com/sweet-cross/crosscontract/commit/b6ba1319c54ed9ab994682fabf0cadc4b5852be2))

  ## Pull request overview

  This PR refactors the Pandera adapter implementation to follow a consistent adapter pattern similar to the SQLAlchemy and Pydantic adapters. The refactoring moves Pandera-specific logic from individual field classes into a centralized `PanderaPandasAdapter` class.

  **Changes:**
  - Moved Pandera conversion logic from `converter.py` to `adapters/pandera_adapter.py` with a proper adapter class
  - Removed Pandera-specific methods (`get_pandera_kwargs`, `python_type`, `pandera_type`) from field classes, centralizing this logic in the adapter
  - Migrated and reorganized test suite to match the new adapter structure

  ### Reviewed changes

  Copilot reviewed 19 out of 20 changed files in this pull request and generated 3 comments.

  <details> <summary>Show a summary per file</summary>

  | File | Description | | ---- | ----------- | | src/crosscontract/contracts/schema/adapters/pandera_adapter.py | New adapter class implementing centralized Pandera schema conversion | | src/crosscontract/contracts/schema/adapters/__init__.py | Added exports for new Pandera adapter | | src/crosscontract/contracts/schema/__init__.py | Updated import to use new adapter location | | src/crosscontract/contracts/schema/schema.py | Updated import path from converter to adapters | | src/crosscontract/contracts/schema/fields/base.py | Removed Pandera-specific methods from base classes | | src/crosscontract/contracts/schema/fields/string_field.py | Removed Pandera-specific implementation details | | src/crosscontract/contracts/schema/fields/numeric_field.py | Removed Pandera-specific implementation details | | src/crosscontract/contracts/schema/fields/list_field.py | Removed Pandera-specific implementation details | | src/crosscontract/contracts/schema/fields/datetime_field.py | Removed Pandera-specific implementation details and moved parse_datetime to utils | | src/crosscontract/contracts/schema/converter.py | Deleted - replaced by adapter pattern | | src/crosscontract/contracts/schema/adapters/sqlalchemy_adapter.py | Made metadata parameter optional with default None | | src/tests/contracts/schema/adapters/test_pandera_pandas_adapter.py | New comprehensive test suite for Pandera adapter | | src/tests/contracts/schema/adapters/test_sqlaqlchemy_adapter.py | Updated test to use new convert function directly | | src/tests/contracts/schema/test_converter.py | Deleted - tests moved to new adapter test file | | src/tests/contracts/schema/fields/test_*.py | Deleted - field-level Pandera tests no longer needed | </details>

  * pandera adapter

  * replaced old covnertor in schema

  * cleaning: keep field models lean

  * removed usage of convert_... functions

  * pandera integration checks

  * copilote comments

- **Sql adapter** ([`9adabc2`](https://github.com/sweet-cross/crosscontract/commit/9adabc2e4997be35c2406da38ff90d56f6b2aa88))

  ## Pull request overview

  This PR refactors the SQLAlchemy conversion logic by introducing a new adapter pattern for schema conversions. The changes move SQLAlchemy-specific functionality from individual field classes to a centralized `SQLAlchemyPostgresAdapter`, following the same pattern as the existing `PydanticAdapter`. This improves maintainability and separation of concerns.

  **Changes:**
  - Introduced `AbstractAdapter` base class and `SQLAlchemyPostgresAdapter` for SQLAlchemy table conversion
  - Removed `to_sqlalchemy_column()` method from field classes (BaseField, StringField, NumericField, ListField, DateTimeField)
  - Migrated SQLAlchemy conversion logic from `converter.py` to new `adapters/sqlalchemy_adapter.py`
  - Renamed `_convert_number_field` to `_convert_numeric_field` in PydanticAdapter for consistency
  - Updated all adapter classes to provide both instance `convert()` and classmethod `convert_schema()` methods

  ### Reviewed changes

  Copilot reviewed 20 out of 20 changed files in this pull request and generated 4 comments.

  <details> <summary>Show a summary per file</summary>

  | File | Description | | ---- | ----------- | | src/crosscontract/contracts/schema/adapters/abstract_adapter.py | New abstract base class defining the adapter pattern with convert() and convert_schema() methods | | src/crosscontract/contracts/schema/adapters/sqlalchemy_adapter.py | New SQLAlchemyPostgresAdapter implementation with centralized column creation logic | | src/crosscontract/contracts/schema/adapters/pydantic_adapter.py | Updated to extend AbstractAdapter and renamed _convert_number_field to _convert_numeric_field | | src/crosscontract/contracts/schema/fields/base.py | Removed abstract to_sqlalchemy_column() method | | src/crosscontract/contracts/schema/fields/*.py | Removed to_sqlalchemy_column() implementations from all field classes | | src/crosscontract/contracts/schema/converter.py | Removed convert_schema_to_sqlalchemy function | | src/crosscontract/contracts/schema/schema.py | Updated to use SQLAlchemyPostgresAdapter.convert_schema() and PydanticAdapter.convert_schema() | | src/crosscontract/contracts/schema/adapters/__init__.py | Added SQLAlchemyPostgresAdapter and convert_schema_to_sqlalchemy exports | | src/tests/contracts/schema/adapters/test_sqlqlchemy_adapter.py | New comprehensive test suite for SQLAlchemyPostgresAdapter | | src/tests/contracts/schema/fields/test_*.py | Removed to_sqlalchemy_column tests from field test files | | src/tests/contracts/schema/test_converter.py | Removed SQLAlchemy conversion tests | | src/tests/contracts/schema/adapters/test_pydantic_adapater.py | Updated test calls to use _convert_numeric_field | | src/tests/contracts/schema/adapters/test_integration_pydantic.py | Updated to use PydanticAdapter.convert_schema() classmethod | </details>

  * sqlqlchemy postgres adapter

  * remove old sqlconverter; cleaning

  * abstract adapter class

  * copilote comments

- **Pydantic adapter** ([`2ad53cc`](https://github.com/sweet-cross/crosscontract/commit/2ad53ccb26df786e8db583c779efd03c80f91a68))

  ## Pull request overview

  This PR refactors the Pydantic model generation from schemas by introducing a dedicated adapter pattern. The main goal is to separate concerns and provide better organization for schema conversion functionality while adding support for ListField types.

  **Changes:**
  - Introduced a new `PydanticAdapter` class that encapsulates Pydantic model generation logic using an adapter pattern
  - Moved Pydantic-specific field conversion logic from field classes (removal of `get_pydantic_field_kwargs()` methods) to the adapter
  - Added support for ListField types with integer, string, number, and boolean item types
  - Created comprehensive unit and integration tests for the new adapter

  ### Reviewed changes

  Copilot reviewed 21 out of 21 changed files in this pull request and generated 9 comments.

  <details> <summary>Show a summary per file</summary>

  | File | Description | | ---- | ----------- | | src/crosscontract/contracts/schema/adapters/pydantic_adapter.py | New adapter class with field conversion methods for all field types | | src/crosscontract/contracts/schema/adapters/utils.py | Utility function for datetime parsing (moved from datetime_field.py) | | src/crosscontract/contracts/schema/adapters/__init__.py | Module exports for the new adapters package | | src/crosscontract/contracts/schema/schema.py | Updated imports and added ListField to FieldUnion | | src/crosscontract/contracts/schema/fields/*.py | Removed `get_pydantic_field_kwargs()` methods from field classes | | src/crosscontract/contracts/schema/converter.py | Removed `convert_schema_to_pydantic()` function (moved to adapter) | | src/crosscontract/contracts/schema/__init__.py | Updated import path for convert_schema_to_pydantic | | src/tests/contracts/schema/adapaters/*.py | New comprehensive test suite for the adapter | | src/tests/contracts/schema/fields/*.py | Removed Pydantic-specific tests from field test files | | src/tests/contracts/schema/test_converter.py | Removed Pydantic conversion tests (migrated to new test files) | | pyproject.toml | Added commit_message configuration (unrelated to main PR purpose) | </details>

  chore: add skip ci to semantic release commit message

  * pydantic converter

  * connect pydantic adpater

  * add list field conversion

  * cleaning: remove pydantic covnersion from fields

  * integration tests

  * mypy, copilot comments



## v0.1.2 (2026-02-16)



### Bug fixes


- **Introduce base url** ([`9b9c951`](https://github.com/sweet-cross/crosscontract/commit/9b9c951c28c11375fcd2dff00a3f1420ebce4c69))

  * introduce base_url equal to prod server, remove py3.10 typing

  * remove main_dev

  docs

  * linting

  * Update docs/contracts/schema.md

  Co-authored-by: Copilot <175728472+Copilot@users.noreply.github.com>

  * Update notebooks/client_tutorial.ipynb

  * Update src/crosscontract/crossclient/crossclient.py

  ---------



## v0.1.1 (2026-02-12)



### Bug fixes


- **Constrains use objects instead of instances for default_factory** ([`c28204b`](https://github.com/sweet-cross/crosscontract/commit/c28204b40db50499551aae88471a0eba17178f1c))

  * updated dev docs

  * user generics for py3.11 compliance

  * no class attributes in default_factories

  * action optimization


### Chores


- **check pr on edit** ([`342f53d`](https://github.com/sweet-cross/crosscontract/commit/342f53d5650f989e91159bf8efd2f25ed49dfb2e))



## v0.1.0 (2026-02-12)

### Chores


- **fix semantic release config for zero version** ([`2b1acaa`](https://github.com/sweet-cross/crosscontract/commit/2b1acaa6e84d3c9f25dfb30c75db73ce0f143d26))

- **remove build command from semantic release config** ([`f3473cc`](https://github.com/sweet-cross/crosscontract/commit/f3473cc51ad46e0fcbcea159240f7d1987c38203))

- **move semantic_release config under correct section** ([`b35d5b2`](https://github.com/sweet-cross/crosscontract/commit/b35d5b2da8312b51ad53d84144d2eea42b4554f9))

- **reset version to 0.1.0** ([`8513f44`](https://github.com/sweet-cross/crosscontract/commit/8513f4454e58f75cdf6896c25aa288e3e5b51515))




### Bug fixes


- **contract route** ([`68c5c14`](https://github.com/sweet-cross/crosscontract/commit/68c5c1482150daa9e867002ab9e209bb17767c58))
