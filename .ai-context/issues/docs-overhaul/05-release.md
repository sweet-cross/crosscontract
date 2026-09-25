# WP5 — Release: own nav section, fetch and aggregation reference

## Context
**Part of PRD:** [docs-overhaul.md](../../prds/docs-overhaul.md) — WP5

Release is a separate layer from the Registry, but its page sits under CrossRegistry in
the nav. The fetch and aggregation models its spec accepts are not documented anywhere.
The page content itself is mostly accurate. This task gives Release its own section,
documents the fetch models, and re-checks the page against the code.

## Acceptance Criteria
- [ ] `mkdocs.yml` nav has a top-level "Release" entry with the overview. "Releasing data"
      is removed from under CrossRegistry.
- [ ] `FetchSpecMixin`, `AggregationSpec`, `LevelKeepSpec`, and `ColumnAggregation` are
      rendered in the API reference, each once, via their public re-exports from
      `crosscontract.transformations`.
- [ ] `docs/release/index.md` links to those models where it now says "see the registry
      tutorial".
- [ ] Every YAML key in the example spec in `docs/release/index.md` is accepted by
      `CrossDataPackageReleaseSpec` on `dev`. Verify by loading the example with the spec
      model.
- [ ] The "taken from the contract vs. the specification" table matches
      `build_data_resource` in `_resolve_resource.py`.
- [ ] `uv run mkdocs build` introduces no new warnings (run only with the user's
      go-ahead).

## Implementation Details
- Files to modify:
  - `mkdocs.yml` (nav)
  - `docs/release/index.md`
  - `docs/reference/release.md`
- **Create `docs/reference/transformations.md`** with the fetch and aggregation models,
  and add it to the API Reference nav. WP6 adds the column transformations to this same
  page, so title it for transformations as a whole, not only fetch.
- Sources of truth:
  - `release/data_package/release_specification.py`
  - `release/data_package/_resolve_resource.py`
  - `transformations/fetch/fetch_spec.py`
  - `transformations/fetch/aggregation_spec.py`
- ADR 0003: document `create_data_package` and the two spec models as the whole public
  surface. There are no descriptor classes to document.
- `mkdocs.yml` is also touched by WP1 and WP6. Conflicts are small and textual; rebase if
  another WP lands first.
- Dependencies: none. Branch off `dev`; PR title `docs: ...`.
