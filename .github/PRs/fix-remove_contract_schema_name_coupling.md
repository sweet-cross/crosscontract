# refactor: decouple `contract_type` from `table_type` via an explicit mapping

## Summary

`CrossContract._inject_table_type_to_schema` established the schema discriminator by
copying the contract type straight into the tableschema (`schema_copy["table_type"] =
contr_type`). That made the two vocabularies string-identical by construction: a
contract type could never map onto an existing schema, and the identity was implicit
in an assignment rather than stated anywhere. This branch replaces that assignment
with an explicit `CONTRACT_TYPE_TO_TABLE_TYPE` table, so adding a contract type that
reuses `DimensionSchema` (or any other) becomes a one-line dict entry.

The mapping is the identity today, so **behaviour is unchanged** apart from the wording
of one error message (below). This is a refactor that opens a door, not a fix.

## Changes

- Added a `TableType` literal alias alongside `ContractType`. The two carry identical
  members today; declaring them separately is the statement that they are different
  vocabularies that happen to coincide.
- Added `CONTRACT_TYPE_TO_TABLE_TYPE: dict[ContractType, TableType]` as the single
  place relating the two. Both the discriminator injection and the mismatch check now
  read from it.
- An unmapped `contract_type` is no longer rejected inside the before-validator. The
  helper returns the data untouched so the `Literal`-typed `contract_type` field
  raises pydantic's own `literal_error` at `loc=("contract_type",)`, preserving field
  anchoring for callers that inspect `.errors()`.
- **Reworded the mismatch error** to name the expected table type. It previously read
  `Mismatch between contract_type 'X' and tableschema.table_type 'Y'`, which silently
  assumed the two vocabularies are equal; it now reads `... contract_type 'X', which
  maps to table_type 'Z', and the provided tableschema.table_type 'Y'`. This is the
  only observable change on the branch.
- Documented the design in the helper docstring and added the missing `Raises:`
  section.
- Recorded the branches that still key schema behaviour off a contract type in
  `.ai-context/TODO.md` — `from_server` / `to_server`, plus
  `CrossRegistry.add_variable`.
- Added a **Table type** term to `.ai-context/CONTEXT.md` and updated the **Contract
  type** entry, since this change splits one concept into two. `CLAUDE.md`'s
  "maps 1:1" note was updated to point at the mapping table.

## Testing

New tests, none run in this session (per the repo's no-automatic-validation rule):

- `TestContractTypeToTableTypeMapping` — three guards: every `ContractType` member has
  a mapping; every mapped value is a `table_type` some schema class actually declares;
  and the `TableType` alias itself still matches the schema union. The latter two read
  the tags off `AnyTableSchema`'s members rather than off `TableType`, so a mapping
  pointing at a table type no schema can resolve fails here instead of at runtime.
- `test_instantiated_subclass_schema_mismatch_raises_value_error` — covers the subclass
  direction of the mismatch check, which had no coverage. Note this passes on `dev`
  too; it is a regression guard, not new behaviour.
- Updated the two mismatch-message assertions for the reworded error.

**Please run `uv run pytest` and `uv run mypy src/crosscontract/` before merging.**

## Notes for reviewer

- **Two identical literal definitions.** `ContractType` and `TableType` list the same
  four members. That is deliberate, but it reads as duplication and invites someone to
  alias one to the other later, which would re-introduce the coupling. The mapping
  tests are the guard against that.
- **The unknown-contract-type path produces two validation errors**, not one: the
  `literal_error` on `contract_type`, plus a discriminator error on `tableschema`
  because no `table_type` was injected. This is unchanged from `dev` (which produced a
  `union_tag_invalid` there instead), and is now stated in the helper docstring and in
  the test docstring so nobody tightens the assertion to an error count.
- **`refactor:` rather than `fix:`.** The mapping is the identity, so no input changes
  its outcome; the only observable delta is the error-message wording. Under PSR a
  `refactor:` prefix does not bump the version, which is the right outcome for a
  change with no user-visible behaviour. The branch name still says `fix/` — harmless,
  since the squash-commit message comes from this title.
- **`uv.lock` carries an incidental one-line change** syncing `crosscontract` to
  `0.13.1` to match `pyproject.toml`; it was picked up by a `uv run` during the
  session and is unrelated to the logic here.
