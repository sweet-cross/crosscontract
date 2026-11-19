---
paths:
  - "src/tests/**/*.py"
  - "**/conftest.py"
  - "**/test_*.py"
---

# Test conventions (pytest)

What a test verifies:

- Tests verify behavior through the public interface at a seam. Mock only what lies
  across the seam; where this file has rules per layer, they say what that is. A test
  that breaks on a refactor that kept the behavior is coupled to the implementation.
- Observe results through the interface. Read state directly (e.g. querying the
  database) only when the interface cannot show the effect: a write without a read
  endpoint, or checking that a rejected call changed nothing.
- Test a private helper directly only when it holds logic too intricate to cover
  through its caller (parsers, validators); otherwise cover it through the caller.
- Expected values come from an independent source of truth: a known-good literal, a
  worked example, the spec. Never recompute them the way the code does
  (`assert add(a, b) == a + b`); such a test passes by construction.
- A test's name states the behavior it specifies, so the test list reads as a spec of
  the unit.

Tests follow the code and docstring conventions in `python.md`, except:

- A test's docstring is a one-line summary of what it verifies; no `Args:` for its
  fixture parameters.
- Fixtures get a full docstring with `Returns:` or `Yields:` describing what they
  provide.
- Test classes (`class TestX:`) need no docstring; the class name states the unit or
  behavior under test.

Structure and mocking:

- Group tests in classes (`class TestX:`) by the unit or behavior under test.
- Use `pytest.mark.parametrize` for related cases instead of duplicated test
  functions; cover the meaningful cases, not every possible one.
- Share setup through reusable fixtures where it pays off. Fixtures that create data
  must clean it up even when the test fails (yield-fixture teardown).
- Mock collaborators with `spec=` (e.g. `AsyncMock(spec=<Class>)`), and use real pure
  functions; replace one only when the test must control its result.

Where tests go and what they assert:

- Tests live in `src/tests`, mirroring the structure of `src/crosscontract`.
- Do not assert the same behavior at several layers. Test each behavior where it is
  decided; when a function becomes a pass-through, delete its tests rather than
  re-mocking them.
- Put each assertion where it can fail: a claim that depends on a real system (e.g.
  that a query actually filters rows) belongs in an integration test, not in a test
  where that system is mocked.
- Mock HTTP calls to the CROSS platform with `respx`. Where hand-built test data gets
  repetitive, offer the user to use `polyfactory`; don't introduce it unasked.
