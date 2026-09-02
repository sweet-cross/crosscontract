# feat: validate submission targets against the contracts they name

## Summary

`SubmissionHandler` could extract and transform a target's rows but not check them
against the contract that target names, so the last step of ingesting a bundle sat
with every caller. This branch adds that step at both grains: `validate_target` for
one target, `validate_targets` for every target or a named selection. Across targets
every failure is collected rather than stopping at the first, so a provider fixing a
bundle sees all of it at once instead of one error per round trip.

This withdraws the handler's former "no method runs every target" stance. That stance
held while nothing consumed a loop; batch submission through the server is that
consumer, and leaving the loop to callers would put the same three lines in every
backend, tool and notebook. The decision the absent method was deferring is therefore
made rather than dodged: failures are collected, with no `fail_fast` escape.

## Changes

**Target validation on the handler**
- `validate_target(target_name, contract=None, resolver=None, check_existing_primary_key=False, check_existing_foreign_key=False, lazy=True)`
  composes `get_target_data` with the contract's `validate_data` and returns the
  validated, coerced frame. A target claiming no rows validates like any other and
  returns an empty frame.
- The contract arrives from the caller, directly or through a `ContractResolver`; the
  handler never constructs one, so it stays loadable and runnable with no platform
  connection. An explicitly passed contract wins over one the resolver would return,
  which lets a provider validate against a contract not yet on the platform.
- Three wiring failures raise `ValueError` immediately: no contract and no resolver, a
  contract whose `name` does not match the target's, and a contract the resolver cannot
  supply. The last names both the target and the contract, so a failure inside a loop
  says which target sent you there. An unknown target name stays the `KeyError` that
  `get_target` already raises, keeping "no such target" distinguishable from "no such
  contract".
- No guard was added for a `check_existing_*` flag set without a resolver —
  `validate_data` already raises there naming the contract and both remedies, and a
  second guard would produce two messages for one mistake.

**Collecting across targets**
- `validate_targets(resolver, targets=None, ...)` delegates per target and returns the
  validated frames keyed by **target name**, not by contract name: contract-uniqueness
  is a relaxable guard while a target's name is its identity, so a contract-keyed result
  would silently collapse two entries if that guard were ever relaxed.
- Every target is attempted before anything is raised. Data failures are collected and
  raised together as `TargetValidationError`; wiring failures escape immediately and
  uncollected, because they mean the run is set up wrongly rather than that the rows are
  bad. The result is all-or-nothing — a partly successful run returns nothing.
- `targets=None` means every target in declaration order, `targets=[]` means none. A
  subset asks the resolver only for the contracts it needs, so re-checking three fixed
  targets stays cheap on the wire.

**`TargetValidationError`**
- New `submission/exceptions.py`. Holds `dict[str, SchemaValidationError]` keyed by
  target name; `to_list()` flattens every sub-error's rows with a `target` key added,
  `to_pandas()` wraps that in a frame, and the message names the failing targets.
- Deliberately not a `SchemaValidationError` subclass: that class wraps and parses a
  single pandera exception, while this one holds a mapping of already-parsed failures
  and parses nothing.
- Exported from both `crosscontract` and `crosscontract.submission`.

**Resolver, renamed and exported**
- `ClientContractResolver` → `CrossContractResolver`, now exported from
  `crosscontract.crossclient`. It was internal to `ContractResource`; callers need it to
  supply target contracts to `validate_targets`.
- Docstrings state what the rename makes visible: it reaches the platform over HTTP and
  sees whatever the authenticated caller may read, and only a missing contract becomes
  `None` — a permission error or server failure propagates as the client exception.

**Prose corrected where the code now contradicts it**
- The `SubmissionHandler` class docstring no longer claims no method runs every target;
  the paragraph is rewritten to state the current shape.
- CLAUDE.md's `submission/` section gains `submission_handler.py` and `exceptions.py`,
  both previously absent, and drops the "(later) the code that executes them" phrasing
  there and in `submission/__init__.py`.
- CONTEXT.md's **Submission handler** entry is rewritten and a **Submission validation**
  entry added; ADR 0004 carries a dated amendment recording the withdrawn consequence and
  the decisions that replace it.

## Testing

`src/tests/submission/test_validate_targets.py` (new, 575 lines) covers the three
surfaces in four classes:

- `TestValidateTarget` — the composition and its coerced result, contract precedence
  over the resolver (asserted with a resolver whose contract *would* fail, so a
  regression surfaces as a failure rather than a pass), resolver-only resolution,
  argument pass-through, and the empty-target case. Coercion is asserted by a changed
  dtype, not by the absence of an exception.
- `TestValidateTargetGuards` — one test per wiring failure, including that an unknown
  target stays a `KeyError` and that a `check_existing_*` flag without a resolver
  surfaces `validate_data`'s own message rather than a second one.
- `TestValidateTargets` — every target attempted before raising, passing frames
  discarded, the message and flattened rows carrying target names, a wiring failure
  escaping even after an earlier target already failed on its data, a forgotten
  `drop_columns` (extra column, caught by `strict=True`) arriving as a *collected*
  failure, and `lazy=False` still yielding one error per failing target.
- `TestSelectiveTargets` — `None` vs `[]`, an unknown name raising, a repeated name
  collapsing, and a subset leaving the other contracts unresolved.

`src/tests/submission/test_exceptions.py` (new) builds its sub-errors by validating
genuinely bad frames rather than constructing bare `SchemaValidationError`s, whose
`to_list()` is empty and would make the flattening assertions vacuous.

`src/tests/contracts/schema/validation/test_pandas_validation.py` gains
`TestEmptyDataFrame`, pinning the assumption target validation rests on: a strict,
coercing schema accepts a zero-row frame, and `primary_key_values=[]` still turns the
uniqueness check on.

Resolvers are `Mock(spec=ContractResolver)` doubles throughout; nothing reaches the
platform.

## Notes for reviewer

- **The three `ValueError` guards are defensive branches, which the repo's style
  normally bans.** They are here because `contract` wins over `resolver`, so handing one
  target's rows to another target's contract validates happily and returns a
  plausible-looking wrong answer. That is silently wrong rather than a crash, and the
  handler has `target.contract` in hand to catch it. Note the honest counter-precedent:
  `transform_target_data` *documents* the analogous mistake instead of guarding it — the
  difference being that a DataFrame carries no identity.
- **An exception raised by a transformation propagates rather than joining the
  collection.** Only `SchemaValidationError` is caught. Anything else escaping is
  intended: the collection is typed as schema failures, and widening it would change what
  a `to_list()` row means.
- **Nothing checks that a target's contract exists at authoring time.**
  `SubmissionContract` inherits `validate_references`, which walks foreign keys and never
  looks at `extraction.targets`, so a target naming an absent contract is only discovered
  when validation asks a resolver for it. Deferred to `.ai-context/TODO.md` with the
  reasoning: keeping it out is what lets target validation treat an unresolvable contract
  as an immediate wiring error instead of folding it into the collected data failures.
- **`validate_targets` requires its resolver positionally** (`resolver: ContractResolver`,
  no default), unlike `validate_target` where `None` is a working mode because a contract
  can arrive directly. There is no such mode on the loop, so omitting it is a `TypeError`
  at the call site rather than a `ValueError` from inside the loop.
- There is no mkdocs page for `submission/` to update — a pre-existing gap, untouched
  here.
