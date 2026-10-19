# refactor!: move registry, submitter and data package creation into crosscontract.services

## Summary
The high-level layer, meaning the entry points a user calls to work with the CROSS platform, was spread over three top-level packages: `registry/`, `submission/` and `release/`. This branch moves them into one package, `crosscontract/services/`, with one subpackage per job: `reader/`, `submitter/` and `package_creator/`. It also introduces `CrossReader` as the new name of `CrossRegistry`, which stays available as a subclass. Closes #128.

## Changes
- **New `crosscontract/services/` package**
  - `registry/` → `services/reader/`. `registry.py` becomes `reader.py`; the `variables/` subfolder moves with it.
  - `submission/submitter.py` → `services/submitter/`.
  - `release/data_package/` → `services/package_creator/`.
  - `services/__init__.py` exports `CrossReader`, `CrossRegistry`, `CrossSubmitter` and `create_data_package`. Each subpackage exports only its own names.
- **`CrossReader`**
  - The implementation class is renamed `CrossRegistry` → `CrossReader`. `class CrossRegistry(CrossReader)` remains as a plain subclass, with no warning yet; that comes in #132.
  - User-facing docstrings and warning/error messages now say "reader" instead of "registry", e.g. the `filters` deprecation hint now reads `reader['…'].get_data(...)`.
  - `create_data_package` and the `_resolve_resource` helpers are typed `CrossReader`. The parameter keeps its name `registry`, so keyword callers don't break.
- **Imports no longer go through the package root.** `reader.py`, `base_variable.py` and `data_variable.py` imported `CrossClient` via `from crosscontract import CrossClient`; they now import it from `crosscontract.crossclient`.
- **Exports**
  - Removed with no shims: `crosscontract.registry`, `crosscontract.submission` (including its re-exports of `SubmissionContract`, `SubmissionHandler`, the Excel readers and the exceptions) and `crosscontract.release` (including its re-exports of the release specs).
  - The root keeps every name it exported before, now importing each from its home package, and adds `CrossReader`.
  - `create_data_package` is deliberately not exported from the root. Import it from `crosscontract.services`.
- **Docs**
  - The API reference and guides use `crosscontract.services.*` and `CrossReader`. The mkdocs navigation says `CrossReader`.
  - The registry tutorial notebook (`notebooks/registry_tutorial.ipynb`) uses `CrossReader` / `my_reader`. Only cell sources changed; outputs are not re-run.
  - New section in `docs/client/index.md` on validating a bundle against a local `SubmissionContract`. This guidance was only in the removed `crosscontract.submission` docstring.
- **Context**
  - CLAUDE.md describes `services/`. The import graph now ends `… ← crossclient ← services`, and the naming notes now cover three `submission` packages and two `services` packages; the `release` note is gone.
  - CONTEXT.md renames the domain term **Registry** → **Reader**.
  - New ADR 0013 records the decision and the rejected names.

## Testing
- Tests moved to `src/tests/services/{reader,submitter,package_creator}/`. Only import paths and mock targets changed. The three new test folders got `__init__.py` files, matching the other test folders.
- Tests that checked the removed re-exports were deleted or now point at the root.
- New tests: `test_registry_is_a_reader`, which checks `CrossRegistry` is a `CrossReader`, and `src/tests/services/test_exports.py`. The latter checks that `CrossReader` is exported from the root and that `create_data_package` is in `services` but not in the root.
- Full test suite, ruff, mypy and the docs build pass locally.

## Notes for reviewer
- **Breaking change for deep imports.** Anyone importing from `crosscontract.registry`, `crosscontract.submission` or `crosscontract.release` must switch to `crosscontract.services` or the root. Nothing changes for root imports.
- **Name clash with `crosscontract.crossclient.services`.** That package is the transport layer, which users reach as `client.contracts` / `client.submissions`, not by import path. The clash is documented in CLAUDE.md.
- **Tests still use `CrossRegistry`.** Switching them to `CrossReader`, adding the `FutureWarning`, and possibly renaming the `registry` parameter of `create_data_package` happen in #132.
- **Older ADRs** (0003, 0007, 0010–0012) keep the old paths as historical records. ADR 0013 notes the move.
- **Planning files:** `.ai-context/issues/128-services-package/04-exports.md` and `05-docs-and-context.md` are still on the branch. Tasks 01–03 were already removed from it.
