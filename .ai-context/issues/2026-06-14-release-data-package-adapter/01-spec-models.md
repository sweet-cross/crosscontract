# Spec models: DataResourceSpec, DataPackageSpec, DataInstructions

## Context
**Part of PRD:** [2026-06-14-release-data-package-adapter.md](../../prds/2026-06-14-release-data-package-adapter.md)

The Release adapter is driven by a declarative **Release spec**. This task defines
that recipe — the two Pydantic v2 models plus the data-instruction wrapper — so the
adapter (later tasks) has a typed input. No dependencies; this is the foundation.

## Acceptance Criteria
- [x] `DataInstructions` wraps `fetch: FetchSpecMixin` (carried over unchanged from the
      retired `release_specification.py`).
- [x] `DataResourceSpec` inherits from `_standards.frictionless.ResourceMetaData` with
      partial overrides: descriptive fields (`name`, `title`, `description`, `homepage`,
      `sources`, `licenses`) all optional; `name` validated by `CONTRACT_NAME_PATTERN`
      (rejects `/` and uppercase) and defaulting to the contract name is deferred to the
      adapter (the field itself is optional here).
- [x] `DataResourceSpec` adds `format: Literal["csv", "parquet"] = "csv"` and
      `data_instructions: DataInstructions`. `path`/`encoding`/`profile`/`schema` are
      **not** author-settable.
- [ ] `DataPackageSpec` inherits from `_standards.frictionless.PackageMetaData`:
      `name`/`title`/`description` required; `resources: list[DataResourceSpec]` with
      `min_length=1`.
- [ ] Both models keep `extra="allow"` so additional descriptive keys ride through.
- [ ] Models importable from `crosscontract.release.data_package.specs`.

## Implementation Details
- **Create:** `src/crosscontract/release/data_package/specs.py`.
- Reuse `FetchSpecMixin` from `crosscontract.transformations`; `CONTRACT_NAME_PATTERN`
  from `crosscontract.contracts.contracts.base_contract`; metadata bases from
  `crosscontract._standards.frictionless`.
- Pydantic v2, `ConfigDict(extra="allow", str_strip_whitespace=True)`. Relaxing an
  inherited required field to optional follows the existing pattern in the old
  `CrossDataResourceReleaseSpec` (`# type: ignore[assignment]`).
- Do **not** yet delete the old `release_specification.py` — that happens in task 04.
- No dependency on other tasks.
