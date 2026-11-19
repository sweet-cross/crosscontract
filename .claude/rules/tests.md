---
paths:
  - "src/tests/**/*.py"
  - "**/conftest.py"
  - "**/test_*.py"
---

# Test conventions (pytest)

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
