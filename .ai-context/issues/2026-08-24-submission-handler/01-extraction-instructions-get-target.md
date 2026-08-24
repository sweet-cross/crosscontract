# WP1 — `ExtractionInstructions.get_target`

## Context

The **Submission handler** (WP2, WP3) resolves a target by name on every call. The lookup
belongs on
[extraction_instruction.py](../../../src/crosscontract/submission/extraction/extraction_instruction.py)
rather than on the handler or on `SubmissionContract`, because that is the model that
owns `targets`: the accessor sits next to its data, and the handler stays free of spec
navigation.

`_check_name_unique` already guarantees target names are unique across the instructions,
so the lookup is unambiguous and needs no tie-breaking.

Note the resulting name collision is deliberate and accepted:
`ExtractionInstructions.get_target` returns a `Target` (a spec), while
`SubmissionHandler.get_target_data` returns a `pd.DataFrame`. The two live on a spec
model and an executor respectively and the suffix distinguishes them.

## Acceptance Criteria

- [x] `ExtractionInstructions.get_target(name)` returns the `Target` carrying that name.
- [x] An unknown name raises — see the open decision below.
- [x] No caching, no precomputed index. There are ~24 targets in the reference spec; a
      linear scan is not worth an accessor's worth of state.

## Implementation Details

**Modify:**

- `src/crosscontract/submission/extraction/extraction_instruction.py`
- `src/tests/submission/extraction/test_extraction_instructions.py`

### Decision required: what an unknown name raises

- **(a) — recommended.** A `KeyError` (or `ValueError`) whose message names the valid
  targets. Callers loop over names they typed by hand or read from another spec, so the
  valid set is the thing they need to see.
- **(b)** A bare `KeyError` from a dict lookup. Cheapest, and consistent with mapping
  semantics, but unhelpful in the loop this will actually sit in.

Whichever is chosen, it must be a *raise*, not a `None` return — the handler methods
would otherwise fail later with an unrelated pandas error.

**Dependencies:** none. First in the sequence because WP2 and WP3 both call it.

**Verification:** `uv run pytest src/tests/submission/`. A hit, a miss, and a lookup
against a fixture shaped like the cross2025 spec (several targets, some deriving their
`filters` from `name`). *Ask before running — see CLAUDE.md.*
