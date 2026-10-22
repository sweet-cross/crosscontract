# Release specs live in contracts/, their execution stays in release/

> **Superseded in part 2026-10-22** (#137): `FetchSpecMixin` is now `FetchSpec` and lives,
> with the aggregation specs, in `contracts/fetching/`; `transformations/fetch/` is gone.
> The release spec module imports it from there instead of from `transformations`.

The **Release spec** moves out of `release/data_package/` into `contracts/release/`:
`CrossDataPackageReleaseSpec`, `CrossDataResourceReleaseSpec` and `DataInstructions` now
live in `contracts/release/release_specification.py`. `FetchSpecMixin` stays in
`transformations/fetch/`. The **Release adapter** (`create_data_package`,
`_resolve_resource.py`, `_resolve_package.py`) stays in `release/data_package/` and keeps
running against a `CrossRegistry`.

`contracts/` thereby becomes the declarative layer: contracts plus the specs that name
them. It already held the submission specs (ADR 0010); the release specs follow the same
rule.

## Why

cross_back has to parse, validate and store release specs. With the specs in `release/`,
it would have to import a package that depends on `registry/` and so on `crossclient/`,
just to read a YAML file. The spec module never needed any of that: it imports only
`_helpers`, `_standards`, `constants` and `transformations`, all of which sit below
`contracts/`. So the move closes no cycle and changes no direction in the import graph.

The execution does not move with it. It fetches through the **Registry** and shapes data
with the registry's variables (filters, dimension aggregation, labels), so it cannot sit
in `handlers/`, which must not depend on `crossclient/` (ADR 0011). Moving it there means
running it against a `ContractResolver` and pulling the data shaping out of
`registry/variables/` first. That is a separate issue, opened once cross_back needs
server-side data packages.

## Consequences worth knowing

- **The old module path is gone.** `crosscontract.release.data_package.release_specification`
  is removed with no shim. Both specs are still importable from `crosscontract.release` and
  `crosscontract.release.data_package`, and now also from `crosscontract.contracts` and the
  top-level `crosscontract`. `DataInstructions` is exported only from
  `crosscontract.contracts.release`.
- **`release/` still imports `registry/`.** Only the spec became independent of the client;
  building a **Data Package** still needs a live **Registry**.
