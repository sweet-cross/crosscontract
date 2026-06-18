# Release is a contract → Frictionless adapter, with no bespoke descriptor classes

The release layer is an **adapter** from CROSS **Contracts** to a Frictionless
**Data Package**, parameterised by how each resource's data is obtained. It holds
only specification models — `CrossDataPackageReleaseSpec` and
`CrossDataResourceReleaseSpec` — plus a single
`create_data_package(registry: CrossRegistry, release_spec, fn_out)` function that
fetches through the **Registry**, overlays the spec, and writes a zip. Its output
type is the faithful, permissive `_standards.frictionless` `DataResource` /
`DataPackage` directly. We **retired** the bespoke `CrossDataResource` and
`CrossDataPackage` descriptor classes.

> Accepting a `CrossClient` as `source` (promoted to a `CrossRegistry`) is the
> intended end state but **not yet implemented**: the current signature takes a
> `CrossRegistry` directly.

## Why

We want the release to be Frictionless-compliant by construction. A parallel,
CROSS-strict descriptor hierarchy bought us little and cost us a lot: it
duplicated the metadata models three ways and it re-admitted a supplied schema on
egress, which collided with dimension rigidity (the old
`CrossDataResource.from_contract` corner). Emitting the standard models directly
removes both problems.

The CROSS restriction we *do* care about — the file description being correct —
moves to where it can't be violated rather than living in a descriptor class:

- `format` is a strict `Literal["csv", "parquet"]` on the resource spec's `fetch`
  instructions.
- `create_data_package` derives `path` (a flat `<name>.<ext>`) and `profile`
  (`tabular-data-resource` for csv, `data-resource` for parquet) from that
  `format`, so filename/format consistency holds by construction — there is no way
  to express a mismatch.

## Consequences

- **Resource metadata overrides, package metadata is authored.** A resource's
  descriptive metadata defaults from its fetched **Contract** and is overridden
  field-by-field by the spec; a **Data Package** has no contract to default from,
  so its metadata is authored wholesale.
- **The dimension-egress corner dissolves.** The adapter fetches every contract
  through the **Registry**, i.e. via the trusted `from_server` path, which
  regenerates a Dimension's rigid schema from template. The adapter embeds that
  trusted schema; `from_contract` is never called on a local contract.
- **The fetch layer is untouched.** `ContractResource` (the Registry/Client
  per-contract handle) keeps fetching data and exposing the contract. It is a
  different thing from the retired `CrossDataResource` despite the near-identical
  name.
- **`encoding` is fixed at `utf-8`** and not exposed on the spec.
- **Output is a single zip** written to a caller-chosen path; whether to extract
  it is the caller's concern. The zip carries the descriptor as both
  `datapackage.json` (canonical) and `datapackage.yaml` (a human-readable twin).
- **A release must yield at least one non-empty resource.** Resources whose
  fetched data is empty are warned and skipped; if *every* resource is skipped,
  `create_data_package` raises rather than emitting an empty package.
