# feat!: add a required replace_key to SubmissionContract

## Summary

A Submission Contract can be shared by several teams, typically one per model, and the
backend cannot tell which team a user belongs to — the team has to be identified by the
data. `replace_key` declares the columns whose values identify a submitter's slice, so a
resubmission replaces exactly that slice in every target, including targets the new
bundle leaves empty. Inferring the previous submission from primary-key overlap fails
when keys change (a renamed scenario, say) and leaves stale rows behind. The replace
itself is performed by `cross_back`, which uses the key values to find the uuid of the
last submission; this package only declares the field and validates it.

Closes [#108](https://github.com/sweet-cross/crosscontract/issues/108).

## Changes

- **`SubmissionContract.replace_key: list[str] | Literal["all"]`**, required. A column
  list scopes the replace; `"all"` replaces everything previously submitted under the
  contract. The columns name the *target* contracts as they land after extraction, not
  the submission's own `tableschema`, since transformations may rename bundle columns.
- **`_validate_replace_key`** rejects an empty list and names any duplicated columns in
  the error.
- **`validate_references`** now also checks, for a column list, that every target's
  contract declares each column. Only presence is checked — see the note on the
  nullability hole below. Declaration failures join the existing unresolved-contract
  errors in the one aggregate exception; an unresolved contract is reported as unknown
  only, without the column check running against `None`.
- **`CrossSubmitter.validate_submission`** docstring updated: the pre-flight contract
  check now covers the replace key as well as resolution, and its `ValueError` says so.
- Test fixtures carrying a `SubmissionContract` updated for the now-required field, and
  `.ai-context/prds/cross2025_submission.yaml` given `replace_key: [model,
  scenario_group]` so the reference campaign file still validates.

## Testing

`TestReplaceKey` (9 tests, 13 cases) covers the field: both forms accepted, omission /
explicit `None` / empty list / duplicates / a bare column string rejected, and round
trips through `model_dump` and `to_server`/`from_server` for both forms.
`TestValidateReferencesReplaceKey` (8 tests) covers the target checks: the passing case,
`"all"` skipping the check, a missing column, a declared-but-optional column *accepted*,
every offending target reported, every offending column named, an unresolved contract
skipping the column check, and both error kinds in one exception.
`example_submission.yaml` carries the list form so the YAML/JSON round-trip tests
exercise the branch `"all"` does not.

## Notes for reviewer

- **The design deviates from the issue text.** The issue proposes
  `replace_key: list[str] | None = None`, with `None` meaning "replace everything this
  contract wrote". That was rejected: the destructive setting must not be reachable by
  omission. `[]` was rejected as the spelling for it on the same grounds — a falsy value
  that reads like "no key" to a human. Hence a required field with an explicit `"all"`.
  Append-only ("never replace") is deliberately not expressible; it is not a case the
  platform handles. The issue's acceptance criteria are therefore met in substance, not
  literally.
- **Breaking**: the field is required, so any code or YAML constructing a
  `SubmissionContract` must now supply it. No submission contracts exist server-side
  yet, so there is nothing to migrate. PR title must stay `feat!:` so
  python-semantic-release cuts the right bump.
- **Presence only, and the hole that leaves.** An earlier revision also required each
  key column to be declared `required` in the target contract. Dropped: it is a hard
  rule to impose on contract authors for a property only `cross_back` can say it needs,
  and it rejected the idiomatic shape where a key column is declared through the
  target's `primaryKey` without an explicit `constraints.required`. The cost is that an
  optional key column can arrive null — or be absent from the bundle altogether, since
  step 1 enforces presence only for required columns — so a submission can pass every
  check here while carrying nothing that identifies its slice. Closing that belongs at
  data-validation time (does the extracted frame actually carry the key values?), not in
  `validate_references`, which sees declarations only. Left open pending one answer from
  the `cross_back` side: whether the submission lookup compares key tuples null-safely.
  If it does not, a null key tuple makes a submission un-replaceable and its rows orphan.
- **No per-target opt-out.** A target whose contract legitimately has no team column —
  a shared dimension, say — makes the contract unauthorable under a scoped key. That is
  intended for now; a `Dimension` target will always fail a scoped key, since its
  template declares only `id`/`level`/`parent_id`/`label`/`description`.
- **Nothing stops a submitter putting another team's key value in their bundle** and so
  wiping that team's rows. That is authorization and belongs in `cross_back`, not here.
- One nit left deliberately: `_validate_replace_key` is named `_validate_*` where the
  other four validators in the file are `_check_*`.
- No docs changes: there is no submission docs page, and `docs/reference/` has no
  submission entry. `replace_key` should be covered when that page is written.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
