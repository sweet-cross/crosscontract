# fix!: reject primary and foreign keys on submission contracts

## Summary

`CrossSubmitter.validate_submission` forwarded `check_existing_primary_key` to step 1,
where the bundle is validated against the submission contract's own schema. With a
primary key declared on that schema, `BaseContract.validate_data` fired
`_get_existing_values(resolver, self.name, ...)` — a `get_data` read against the
submission contract itself. A submission contract is instructions, not a table: nothing
is stored under its name, so the read fails with a `CrossClientError` instead of
producing a validation verdict. A self-referencing foreign key hit the same path via
`fk.reference.resource or self.name`.

Rather than special-casing the call site, this rejects the declarations at construction:
a `SubmissionContract`'s `tableschema` may declare neither `primaryKey` nor
`foreignKeys`. Both lookups in `validate_data` are already guarded on the (now always
empty) declaration, so `CrossSubmitter` needs no change — it keeps forwarding both flags
verbatim and they are simply inert for step 1.

**Breaking:** existing submission contracts declaring either key no longer construct.

## Changes

- **`SubmissionContract` gains two `mode="after"` validators** — `_check_no_primary_key`
  and `_check_no_foreign_keys` — alongside the existing `_check_routing_column` and
  `_check_filters`.
- **Docstrings corrected where the change made them false.**
  `validate_submission`'s two flag parameters claimed to cover "the submission contract
  in step 1, each target's contract in step 3"; they now apply to step 3 only. Its
  summary claimed "every step is checked against the platform" — step 1 no longer
  reaches it at all (and step 2 never did). `SubmissionContract`'s `tableschema`
  attribute states the restriction and where keys belong instead.
- **Both submission YAMLs stripped of their keys** — the test fixture
  `src/tests/submission/example_submission.yaml` (a 6-column composite primary key) and
  the reference campaign file `.ai-context/prds/cross2025_submission.yaml` (a 10-column
  primary key plus three foreign keys into dimensions).
- **Docs.** ADR 0004 amended, CONTEXT.md updated in three places (the **Submission
  contract** entry, **Submission validation**, and the summary bullet), and the
  `submission/` section of `CLAUDE.md`.

## Testing

Two cases added to `TestSubmissionContract`, following the file's existing shape —
`deepcopy(valid_data)`, inject the offending key, assert on a fragment of the validator's
message. The foreign-key case uses an *external* reference (`dim_variable`) rather than a
self-reference, since an external FK is the case that was previously legal and sensible,
and so is the behaviour this PR actually removes. Both use a field that exists in the
schema, so `ForeignKey`'s own validators cannot reject the input first and make the test
pass for the wrong reason.

**The suite is green on this branch.** The fixture edit is what unblocks it:
`example_submission.yaml` is loaded by `TestRoundTrip` in `test_submission_contract.py`,
which would otherwise fail at contract construction. The remaining submission tests build
their contracts from inline dicts that declare no keys, so nothing else needed changing —
including `test_submitter.py`'s assertions that both flags reach both steps with their
values intact, since the submitter still forwards them untouched.

## Notes for reviewer

- **The commit title must stay `fix!:` / `feat!:`.** It becomes the squash message PSR
  analyses on `dev`, and a plain `fix:` would ship a construction-time failure as a patch
  bump to anyone holding a submission YAML with keys.
- **What is given up, deliberately.** A bundle primary key expressed something real —
  each delivered row is a distinct observation. That is now the target contracts'
  business: because the routing column is itself part of any identifying key, duplicated
  rows always land in the same target and are caught by that contract's own primary key —
  but only if it declares one, and only if the caller left `check_existing_primary_key`
  on. A caller passing `False` now has no duplicate detection anywhere in the pipeline.
  Stated in the docstring and in ADR 0004 rather than left to be discovered.
- **Field-level constraints are untouched, `unique` included.** They are frame-local and
  never reach the platform, so they cannot reproduce the failure. External foreign keys
  *are* rejected even though they resolve to contracts that exist and the read would have
  worked — the same reference is declared by the target contract that owns the column,
  and a second copy on the bundle only invites drift.
- **ADR 0004's inheritance bullet lost its stated rationale.** `SubmissionContract`
  inherits `CrossContract` "for `validate_references`'s star-schema default, which is
  correct here since a bundle's foreign keys all point at dimensions" — with no foreign
  keys, `validate_references` has nothing to validate. The decision still stands on the
  bullet's second half (the contract stays usable wherever a `CrossContract` is
  accepted); the amendment withdraws the first half explicitly rather than deleting it.
  Worth checking that reads the way you want, since it is the one place the change
  reaches beyond `submission/`.
- **Two validators where one would do.** Pydantic stops at the first raising
  `mode="after"` validator, so splitting buys no extra reporting over one validator with
  two branches — it buys symmetry with `_check_routing_column` / `_check_filters`. Left
  as two deliberately; say so if you read them as one rule.
- **Error message wording.** Both messages say the keys "belong to the contracts the
  targets name", matching the `tableschema` attribute docstring. Deliberately not
  "enforced at the target level": a bundle's key is not *relocated* — the target
  contracts declare their own, which may not cover the same columns — and the stronger
  phrasing reads as a promise that a 6-column bundle key is still checked somewhere.
- **Not done here:** the same `fk.reference.resource or self.name` sharp edge still
  exists on non-submission contracts, where a self-referencing foreign key is legal. No
  longer reachable through this path. No TODO entry added, by request.
