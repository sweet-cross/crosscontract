# Unit tests: specs + adapter helpers

## Context
**Part of PRD:** [2026-06-14-release-data-package-adapter.md](../../prds/2026-06-14-release-data-package-adapter.md)

Lock in the spec validation rules and the pure build helpers — especially the override
merge and the structural file-correctness guard — without touching the network.

## Acceptance Criteria
- [ ] `test_specs.py`: `name` optional + `CONTRACT_NAME_PATTERN` rejects `/`/uppercase;
      `format` Literal rejects unknown values (default `csv`); `resources` `min_length=1`;
      missing package `name`/`title`/`description` fails; `extra="allow"` carries unknown
      keys through.
- [ ] `test_create_data_package.py` (unit portion): `_override_metadata` — explicit field
      wins, unset optional inherits the contract (assert via `model_fields_set`), extra key
      appended.
- [ ] `_derive_path` csv/parquet mapping; `_profile_for` mapping.
- [ ] `_assemble_package` raises on duplicate resource names (edge 1); sets `created` when
      absent.
- [ ] All tests pass under `uv run pytest src/tests/release/data_package/`.

## Implementation Details
- **Create:** `src/tests/release/data_package/test_specs.py` and
  `src/tests/release/data_package/test_create_data_package.py` (unit classes here;
  integration in task 06).
- Reuse `CrossContractFactory` from `src/tests/conftest.py` to produce a `CrossContract`
  for the override/assembly helpers.
- No fake registry needed for this task — helpers are pure.
- Depends on **tasks 01–04** (public surface wired so imports resolve).
