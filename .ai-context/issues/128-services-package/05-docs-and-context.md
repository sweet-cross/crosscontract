# Update docs, CLAUDE.md, CONTEXT.md and ADRs

## Context
**Part of PRD:** none. Source is GitHub issue #128 and the agreed design discussion.

The import paths in the docs and the architecture notes still name `registry/`, `submission/` and `release/`. They need to describe the new `services/` package and the `CrossReader` name.

## Acceptance Criteria
- [ ] `docs/reference/registry.md` and `docs/reference/release.md` point at `crosscontract.services.reader…` / `crosscontract.services.package_creator…`; the reference page lists `CrossReader`. The release specs are referenced from `crosscontract.contracts.release`.
- [ ] `docs/release/index.md` imports `create_data_package` from `crosscontract.services` and uses `CrossReader`; `docs/registry/index.md` and `docs/notebooks/registry_tutorial.ipynb` use `CrossReader`.
- [ ] `mkdocs.yml` navigation entry `CrossRegistry: reference/registry.md` is renamed to `CrossReader`.
- [ ] `.claude/CLAUDE.md`:
  - the architecture section describes `services/` with `reader/`, `submitter/`, `package_creator/`;
  - the import graph ends `… ← crossclient ← services`, and the rule becomes "never import `services/`";
  - a "two packages named `services`" note (`crossclient.services` = transport, `crosscontract.services` = high-level);
  - the four-`submission` note becomes three, and the two-`release` note is removed (only `contracts.release` remains).
- [ ] `.ai-context/CONTEXT.md`: **Registry** becomes **Reader**, with "Registry" under _Avoid_.
- [ ] A new ADR 0013 records the `services` package, the folder names, the `CrossReader` rename and the removed re-exports. Older ADRs (0003, 0007, 0010–0012) stay as historical records.
- [ ] `uv run mkdocs build` succeeds with no unresolved references.

## Implementation Details
- Depends on: 04.
