# Retire bespoke descriptors and wire the new public surface

## Context
**Part of PRD:** [2026-06-14-release-data-package-adapter.md](../../prds/2026-06-14-release-data-package-adapter.md)

ADR 0003 retires the parallel CROSS descriptor hierarchy. With the spec models and
adapter in place, delete the obsolete modules and expose the new public surface so
`from crosscontract.release import create_data_package, DataPackageSpec` works.

## Acceptance Criteria
- [ ] **Deleted source:** `data_resource.py`, `data_package.py`, `models_resource.py`,
      `models_package.py`, `release_specification.py` (all under
      `src/crosscontract/release/data_package/`).
- [ ] **Deleted obsolete tests:** `src/tests/release/data_package/test_data_resource.py`
      and `test_data_package.py` (they reference retired `CrossDataResource` /
      `CrossDataPackage`; fresh tests come in tasks 05/06).
- [ ] `src/crosscontract/release/data_package/__init__.py` exports `DataPackageSpec`,
      `DataResourceSpec`, `DataInstructions`, `create_data_package`; no longer exports
      `CrossDataResource` / `CrossDataPackage`.
- [ ] `src/crosscontract/release/__init__.py` mirrors that surface.
- [ ] No remaining references to the retired names anywhere in `src/` (grep clean).
- [ ] `ContractResource` and `CrossContract.to_server`/`from_server` are **untouched**.

## Implementation Details
- **Modify:** the two `__init__.py` files above.
- **Delete:** the five source modules + two obsolete test modules listed.
- Verify with `grep -rn "CrossDataResource\|CrossDataPackage\|CrossData.*ReleaseSpec\|CrossData.*MetaData" src/`
  returns nothing in the release path (curated `CrossMetaData` on the contract stays).
- Depends on **tasks 01–03** (replacements must exist before deletion).
