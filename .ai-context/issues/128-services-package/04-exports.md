# Wire up `services/__init__.py` and the root exports

## Context
**Part of PRD:** none. Source is GitHub issue #128 and the agreed design discussion.

Once the three subpackages exist, `crosscontract.services` becomes their single entry point and the root imports from it. `CrossReader` becomes a public root name.

## Acceptance Criteria
- [ ] `crosscontract.services` exports `CrossReader`, `CrossRegistry`, `CrossSubmitter` and `create_data_package`.
- [ ] The root `crosscontract.__all__` gains `CrossReader`; everything it exported before is still exported; `create_data_package` is not added.
- [ ] `from crosscontract import CrossReader, CrossRegistry, CrossSubmitter` works.
- [ ] Nothing outside `services/` imports from `services/` except the root `__init__.py`.

## Implementation Details
- `src/crosscontract/services/__init__.py`: import from `.reader`, `.submitter` and `.package_creator`.
- `src/crosscontract/__init__.py`: import the role classes from `.services`, keep the other names from their home packages (see task 02).
- Add a test that `CrossReader` is exported from the root and from `crosscontract.services`.
- Depends on: 01, 02, 03.
