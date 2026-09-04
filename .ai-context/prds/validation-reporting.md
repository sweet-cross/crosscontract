# Validation reporting — problem and approaches

Status: **draft**. Problem stated, approaches sketched, nothing chosen. Written 2026-08-30.

The follow-on that [check-based-validation.md](check-based-validation.md) parks under
*Deliberately open*. Terminology lives in the *Validation* section of
[`CONTEXT.md`](../CONTEXT.md) — **Check**, **Base check**, **Composite check**, **Derivation**,
**Data validation**, **Existing values**.

---

## The problem

A **Data validation** currently answers one question — did anything fail — and answers it
in a shape that loses information on the way out. Four distinct defects sit behind that.

### Pandera reports cells, not rules

A **Check** derived from a key or a reference is a *DataFrame-level* pandera check: it
receives the whole frame and returns a row mask. Pandera has no idea which columns the
check was about, so when it builds `failure_cases` it enumerates the **cells of the failing
rows**. A primary key violation on `id`, in a frame with `id` and `name`, arrives as two
rows:

| column | failure_case |
|---|---|
| `id` | `1` |
| `name` | `'a'` |

The second row is noise — `name` had nothing to do with the violation — and neither row
says "this is the primary key". For a composite key it is worse: the columns that jointly
form the key are never grouped.

### The fix for that is prose parsing

`SchemaValidationError._parse_reference_errors` compensates. It identifies key and
reference failures, collapses them to one row per check per index, looks the real key
values up out of the original frame, and rewrites `column` to the key's columns. To do
that it needs to know which columns a check covered — and the only place that survives is
the check's own message, so it recovers them with a regex over
`failure_cases["check"]`.

Two shapes are recognised today: the legacy adapter's `PrimaryKeyError: ['col_a']`, and
`Columns 'col_a, col_b' in check '<label>' …` as produced by the check classes.

Nothing enforces either shape. Rewording one `failure_message()` silently degrades every
report that check appears in, and no test fails — the errors just get noisier and lose
their key values. The coupling is invisible from the check's side.

### Pandera gives one identifying string, not two

The obvious repair — put a machine-readable tag on the check and leave the message to
humans — does not work. `failure_cases["check"]` holds the check's `error` if one is set
and its `name` otherwise. One column, one string. Any scheme that recovers structure from
`failure_cases` alone is parsing prose, however it is dressed up.

### A skipped check is indistinguishable from a passing one

This is the defect the previous PRD retired the `ValueError` for, deliberately, and left
open. An external foreign key with no **Existing values** supplied emits no check. The
frame then validates exactly like one where the reference was checked and held. A
submitter cannot tell "your references are sound" from "nobody looked".

The flags compound it: `skip_primary_key_validation=True` now suppresses only the
comparison against existing keys, but nothing in the result says which comparisons were
made and which were not.

---

## Who consumes this

- `SchemaValidationError.to_list()` / `.to_pandas()` — the public surface, exported from
  the top-level `crosscontract` package.
- `crossclient`'s `ValidationError` wraps the same list and tells the user to call
  `.to_list()` or `.to_pandas()`; raised by `ContractResource.validate_dataframe`.
- `cross_back` catches `SchemaValidationError` in `contract_data.py` and re-raises its own
  `ValidationError`, which becomes a 422 body. **This is what a data provider actually
  sees**, so the shape of `to_list()` is a wire format in practice.
- The notebooks use `.to_pandas()` interactively.

Any change here is a change to all four.

---

## What a report has to answer

1. **What failed** — which rule, on which columns, at which rows, with which values.
2. **What was checked** — the executed **Standard** and **Additional** checks, so a clean
   result means something specific.
3. **What was not checked, and why** — an external reference with no values supplied; a
   comparison suppressed by a flag.
4. **In an order and shape a submitter can act on**, one row per problem rather than one
   per cell.

Only (1) is attempted today. (2) and (3) are unavailable to the error object at all,
because it receives the pandera exception and nothing else.

---

## Approaches

### A. Keep parsing, but make the shape structural

`BaseCheck.failure_message()` composes the `Columns '<cols>' in check '<label>' ` prefix
from `self.columns`; subclasses supply only the rule clause. The parser's pattern then
matches something the base class guarantees rather than a convention each subclass retypes.

- *Cheap.* An hour, no signature changes, no new concepts.
- Still prose parsing, still one string, and it does nothing for (2) or (3).
- Best read as insurance for the status quo rather than a solution.

### B. Recover the check objects from the pandera exception

`SchemaErrors.schema_errors` is a list of `SchemaError`s, each holding the `pa.Check` that
produced it, which in turn wraps our check instance. Columns come off the object; no
message is parsed.

- Exact, and immune to rewording.
- Reaches through pandera's private `_check_fn`, so a pandera upgrade can break it
  silently.
- Requires rebuilding `_parse_pandera_errors` around the per-error objects instead of the
  flattened `failure_cases` frame.
- Still nothing for (3) — a check that was never emitted raises no error to recover.

### C. Hand the executed checks to the error object

`TableSchema.validate_dataframe` already builds the merged check list. Pass it down
through the runner into `SchemaValidationError` alongside the pandera exception. The error
then holds both sides and joins them — by `failure_message()` as an exact dictionary key,
not a regex — and knows the full executed set even for the checks that passed.

- No parsing, no private pandera attributes.
- Answers (1) and (2) directly, and (3) if the assembly also reports what it declined to
  emit and why.
- Changes the runner's signature and `SchemaValidationError.__init__`, both of which are
  public. Ripples into `crossclient` and `cross_back`.
- Makes the report a first-class thing rather than a rendering of an exception, which is
  probably where this ends up regardless.

### D. Stop delegating reporting to pandera

Run the checks directly, collect `(check, mask)` pairs, and build the report from them;
keep pandera for dtype and column-level constraints only.

- Total control, no impedance mismatch at all.
- Duplicates machinery pandera already provides, and splits validation across two engines
  with two failure shapes.
- Only worth considering if B and C both prove insufficient.

---

## Questions to settle

- **Is the report a return value or only an exception?** Today a clean validation returns
  the DataFrame and says nothing. Answering "what was checked" for a *passing* frame means
  something has to come back on the happy path too, which `validate_dataframe`'s signature
  does not currently allow.
- **Does the reporting shape belong in `crosscontract` or in `cross_back`?** The library
  produces the facts; the 422 body is a presentation decision. The line between them is
  currently drawn by accident, at `to_list()`.
- **Is `to_list()` a wire format?** If `cross_back` serialises it, changing it is a
  breaking change for submitters, not just for callers.
- **What identifies a check in a report?** Related to, but not the same as, the merge
  identity WP2 of the previous PRD has to settle.

---

## Out of scope

- The merge identity for **Standard** and **Additional** checks — that is WP2 of
  [check-based-validation.md](check-based-validation.md), and this PRD should be written
  after it lands.
- Anything about *which* checks run. This is about reporting what ran, not changing it.
- The `DataFrameSchema` name, currently unset so reports read `DataFrameSchema 'None'`.
  A one-line fix once the contract name reaches the adapter; noted here only because it
  surfaces in the same output.
