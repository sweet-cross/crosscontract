# TODO — separate-PR backlog

Deferred work that is **out of scope for the current change** but worth doing in its
own PR. This is a lightweight running list, not a tracker: capture enough context to
act on the item cold, then move it to an ADR / PRD / issue if it grows.

When you finish an item, delete it (or move it to a commit/ADR). When you defer
something while working, append it here rather than expanding the PR in front of you.

## Open

### Add descendant traversal to `CrossDimension`

`CrossDimension` ([dimension.py](../src/crosscontract/registry/variables/dimension.py))
can walk **up** the tree (`ancestor_maps`, `_ancestry_chains`) but has no way to walk
**down**. Add a `get_descendants(node_id, include_self=False)` (all children,
grandchildren, …) and a `get_children(node_id)` (direct children only).

Descendants are the inverse of the cached ancestry chains — a node's descendants are
exactly the nodes whose chain contains it — so `get_descendants` can reuse
`_ancestry_chains` with no new cache; `get_children` is a `parent_id == node_id` filter
on `self.data`. If repeated bulk queries become hot, precompute a `parent → [children]`
adjacency dict (mirroring the `ancestor_maps` precompute) instead. Pairs with the
aggregation layer: `get_descendants(x)` yields the id set for "everything under x".

### Decide whether `tags` should be `keywords` at the contract level

Frictionless uses `keywords` (a `list[str]`, `minItems: 1`) for free-text package/resource
labels; CROSS models the same concept as `tags` on `CrossMetaData`
([cross_contract.py](../src/crosscontract/contracts/contracts/cross_contract.py)). In the
release path, `tags` currently leaks into the data-package / data-resource descriptors
under the non-standard key `tags` (tolerated, since the Frictionless schemas don't set
`additionalProperties: false`, but non-canonical).

Decide whether to rename `tags` → `keywords` at the **contract level** (cleanest — the
release output then complies for free) or to remap `tags` → `keywords` only on the way
out in `to_descriptor`. Renaming at the contract level is a breaking change for the
server payload (`to_server`) and stored contracts, so it needs coordination; the
egress-only remap is safe but leaves the two vocabularies out of sync. Note `keywords`
also carries `minItems: 1`, so empty lists must collapse to omitted (same pattern as the
package `_empty_list_to_none` validator).

### Release adapter follow-ups

Deferred while landing the first `create_data_package` draft:

- **Accept `CrossClient` as `source`.** `create_data_package` currently takes a
  `CrossRegistry` directly; ADR 0003's intended signature also accepts a
  `CrossClient` (promoted via `CrossRegistry(client=source)`).
- **Dimension egress.** A resource referencing a Dimension contract routes through
  `var.data`, so `filters` / `aggregation` are silently ignored. Decide whether to
  raise when they are set for a dimension, and add auto-inclusion of referenced
  dimensions as their own resources (the `# todo: Collect dimensions` marker in
  [_resolve_resource.py](../src/crosscontract/release/data_package/_resolve_resource.py)).
- **Narrow error handling.** `fetch_data` wraps *every* exception from `get_data`
  as `RuntimeError`; unknown-column errors from `filters`/`aggregation` should
  propagate as-is instead.

### Replace rST double-backtick literals in docstrings with markdown single backticks

The docstring convention in [CLAUDE.md](../.claude/CLAUDE.md) now bans reStructuredText
syntax outright, matching the sibling `cross_back` repository. The existing docstrings
predate that and use ``double-backtick literals`` throughout — roughly 90 occurrences
across 9 files:

`transformations/fetch/fetch_spec.py`, `contracts/contracts/base_contract.py`,
`contracts/contracts/cross_contract.py`, `contracts/schema/schema.py`,
`registry/registry.py`, `registry/variables/base_dimension.py`,
`registry/variables/dimension.py`, `registry/variables/data_variable.py`,
`registry/variables/flexible_dimension.py`.

The two `crossclient/services/` modules were converted while the project-scoping work
was already editing their docstrings, so they are done and off this list. Grep for the
double-backtick sequence under `src/crosscontract/` to confirm the remaining set
before starting.

