# WP6 — Submission: new section, contract-type entry, transformation reference

## Context
**Part of PRD:** [docs-overhaul.md](../../prds/docs-overhaul.md) — WP6

`SubmissionContract`, `SubmissionHandler`, `CrossSubmitter`, `TargetValidationError`, and
`UnclaimedRowsError` are exported from the top-level package but have no docs page. This
task writes the data-provider documentation for submission.

**Deferred.** Start only once the submission feature has settled: at least
`CrossSubmitter.submit` no longer a stub, and the extraction format no longer changing
between PRs. Re-read `submission/` on `dev` before starting, because details below may
have moved.

## Acceptance Criteria

**`docs/submission/index.md`** (new, written for data providers)
- [ ] What a submission bundle and a `SubmissionContract` are.
- [ ] The `extraction` block: routing column, transformation profiles, and targets.
- [ ] Offline checking with `SubmissionHandler`: target extraction,
      `validate_target`/`validate_targets`, and `unclaimed_rows`.
- [ ] Platform checking and submitting with `CrossSubmitter.validate_submission(name, df)`
      and `submit(name, df)`, and the `SubmissionContractResource` methods underneath
      (`client.submissions.get(name)`).
- [ ] The errors a provider meets: `TargetValidationError` and `UnclaimedRowsError`.
- [ ] A complete, runnable example: a small submission contract as YAML plus a bundle
      DataFrame.

**`docs/contracts/contract_types.md`**
- [ ] A *Submission contracts* section: the `tableschema` declares neither `primaryKey` nor
      `foreignKeys`; `project_name` and `extraction` are required; the routing column must
      be a required string field.

**Reference**
- [ ] `docs/reference/submission.md` renders `SubmissionContract`, `SubmissionHandler`,
      `CrossSubmitter`, the extraction models (`ExtractionInstructions`, `Target`), and the
      two exceptions, each once.
- [ ] `docs/reference/transformations.md` also renders `CastColumn`, `DropColumns`,
      `DropRowsByValue`, `MapColumnValues`, `ParseDatetimeColumn`, and `RenameColumns`.

**Navigation and landing page**
- [ ] `mkdocs.yml` nav has a top-level "Submission" entry and an API Reference entry for
      it.
- [ ] `docs/index.md` lists Submission as a component, linked to the new page.

**Checks**
- [ ] Every snippet runs as written against `dev`.
- [ ] `uv run mkdocs build` introduces no new warnings (run only with the user's
      go-ahead).

## Implementation Details
- Files to create:
  - `docs/submission/index.md`
  - `docs/reference/submission.md`
- Files to modify:
  - `mkdocs.yml` (nav)
  - `docs/contracts/contract_types.md`
  - `docs/index.md`
  - `docs/reference/transformations.md`
- Sources of truth:
  - `contracts/submission/submission_contract.py`
  - `contracts/submission/extraction/`
  - `handlers/submission/submission_handler.py`
  - `handlers/submission/excel_processing.py`
  - `crossclient/services/submission/` (`SubmissionContractResource`, `Submission`)
  - `submission/submitter.py`
  - `exceptions/submission_exceptions.py`
  - `transformations/transformation/`
  - `.ai-context/prds/cross2025_submission.yaml`, as a real-world example to draw from
    (simplify it; don't publish it verbatim).
- ADR 0004 and ADR 0007: present the contract and its `extraction` block as one authored
  YAML, and `CrossSubmitter` as the provider-side counterpart of `CrossRegistry`. Use the
  *Submission and extraction* terms from `.ai-context/CONTEXT.md` (routing column,
  target, unclaimed rows, submission validation). Do not restate ADR rationale on the
  page.
- **Note — package architecture (added 2026-10-12).** #120–#122 change the layout this
  task documents:
  - Specs: `SubmissionContract` and the extraction specs move to `contracts/submission/`,
    and the Excel specs and reader move to `transformations/excel/` (#120). The public
    import paths stay the same.
  - Client layer: `client.submissions` → `SubmissionContractResource` for managing
    submission contracts and following submissions (#121).
  - High-level wrapper: `CrossSubmitter`, built on the client, validates and submits
    (#122).

  Present submission with the same three layers as the landing page (WP2) and the client
  pages (WP4).
- **Note — #122 landed (added 2026-10-17).** `CrossSubmitter.submit` is implemented, so
  the precondition is met. Per ADR 0011: `SubmissionHandler` and the readers moved to
  `handlers/submission/`, the exceptions to `exceptions/`; the full validation is
  `SubmissionHandler.validate_submission(resolver)`; the resource validates and submits;
  `CrossSubmitter` takes a submission contract's name; `check_existing_primary_key`
  defaults to `False`. The reference page should also render `Submission`. The "Sources
  of truth" paths above are updated.
- Dependencies:
  - After 05-release.md, which creates `docs/reference/transformations.md`. If WP5 has
    not landed, create that page here.
  - After 02-landing-and-contributing.md, which writes the component list this task
    extends.
  - Branch off `dev`; PR title `docs: ...`.
