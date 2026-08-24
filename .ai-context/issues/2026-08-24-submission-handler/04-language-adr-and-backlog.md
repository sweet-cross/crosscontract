# WP4 — Language, ADR, and backlog

## Context

The handler introduces a term the glossary does not have, contradicts a consequence ADR
0004 states as fact, and moves a method that four documents name by path. Left alone, the
`.ai-context/` set describes a package that no longer exists.

## Acceptance Criteria

- [ ] CONTEXT.md carries a **Submission handler** term.
- [ ] No document still says execution is absent from `submission/`.
- [ ] No document still refers to `SubmissionContract.unclaimed_rows`.
- [ ] `TODO.md` reflects the questions that are actually still open.

## Implementation Details

### `.ai-context/CONTEXT.md`

- **Add a Submission handler term.** What it is: the executor that applies a
  **Submission contract**'s **Extraction instructions** to a delivered bundle, one
  **Target** at a time — select the rows a target claims, apply its **Transformation
  profile** and then its own **Transformations**. Record two properties that are
  decisions rather than details: it works **one target at a time**, so whether a run
  aborts or collects failures is the caller's, and it **does not resolve target
  contracts** — see the ADR note below.
  `_Avoid_`: extractor, processor, pipeline.

- **Amend the three `_Avoid_` lines that ban "extractor" outright.** *Submission
  contract*, *Extraction instructions* and *Target* each list it. The ban was aimed at
  the legacy hand-written Python form and should stay aimed there — but the glossary now
  has a real executor, so each line should point at **Submission handler** as the term
  for it rather than leaving the reader with a banned word and no replacement.

- **Repoint the *Unclaimed rows* term.** It currently says "Reported by the **Submission
  contract**". It is reported by the **Submission handler**.

### `.ai-context/adrs/0004-submission-contracts-carry-extraction-instructions.md`

- The consequence **"Execution is not in this package yet"** is now false. Rewrite it to
  record what landed: a `SubmissionHandler` in `submission/`, per-target, pandas — and
  *why* pandas is settled rather than provisional (the transformation layer is already
  `pd.DataFrame -> pd.DataFrame`; another engine would fork it or round-trip through it).

- **Add the note that keeps validation open without foreclosing it.** The ADR's second
  named decision is that extraction never resolves its target contracts and that no spec
  needs a platform connection to load, validate, or execute. The handler holds to that,
  and a later `validate_target_data` must too: the contract arrives from the **caller**
  — passed in, or via the existing `ContractResolver` protocol that `BaseContract`
  already defines for `validate_references` — rather than being looked up inside
  `submission/`. Writing this down is the point: the name "handler" was chosen to leave
  room for validation, and the next person should find the constraint before they add a
  lookup rather than after.

### `.ai-context/TODO.md`

Under "Submission extraction follow-ups":

- **Delete "Decide whether unclaimed rows raise or warn."** The per-target handler
  answers it: there is no aggregate run for a policy to attach to, so it is the caller's
  loop that decides. Nothing left to decide.

- **Reprice the contested-rows item.** It currently warns that `unclaimed_rows` "folds
  each target's mask into a single accumulator and keeps no intermediates, so adding it
  means reshaping that loop". After WP2 the per-target mask is the handler's primitive
  and available on demand, so contested detection is a sum over masks rather than a
  restructure. The *question* — whether unintentional overlap is worth surfacing at all,
  given ADR 0004 makes overlap legal — is unchanged and stays open.

- **Follow the `unclaimed_rows` path references.** Both surviving items name it as living
  on `SubmissionContract`.

- Leave the load-time filter parseability item, the column-tracking item, and the
  `MapColumnValues` conflict-guard item alone.

**Dependencies:** WP1–WP3. The documents should describe what the branch actually
contains.

**Verification:** prose only, no test run.
`grep -rn "unclaimed_rows" .ai-context/` should turn up no reference to it on
`SubmissionContract`, and no document should still assert that execution is absent from
`submission/`.
