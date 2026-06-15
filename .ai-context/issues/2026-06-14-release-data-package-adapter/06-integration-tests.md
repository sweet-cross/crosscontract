# Integration tests: end-to-end create_data_package + Frictionless round-trip

## Context
**Part of PRD:** [2026-06-14-release-data-package-adapter.md](../../prds/2026-06-14-release-data-package-adapter.md)

Prove the adapter produces a valid, self-consistent zip from a faked fetch layer, and
that the emitted `datapackage.json` is Frictionless-valid — the correctness anchor for
the whole feature.

## Acceptance Criteria
- [ ] A **fake fetch layer** (stub `CrossRegistry.get_variable` / `CrossClient.contracts.get`)
      yields a known `CrossContract` + a small DataFrame; `filters`/`aggregation` from the
      `FetchSpecMixin` are asserted to reach `get_data` (`get_data_kwargs` plumbing).
- [ ] Produced zip contains `datapackage.json` (root) + `data/<name>.csv`; the data file
      content matches the fetched DataFrame.
- [ ] Resource `schema` in the descriptor equals the contract `tableschema`; resource
      metadata reflects spec overrides; `created` is set.
- [ ] **Round-trip:** `DataPackage.model_validate(json.loads(datapackage.json))` succeeds.
- [ ] A two-resource package builds; unique-name collision raises (edge 1); dimension
      resource with filters/aggregation raises (edge 4).
- [ ] `fn_out` suffix normalization/rejection (edge 10) and parent-dir creation (edge 8).
- [ ] A parquet resource is exercised, skipped via `pytest.importorskip("pyarrow")` if the
      engine is absent (edge 15).

## Implementation Details
- **Modify:** `src/tests/release/data_package/test_create_data_package.py` (add
  integration classes alongside the unit ones from task 05).
- Build the stub so no live platform is needed; assert zip contents with `zipfile.ZipFile`
  and `tmp_path` for `fn_out`.
- Use `CrossContractFactory` (`conftest.py`) for the contract; a `pandas.DataFrame`
  literal for the data.
- Depends on **tasks 03 and 04** (function + wired exports). Pairs with task 05's file.
