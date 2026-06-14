# TODO — separate-PR backlog

Deferred work that is **out of scope for the current change** but worth doing in its
own PR. This is a lightweight running list, not a tracker: capture enough context to
act on the item cold, then move it to an ADR / PRD / issue if it grows.

When you finish an item, delete it (or move it to a commit/ADR). When you defer
something while working, append it here rather than expanding the PR in front of you.

## Open

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

## Related context (not TODO items)

- The release layer is a contract → Frictionless adapter; `CrossDataResource` /
  `CrossDataPackage` are retired. See [ADR 0003](./adrs/0003-release-is-a-contract-to-frictionless-adapter.md)
  and the "Release adapter" terms in [CONTEXT.md](./CONTEXT.md). The old `from_contract`
  + `Dimension` egress corner is **resolved** by routing through the registry's
  trusted-source path (CONTEXT.md "Flagged ambiguities").
