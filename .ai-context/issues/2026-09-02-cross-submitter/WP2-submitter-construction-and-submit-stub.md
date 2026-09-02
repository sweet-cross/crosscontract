# WP2 — `CrossSubmitter`: construction, resolver, `submit` stub

## Context
**Part of PRD:** [2026-09-02-cross-submitter.md](../../prds/2026-09-02-cross-submitter.md)

`CrossSubmitter` is the **Data provider**'s entry point — the provider-side mirror of
`CrossRegistry` ([ADR 0007](../../adrs/0007-the-submitter-is-the-provider-side-mirror-of-the-registry.md)).
This package brings the class into existence with everything except the validation
sequence: the connection it owns, the resolver it builds, and the honest stub for the
submission it cannot yet perform. WP3 adds `validate_submission` on top.

## Acceptance Criteria
- [ ] `src/crosscontract/submission/submitter.py` defines `CrossSubmitter`.
- [ ] `__init__(username=None, password=None, client=None)` — mirrors
      `CrossRegistry.__init__`: uses `client` when given, otherwise builds
      `CrossClient(username=..., password=...)`, and raises `ValueError` when neither is
      complete. **No `base_url` parameter.**
- [ ] It holds `self._resolver = CrossContractResolver(client.contracts)` — private, and
      **not** a constructor parameter.
- [ ] No `close()`, no `__enter__` / `__exit__` (matches `CrossRegistry`; `CrossClient`
      registers its own `atexit` cleanup, and the submitter must never close a client it
      was handed).
- [ ] `submit(contract, df) -> None` raises `NotImplementedError` whose message names the
      reason: the CROSS platform does not yet expose the submission endpoint. Minimal
      signature — no validation flags.
- [ ] Class docstring states what it is (provider-side mirror of the registry), that it
      performs no validation itself, and that a client-side validation is advisory
      because the platform re-validates on ingest (per ADR 0005).
- [ ] Tests in `src/tests/submission/test_submitter.py`: credentials build a client
      (patching `crosscontract.crossclient.crossclient.CrossClient.authenticate`, as
      `src/tests/crossclient/conftest.py` does); `client=` is used as given; neither
      raises `ValueError`; `_resolver` is a `CrossContractResolver` over
      `client.contracts`; the class exposes no `close` / `__enter__`.

## Implementation Details

**Create:** `src/crosscontract/submission/submitter.py`
**Create:** `src/tests/submission/test_submitter.py`

- Depends on **WP1** only for the eventual import in WP3; this package needs nothing from
  it and can proceed in parallel.
- `__init__` is the `CrossRegistry.__init__` branch copied verbatim
  (`src/crosscontract/registry/registry.py`) plus the resolver line. Copy it rather than
  paraphrasing — the two constructors reading identically is the point.
- Import `CrossClient` and `CrossContractResolver` from `crosscontract.crossclient`. This
  makes `submission/` the one domain package importing the client layer; ADR 0007 records
  that trade-off, so no comment apologising for it in the code.
- **Do not** construct or hold a `SubmissionHandler` here — the submitter is stateless
  across calls and WP3 builds one per call.
- Slim class per CLAUDE.md house style: no helpers, no module constants, no defensive
  branches beyond the one `ValueError`.
- The `no close/__enter__` test is deliberate — it guards against a well-meaning future
  addition, so write it as an assertion with a comment saying so.
- Per CLAUDE.md, do not run `pytest` / `ruff` / `mypy` on your own initiative — ask first.
