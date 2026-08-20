# Deprecate the construction-time `filters` argument on `CrossDataVariable`

## Summary
`CrossDataVariable` currently accepts `filters` both at construction (baked
server-side into the cached data on first fetch) and on every `get_data()` call
(applied client-side, on top of whatever construction-time filters already
narrowed the cache). The two compose by intersection but share one name, so the
scope a variable was constructed with is invisible at the `get_data()` call site
— and if the variable is later aggregated, the result looks like a legitimate
total while silently being a total over a slice. This PR deprecates the
construction-time argument with a `FutureWarning`, ahead of removing it once
usage outside this repo is confirmed clear.

## Changes
- `CrossDataVariable.__init__` now warns (`FutureWarning`) when `filters` is
  passed, explaining that it is applied once at fetch time and then cached, so
  it silently narrows every later `get_data()` call including aggregations.
  `from_client` and `CrossRegistry.add_variable` both delegate to `__init__`, so
  this single warning site covers all three public entry points without
  double-firing.
- `CrossRegistry.add_variable` now warns when `filters` is passed for a
  dimension contract, instead of silently discarding them as before (dimensions
  never supported filtering).
- Docstrings on `CrossDataVariable.__init__`, `from_client`, and `get_data`, and
  on `CrossRegistry.add_variable`, updated to mark `filters` deprecated and
  point at `get_data(filters=...)` as the one remaining filter surface.
- `CrossBaseVariable._fetch_data`'s docstring corrected — it claimed the base
  class filters data by construction-time filters, which it never did (only the
  `CrossDataVariable` subclass ever had that state).
- `.ai-context/TODO.md` links to the tracking issue for the follow-up removal.
- No behavior change for any caller that doesn't pass `filters`.

## Testing
Added/updated tests in `src/tests/registry/test_data_variable.py` and
`src/tests/registry/test_registry.py`:
- Existing tests that construct with `filters` now assert the `FutureWarning`
  (`pytest.warns`).
- New tests confirm the warning fires on `CrossDataVariable(filters=...)`,
  `CrossRegistry.add_variable(filters=...)` for both value variables and
  dimensions, and confirm no warning fires when `filters` is omitted.

## Notes for reviewer
- This is deprecation only — the argument still works exactly as before, just
  with a warning. The follow-up removal PR is tracked in a GitHub issue
  (transferred from a local `.ai-context/issues/` write-up) and is gated on
  confirming there are no external callers (e.g. `crossmcp`, `cross_back`,
  analysis notebooks).
- `FutureWarning` was chosen over `DeprecationWarning` because this repo's
  `pyproject.toml` sets `-W ignore::DeprecationWarning` for its own test suite,
  which would have made the deprecation invisible in-repo, and because
  `FutureWarning` displays by default in notebooks regardless of calling
  module — the expected audience for this API.
- Deliberately not fixed here: the construction-time `filters` value shape
  (`dict[str, Any]`, one value per column) doesn't match `get_data`'s
  (`dict[str, list[Any]]`), and a list value would be mis-encoded into the
  server query params. Left as-is since the whole argument is being removed
  rather than repaired.
