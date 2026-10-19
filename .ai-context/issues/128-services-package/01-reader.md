# Move `registry/` to `services/reader/` and introduce `CrossReader`

## Context
**Part of PRD:** none. Source is GitHub issue #128 and the agreed design discussion (summarized in this folder's task set).

The high-level, platform-facing layer moves into one top-level package, `crosscontract/services/`. The registry is the first and riskiest move, because `registry.py` imports `CrossClient` through the package root, and the class gets its new name `CrossReader`. `CrossRegistry` stays as a plain subclass. Its deprecation warning is a separate issue (#132).

## Acceptance Criteria
- [ ] `src/crosscontract/registry/` no longer exists; its content lives in `src/crosscontract/services/reader/` (including `variables/`).
- [ ] The implementation class is `CrossReader`; `class CrossRegistry(CrossReader): pass` exists next to it, with a docstring saying it is the former name of `CrossReader`. No warning.
- [ ] `isinstance(CrossRegistry(...), CrossReader)` holds.
- [ ] `services/reader/__init__.py` exports `CrossReader`, `CrossRegistry` and the five variable classes.
- [ ] The reader no longer imports through the package root: `from crosscontract import CrossClient` becomes an import from `crosscontract.crossclient`.
- [ ] Tests move from `src/tests/registry/` to `src/tests/services/reader/` with only import-path changes; they keep using `CrossRegistry` (switching them is #132).

## Implementation Details
- `git mv src/crosscontract/registry src/crosscontract/services/reader`; the module `registry.py` becomes `reader.py`.
- Create `src/crosscontract/services/__init__.py` (it is filled in task 04; a minimal one is enough here).
- Fix `src/crosscontract/registry/registry.py:6` (`from crosscontract import CrossClient`).
- `src/tests/registry/test_registry.py:189` patches `"crosscontract.registry.registry.CrossClient"`; the patch target becomes `"crosscontract.services.reader.reader.CrossClient"`.
- Docstrings: the class docstring describes `CrossReader`. No ADR or issue references in docstrings.
- Until task 04, the root `__init__.py` has to import `CrossRegistry` from the new path so that `import crosscontract` still works.
- Depends on: nothing.
