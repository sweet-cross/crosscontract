# Move `release/data_package/` to `services/package_creator/`

## Context
**Part of PRD:** none. Source is GitHub issue #128 and the agreed design discussion.

Data package creation joins the other high-level services. `create_data_package` stays a function for now (it may become a class later) and is not exported from the root. The top-level `crosscontract.release` package goes away, along with its re-exports of the release specs (they stay in `crosscontract.contracts.release`, `crosscontract.contracts` and the root).

## Acceptance Criteria
- [ ] `src/crosscontract/release/` no longer exists; `create_data_package.py`, `_resolve_resource.py` and `_resolve_package.py` live in `src/crosscontract/services/package_creator/`.
- [ ] `services/package_creator/__init__.py` exports only `create_data_package`.
- [ ] The modules import `CrossReader` and the variable classes from `..reader`; type hints and docstrings say `CrossReader`.
- [ ] `create_data_package` is not in the root `crosscontract.__all__`.
- [ ] No code or test imports `crosscontract.release` (`crosscontract.contracts.release` is unaffected).

## Implementation Details
- `git mv` the three modules, then delete `release/` and `release/data_package/`.
- The parameter keeps its name `registry` (only the type changes to `CrossReader`), so keyword callers don't break. Renaming it is not part of this task.
- Tests: move `src/tests/release/data_package/` (including `conftest.py` and `data-package.json`) to `src/tests/services/package_creator/`; update the import paths and the `MODULE = "crosscontract.release.data_package.create_data_package"` patch target in `test_create_data_package.py`.
- `src/tests/contracts/release/test_release_specification.py:46-47` (`test_specs_reexported`) loops over `crosscontract.release` and `crosscontract.release.data_package`; drop those two from the loop.
- Depends on: 01 (imports `CrossReader`).