Mechanical `` `` `` → `` ` `` substitution inside docstrings only — do not touch string
literals or comments. mkdocstrings renders both today, so this is consistency rather
than a rendering fix, which is why it is deferred rather than blocking. Worth doing in
one sweep so no file is left half-converted. There is also a single surviving rST role
(`grep -rn ':param:\|:returns:\|:raises:\|:class:\|:meth:\|:func:\|:attr:' src/crosscontract/`)
to clear at the same time.

While sweeping, check the same files for docstrings missing an applicable
`Args:` / `Returns:` / `Raises:` section — the convention now requires all three where
they apply.

### Remove the construction-time `filters` argument from `CrossDataVariable`

Deprecated (`FutureWarning`) on `fix/filter_at_var_level`; the removal itself is gated
on confirming there are no callers outside this repo. Full write-up, rationale, and
removal checklist in
[issue #77](https://github.com/sweet-cross/crosscontract/issues/77).

### Key the remaining contract-type branches off the schema instead

`CONTRACT_TYPE_TO_TABLE_TYPE` decoupled the discriminator injection, but three branches
still hardcode a contract type against schema behaviour. Once a second contract type
maps onto `DimensionSchema`, each of them silently does the wrong thing.

- `CrossContract.from_server` / `CrossContract.to_server` in
  `src/crosscontract/contracts/contracts/cross_contract.py` branch on
  `contract_type == "Dimension"` to strip the `tableschema` the server owns. Rework
  them to test the resolved schema — `isinstance(self.tableschema, DimensionSchema)`,
  **not** `BaseDimensionSchema`: that also matches `FlexibleDimensionSchema`, whose
  fields are user-defined and must round-trip, so the broader check would silently drop
  them from the `to_server` payload. An explicit "server owns this schema" marker on
  the schema class would work too.
- `CrossRegistry.add_variable` in `src/crosscontract/registry/registry.py` picks
  `CrossDimension` vs `CrossFlexibleDimension` off
  `cr.contract.contract_type == "Dimension"`. The surrounding `cr.is_dimension` already
  keys off the schema, so this should read
  `isinstance(cr.contract.tableschema, DimensionSchema)` for consistency.

Deferred because the first item touches the client round-trip and both want their own
test pass.

### Submission extraction follow-ups

Deferred while landing the extraction spec models
([ADR 0004](./adrs/0004-submission-contracts-carry-extraction-instructions.md)). The PRD
and task files that carried the analysis are deleted, so the detail is reproduced here.

- **Assemble the derived routing `enum`.** The routing field's permitted values come from
  the targets' filters and are never authored — `_check_routing_column` in
  [submission_contract.py](../src/crosscontract/submission/submission_contract.py)
  rejects an authored `enum` for exactly that reason, but nothing yet builds the derived
  set, so the claim is enforced without being delivered. Where the assembly lives is
  deliberately open: a property on `SubmissionContract`, a helper on
  `ExtractionInstructions`, or the future validator that checks data against the
  contract. Whichever site is chosen, the values are the `routing_column` entry of each
  target's `filters`.

- **Decide how far column tracking goes.** Column references are order-dependent: after
  `rename_columns {timestamp: year}` a later `cast_column year` is correct and
  `cast_column timestamp` is not, so static checking needs the column set tracked
  *through* the pipeline rather than compared against the schema fields. The options are
  (a) every transformation declares `output_columns(input_columns) -> set[str]` —
  strongest checking, but it raises the cost of adding a transformation, which cuts
  against the extensibility goal; (b) *recommended* — the method is optional, a
  transformation that omits it returns `None` and tracking stops there with the remainder
  unchecked; (c) no static checking, rely on runtime failures. Under (a) or (b) these
  raise: a `rename_columns` key not in the tracked set, a `drop_columns` naming an
  untracked column, and a `column_name` not in the tracked set. Strictness on
  `drop_columns` is deliberate — it is what removes the `uploaded_by` / `uploaded_at`
  wart, which exists today only because `admin_tools` reads back from the server while
  the backend reads the raw upload. The hook was never added to the six transformations
  in [transformation/](../src/crosscontract/transformations/transformation/), so adopting
  (a) or (b) now means retrofitting all six rather than writing it into three while they
  were being drafted. That changes the price, not which option is right.

- **`MapColumnValues` has no conflict guard.** Mapping a value onto one already present
  in the column merges the two silently; on a foreign-key column that produces duplicate
  primary keys downstream and breaks the sum invariant of
  [ADR 0001](./adrs/0001-dimensions-are-strict-trees.md). Either add an `on_conflict`
  option to `MapColumnValues` in
  [column_transformations.py](../src/crosscontract/transformations/transformation/column_transformations.py)
  or decide that the silent merge is acceptable — but decide, rather than leaving it
  undecided. This is a correctness question about the transformation itself; no legacy
  specification depends on the current behaviour.

- **Execution.** Applying a submission contract to actual data — filter rows per target,
  apply the transformation profile and then the target's own transformations, hand the
  result to the named contract for validation — is not written. When it lands it joins
  [submission/](../src/crosscontract/submission/) alongside the spec models, as a
  pipeline rather than a schema conversion.

## Related context (not TODO items)

- The release layer is a contract → Frictionless adapter; `CrossDataResource` /
  `CrossDataPackage` are retired. See [ADR 0003](./adrs/0003-release-is-a-contract-to-frictionless-adapter.md)
  and the "Release adapter" terms in [CONTEXT.md](./CONTEXT.md). The old `from_contract`
  + `Dimension` egress corner is **resolved** by routing through the registry's
  trusted-source path (CONTEXT.md "Flagged ambiguities").
