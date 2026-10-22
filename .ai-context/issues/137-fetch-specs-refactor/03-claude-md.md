# WP3 — CLAUDE.md describes `contracts/fetching/` and `transformations/`

## Context
**Part of:** GitHub issue #137 (no PRD) — WP3

CLAUDE.md is the architecture reference for the package. After WP1 and WP2 it must
describe the new homes and the layout rule: `contracts/` holds specs, `handlers/` runs
them, `transformations/` holds self-running DataFrame operations.

## Acceptance Criteria
- [ ] A `**contracts/fetching/**` subsection under `contracts/` describes `FetchSpec`
      (contract, format, filters, aggregation, `get_data_kwargs`) and the aggregation
      forms (`AggregationSpec`, `ColumnAggregation`, `LevelKeepSpec`), and that it is
      exported from `crosscontract.contracts.fetching` only.
- [ ] A `### transformations/` section: each transformation is a spec whose `apply()`
      runs it, schema-agnostic; specs in `contracts/` compose them, `handlers/` runs them.
- [ ] The section states the one exception to "specs don't run themselves" outside
      `transformations/`: `FetchSpec.get_data_kwargs` translates the spec into
      `CrossDataVariable.get_data` arguments.
- [ ] The `contracts/release/` and `services/package_creator/` entries say `FetchSpec`
      (not `FetchSpecMixin`) and point to `contracts/fetching/`.
- [ ] The import-graph paragraph reads correctly with the new layout (the order
      `transformations ← contracts` is unchanged).
- [ ] `grep -n "FetchSpecMixin\|transformations/fetch\|transformation/" CLAUDE.md`
      finds nothing.

## Implementation Details
- File: `CLAUDE.md` (repo root).
- Match the existing entries' style: bold path, dash bullets, one line per module.
- Describe what the code does, not why it moved (rationale stays in the PR and issue).
- Dependencies: after `01-fetch-specs-to-contracts-fetching.md` and
  `02-flatten-transformations.md`.
