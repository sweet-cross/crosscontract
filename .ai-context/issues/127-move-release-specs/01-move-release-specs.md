# WP1 — Move the release specs into `contracts/release/`

## Context
**Part of PRD:** none. Source is GitHub issue #127 plus the discuss-and-plan session of
2026-10-18. This is WP1.

`release/data_package/` holds both the release spec and its execution. cross_back needs to
parse and validate release specs without depending on the client-side execution, which
takes a `CrossRegistry`. This task moves only the spec into the declarative layer, the
same way #120 moved the submission specs. The execution stays where it is.

## Acceptance Criteria
- [ ] `src/crosscontract/contracts/release/release_specification.py` holds
      `DataInstructions`, `CrossDataResourceReleaseSpec` and `CrossDataPackageReleaseSpec`.
      Their content is unchanged apart from the relative imports.
- [ ] `src/crosscontract/release/data_package/release_specification.py` is deleted, with
      **no shim module** left behind.
- [ ] `crosscontract.contracts.release` exports all three classes.
- [ ] `crosscontract.contracts` exports `CrossDataPackageReleaseSpec` and
      `CrossDataResourceReleaseSpec`, but not `DataInstructions`.
- [ ] The top-level `crosscontract` exports both specs as well, imported through
      `.contracts`, the same way `SubmissionContract` is.
- [ ] `crosscontract.release` and `crosscontract.release.data_package` still export both
      specs and `create_data_package`.
- [ ] Nothing under `src/crosscontract/contracts/` imports `crossclient`, `registry` or
      `release`.
- [ ] `test_release_specification.py` lives in `src/tests/contracts/release/`, with an
      `__init__.py` matching the sibling test packages.
- [ ] `docs/reference/release.md` points at `crosscontract.contracts.release.DataInstructions`.
- [ ] The test suite and `uv run mkdocs build` pass. Run them only with the user's
      go-ahead.

## Implementation Details
- **Move** (prefer `git mv` to keep history):
  - `src/crosscontract/release/data_package/release_specification.py` →
    `src/crosscontract/contracts/release/release_specification.py`
  - `src/tests/release/data_package/test_release_specification.py` →
    `src/tests/contracts/release/test_release_specification.py`
- **Imports in the moved spec module.** Both
  `release/data_package/` and `contracts/release/` sit two levels below `crosscontract/`,
  so the `...` prefixes for
  `_helpers`, `_standards.frictionless`, `constants` and `transformations` stay the same.
  Check them anyway.
- **Create** `src/crosscontract/contracts/release/__init__.py`, which exports the three
  classes. Follow `contracts/submission/__init__.py`.
- **Modify:**
  - `src/crosscontract/contracts/__init__.py`: add the two specs to the imports and `__all__`.
  - `src/crosscontract/__init__.py`: add the two specs to the `.contracts` import and `__all__`.
  - `src/crosscontract/release/data_package/__init__.py`: import the specs from
    `...contracts.release`.
  - `src/crosscontract/release/data_package/create_data_package.py`,
    `_resolve_resource.py` and `_resolve_package.py`: replace
    `from .release_specification import ...` with `from ...contracts.release import ...`.
  - `src/tests/release/data_package/conftest.py` and `test_create_data_package.py`: import
    from `crosscontract.contracts.release`.
  - `docs/reference/release.md`: update the `DataInstructions` mkdocstrings path. The two
    specs can stay referenced as `crosscontract.release.*`.
- **Fixtures.** The moved test only uses `CrossDataPackageReleaseSpec.model_validate`
  directly. Check whether it relies on fixtures from
  `src/tests/release/data_package/conftest.py`. If it does, move or copy only the fixtures
  it uses.
- **Import graph.** `contracts` → `transformations` is already allowed
  (`constants, exceptions ← transformations ← contracts`), so no direction changes.
- **PR title.** Use `refactor!: move release specs into contracts/release`, because a
  public module path disappears.
- No behaviour changes and no new helpers.
