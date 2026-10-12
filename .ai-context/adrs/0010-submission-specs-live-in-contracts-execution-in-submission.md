# Submission specs live in contracts/, their execution in submission/

The declarative parts of a **Submission contract** live below the client: the contract and
its extraction specs (`SubmissionContract`, `ExtractionInstructions`, `Target`) in
`contracts/submission/`, and the Excel declaration together with the reader that carries
it out (`ExcelProcessor`, `ExcelSheet`, `WideLayout`, `read_excel_workbook_bytes`) in
`transformations/excel/`. What executes them stays in `submission/`: `SubmissionHandler`,
`CrossSubmitter`, the exceptions, and the reader wrappers that take a contract.
`CONTRACT_NAME_PATTERN` moves to the dependency-free `constants.py`.

This supersedes the placement bullet of [ADR 0004](./0004-submission-contracts-carry-extraction-instructions.md)
("`submission/` is top-level, peer to `release/`"). What a submission contract is, and that
it carries its extraction instructions, is unchanged. [ADR 0007](./0007-the-submitter-is-the-provider-side-mirror-of-the-registry.md)
is untouched: `CrossSubmitter` still lives in `submission/`.

## Why

A client-side `SubmissionService` has to parse a `SubmissionContract`. With the specs in
`submission/`, and `submission/` importing `crossclient` for the submitter, the two
packages would import each other. Python would fail on the half-loaded `crossclient` as
soon as either side was imported first.

The registry already shows the shape that avoids this. `CrossRegistry` sits on top of a
`CrossClient`, which works on `CrossContract`s defined in `contracts/`, below both. Moving
the submission specs to `contracts/` gives the write side the same layers, and the import
graph runs one way:

```
constants ← transformations ← contracts ← crossclient ← submission
```

ADR 0004 kept the specs out of `contracts/` because extraction there, importing
`transformations`, would have closed a cycle with `transformations` importing
`CONTRACT_NAME_PATTERN` from `contracts`. That cycle came only from where a constant lived.
With the constant in `constants.py`, `transformations` imports nothing from `contracts`.

The Excel declaration goes to `transformations/` rather than next to the contract so that
it stays with its reader: reshaping a wide workbook into the long bundle is a
transformation, and the reader needs only the processor and the field names, not the
contract. The submitter and the handler stay together in `submission/`, because one
sequences the other.

## Consequences worth knowing

- **Two packages named `submission`.** `crosscontract.contracts.submission` holds the specs,
  `crosscontract.submission` the execution. Relative imports keep code unambiguous; in
  conversation and in grep results, name the full path.
- **The Excel reader has two layers.** `read_excel_workbook_bytes(processor, field_names,
  data)` in `transformations/excel/` does the work. `read_excel_bundle_bytes(contract, data)`
  and `read_excel_bundle(contract, filename)` in `submission/excel_processing.py` check that
  the contract has an `excel_processor` and pass its sheets and `tableschema` field names on.
- **Public import paths are unchanged.** `SubmissionContract` is still importable from
  `crosscontract` and `crosscontract.submission`, and now also from `crosscontract.contracts`.
  `crosscontract.submission.extraction` and `crosscontract.submission.excel_processing`'s
  spec models are gone; nothing outside this repository imported them.
- **`submission/` is still not free of `crossclient`**, as ADR 0007 states. What changes is
  that nothing below it depends on it any more.
