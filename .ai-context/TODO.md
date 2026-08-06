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

## Related context (not TODO items)

- The release layer is a contract → Frictionless adapter; `CrossDataResource` /
  `CrossDataPackage` are retired. See [ADR 0003](./adrs/0003-release-is-a-contract-to-frictionless-adapter.md)
  and the "Release adapter" terms in [CONTEXT.md](./CONTEXT.md). The old `from_contract`
  + `Dimension` egress corner is **resolved** by routing through the registry's
  trusted-source path (CONTEXT.md "Flagged ambiguities").
