# Adapter build helpers: metadata override, path/profile derivation, resource assembly

## Context
**Part of PRD:** [2026-06-14-release-data-package-adapter.md](../../prds/2026-06-14-release-data-package-adapter.md)

The pure, side-effect-free core of the adapter: turn a fetched contract + a
`DataResourceSpec` into a `_standards.frictionless.DataResource`, and assemble the
package descriptor. Isolating these keeps the file-correctness guard structural and
unit-testable without a server.

## Acceptance Criteria
- [ ] `_override_metadata(contract, spec)` overlays the spec's **explicitly set**
      fields onto the contract's descriptive metadata using `model_dump(exclude_unset=True)`
      (an unset optional must never clobber a contract default with `None`); extra keys
      are appended.
- [ ] `_derive_path(name, format)` returns `data/<name>.csv` or `data/<name>.parquet`.
- [ ] `_profile_for(format)` returns `tabular-data-resource` for csv, `data-resource`
      for parquet.
- [ ] `_build_resource(contract, spec, name)` returns a
      `_standards.frictionless.DataResource` with: overridden descriptive metadata,
      `schema` = `contract.tableschema` (trusted, as fetched), derived `path`/`profile`,
      `format`, `encoding="utf-8"`.
- [ ] `_assemble_package(spec, resources)` returns a
      `_standards.frictionless.DataPackage`, sets `created` to current UTC RFC3339 when
      absent, and raises `ValueError` on duplicate resource names.
- [ ] Helpers live in `create_data_package.py` (private, prefixed `_`).

## Implementation Details
- **Create:** `src/crosscontract/release/data_package/create_data_package.py` (helpers
  only in this task; the public function is task 03).
- Output types from `crosscontract._standards.frictionless` (`DataResource`,
  `DataPackage`). `name` resolution (default from contract) happens here: `name =
  spec.name or contract.name`.
- Schema embedding: read `variable.contract_resource.contract.tableschema` — do **not**
  call any `from_contract`. (The contract is already trusted via `from_server`.)
- Pure functions only — no I/O, no network. Depends on **task 01** (spec models).
