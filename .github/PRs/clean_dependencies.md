# fix: declare pyyaml and drop ruff, pre-commit and jsonschema from runtime dependencies

## Summary
`ruff` and `pre-commit` were listed as runtime dependencies, so every user install pulled in the dev tooling. This branch moves them to the `dev` group. That change exposed a hidden bug: `crosscontract._helpers._io` imports `yaml`, but `pyyaml` was never declared. Users only had it because `pre-commit` depends on it. `pyyaml` is now a runtime dependency. `jsonschema` is removed as well: nothing in `src/` has imported it since #68, yet every install pulled it in along with `attrs`, `referencing`, `rpds-py` and `jsonschema-specifications`. Anyone who relied on `crosscontract` to install `ruff`, `pre-commit` or `jsonschema` must now install them directly. CI also changes so that the test jobs install the package the way a user would, which means a missing runtime dependency fails the tests instead of being covered up.

## Changes
- **Runtime dependencies**
  - Removed `ruff`, `pre-commit` and `jsonschema`.
  - Added `pyyaml>=6.0.3`.
- **Dependency groups**
  - New `test` group: `pytest`, `respx`, `polyfactory`, `coverage`.
  - `dev` includes `test` via `{include-group = "test"}` and now also holds `ruff` and `pre-commit`, so `uv sync --group dev` installs the same set as before.
- **CI test matrix** (`test_and_coverage.yml`)
  - Each Python version gets a fresh venv and runs `uv pip install -e . --group test`. This resolves from `pyproject.toml` instead of `uv.lock`, and installs no dev tooling that could supply a missing runtime dependency.
  - Both `uv run` calls use `--no-sync`, so they don't sync the venv back to the lock.
- **Lowest-versions script** (`scripts/test_lowest_versions.sh`): installs `--group test` instead of `--group dev`, for the same reason.
- **`uv.lock`**: regenerated. `jsonschema` stays in the lock because the `dev` group's Jupyter packages depend on it.

## Testing
- Locally, a fresh Python 3.11 venv with `uv pip install -e . --group test` installed 39 packages and ran the full suite: 1179 passed. The install resolved newer versions than the lock has (e.g. pandera 0.34.1, sqlalchemy 2.1.4, pyarrow 26), so it really did ignore the lock. This run predates the `jsonschema` removal.
- Not run: the updated CI workflow and `scripts/test_lowest_versions.sh`.

## Notes for reviewer
- The `pre-commit` job still uses `uv sync`. It's now the only CI job that runs against `uv.lock`.
- `pythonpath = "src"` means tests import the source tree, not an installed wheel. CI now checks the declared dependencies, not what the built wheel contains.
- Follow-ups not done here:
  - `numpy` is imported directly but only comes in through pandas.
  - The header comment in `test_and_coverage.yml` still says "Python 3.12 and 3.13", but the matrix runs 3.11 to 3.15.
