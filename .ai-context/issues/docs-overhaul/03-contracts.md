# WP3 — Contracts: pages, validation, tutorial, reference

## Context
**Part of PRD:** [docs-overhaul.md](../../prds/docs-overhaul.md) — WP3

The contracts section has errors: an import example that fails (`DataSource`), a wrong
empty-list rule, a constraint that does not exist (`enum` on datetime), a broken link, and
typos. It also leaves out most of what a schema carries and how validation behaves since
v0.22–v0.24. This task corrects the pages, adds the missing schema and validation content,
and fixes the docstrings the contracts reference page renders.

## Acceptance Criteria

**`docs/contracts/index.md`**
- [ ] The broken `(see contracts/custom_metadata.md)` link points to
      `metadata.md#custom-metadata`.
- [ ] The numbered list reads 1, 2 (it currently jumps from 1 to 3).
- [ ] The typos are fixed: "is build", "contact" → "contract", "this packages".
- [ ] `gdp_example.yaml` is linked as the example file for `CrossContract.from_file`.

**`docs/contracts/metadata.md`**
- [ ] `DataSource` is renamed to `Source` in the attribute table, the heading text, and
      the import example.
- [ ] The empty-list bullet says only `contributors` and `licenses` turn `[]` into `None`;
      an empty `sources` list is kept.
- [ ] The sentence announcing a planned DCAT adapter is removed.

**`docs/contracts/schema.md`**
- [ ] Field table: `DateTimeField` lists `minimum`/`maximum` only (no `enum`), and the page
      states that every field supports `required` and `unique`.
- [ ] Documents `primaryKey`, single or composite.
- [ ] Documents `foreignKeys`: references to other contracts, and self-references.
- [ ] Documents `fieldDescriptors`: value (`unit`), time (`frequency`), and location
      (`locationType`).

**Validation section** (in `schema.md`, or `docs/contracts/validation.md` if it outgrows
one screen)
- [ ] Explains `contract.validate_data` versus `tableschema.validate_dataframe` and when to
      use which.
- [ ] States that the primary key is always checked within the data.
- [ ] Explains the `check_existing_primary_key`, `check_existing_foreign_key`, and
      `check_dimension_granularity` flags, and that setting any of them requires a
      `resolver`.
- [ ] Explains `validate_references`.
- [ ] Shows how to read a `SchemaValidationError` with `to_list`, `to_pandas`, and
      `max_errors` (v0.24.0).

**`docs/contracts/contract_types.md`**
- [ ] The typos are fixed: "The however,", "The start nature" → "star".
- [ ] *FlexibleDimension* is described in its own bullet instead of being folded into the
      *Dimension* bullet.

**Contract tutorial (`notebooks/contract_tutorial.ipynb`)**
- [ ] No longer claims a valid frame gives "an empty response"; `validate_dataframe`
      returns the DataFrame.
- [ ] Shows `gdp_contract.validate_data(df)` as the contract-level entry point.
- [ ] Re-executed offline with outputs committed, and the markdown matches those outputs.

**Reference and docstrings**
- [ ] `docs/reference/contracts.md` renders `ContractResolver` and the field-descriptor
      models, each exactly once.
- [ ] The `BaseContract` and `CrossContract` docstrings state the `name` rule as enforced:
      lowercase letters, digits, `.`, `_`, `-`; at most 100 characters.
- [ ] The comment in the `BaseContract` example refers to `tableschema`, not `schema`.
- [ ] The `CrossContract` summary no longer says it adds "tagging capabilities".
- [ ] ADR 0002 refers to `Source` instead of `DataSource`. This is a name correction only.

**Checks**
- [ ] Every Python snippet on a touched page runs as written, in particular
      `from crosscontract.contracts.contracts.metadata_models import Contributor, Source, License`.
- [ ] `uv run mkdocs build` no longer shows the `custom_metadata.md` warning and shows no
      new ones. The existing test suite passes after the docstring edits. Run both only
      with the user's go-ahead.

## Implementation Details
- Files to modify:
  - `docs/contracts/index.md`
  - `docs/contracts/metadata.md`
  - `docs/contracts/schema.md`
  - `docs/contracts/contract_types.md`
  - `docs/reference/contracts.md`
  - `notebooks/contract_tutorial.ipynb` (edit the source in `notebooks/`, never the
    gitignored copy in `docs/notebooks/`)
  - `src/crosscontract/contracts/contracts/base_contract.py` (docstrings only)
  - `src/crosscontract/contracts/contracts/cross_contract.py` (docstrings only)
  - `.ai-context/adrs/0002-metadata-follows-frictionless-with-deviations.md`
- Possibly create `docs/contracts/validation.md`, and if so add it to the `mkdocs.yml` nav
  under CrossContract.
- Sources of truth:
  - `BaseContract.validate_data` in `base_contract.py` and `TableSchema.validate_dataframe`
    in `contracts/schema/schema.py`, for flag semantics.
  - `contracts/schema/field_descriptors/descriptors.py`, for the descriptor fields.
  - `contracts/schema/fields/*.py`, for the constraints.
  - `SchemaValidationError` in `contracts/schema/exceptions/validation_error.py` on `dev`,
    for `max_errors`.
- Use the terms defined in `.ai-context/CONTEXT.md`: resolver, existing values, opt-in key
  checks. Do not restate ADR rationale on the pages (ADRs 0001, 0005, 0006, 0008, 0009).
- ADR 0002: fix only the class name. Its DCAT sentence stays, as part of the record.
- Mkdocstrings: prefer public re-exports over private module paths, and do not render a
  module and a class re-exported from it on the same page.
- Documents `max_errors`, which is on `dev` only, so this WP must land on `dev`, not be
  cherry-picked to `main`.
- Dependencies: none. Branch off `dev`; PR title `docs: ...`.
