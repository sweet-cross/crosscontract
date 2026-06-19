# Release

The **release** layer turns data living on the CROSS platform into a
self-contained, portable **[Frictionless Data Package](https://specs.frictionlessdata.io/data-package/)** —
a single `.zip` that bundles the data files together with a machine-readable
descriptor (`datapackage.json` and `datapackage.yaml`).

Where the [`CrossRegistry`](../registry/index.md) is about *working with* data
interactively, the release layer is about *publishing* a frozen, citable
snapshot of it: the right resources, fetched and shaped exactly once, packaged
with the metadata a downstream consumer needs to understand and cite the data
without any access to the platform.

The whole process is driven by a single function, `create_data_package`, and a
declarative **release specification** that you author as a YAML (or JSON) file.

## How it works

You describe *what* to release in a release specification and call
`create_data_package`. The function then:

1. **Fetches** the data for each resource from the platform through the
   registry, applying any `filters` and `aggregation` you declared.
2. **Resolves references**: every dimension referenced by a released value
   contract is fetched and added to the package automatically, so the package
   stays self-contained (set `resolve_references=False` to opt out).
3. **Embeds the contract**: each resource's `schema` is taken from its underlying
   contract, and the contract's descriptive metadata is used as the baseline, with
   anything you supplied in the specification overlaid on top.
4. **Writes** one data file per resource plus `datapackage.json` and
   `datapackage.yaml` into the output `.zip`.

```python
from crosscontract import CrossRegistry
from crosscontract.release import create_data_package

registry = CrossRegistry(username="me", password="secret")

create_data_package(
    registry=registry,
    release_spec="my_release.yaml",
    fn_out="my_release.zip",
)
```

`release_spec` accepts either a path to a YAML/JSON file or a
`CrossDataPackageReleaseSpec` instance directly. `fn_out` must end in `.zip`
(or have no suffix — the suffix is added for you).

## The release specification

A release specification has two levels: **package** metadata that describes the
release as a whole, and a list of **resources**, each pairing its own
descriptive metadata with the instructions for fetching its data.

```yaml
# my_release.yaml
name: gdp-release-2025
title: Gross Domestic Product — 2025 Release
description: |
  Annual GDP figures released by the CROSS platform.
  Markdown is encouraged in descriptions.

# Citation guidance for downstream users (see "What CROSS standardizes" below).
citeas: "CROSS Team (2025): Gross Domestic Product. https://example.org/gdp"

licenses:
  - name: CC-BY-4.0
    title: Creative Commons Attribution 4.0
    path: https://creativecommons.org/licenses/by/4.0/

contributors:
  - title: Jane Doe
    email: jane.doe@example.org
    organization: CROSS
    role: author          # restricted to author | maintainer | contributor
  - title: John Smith
    role: maintainer

keywords:
  - gdp
  - macroeconomics

resources:
  - title: Gross Domestic Product
    description: GDP in current prices, by country and year.
    data_instructions:
      fetch:
        contract: gdp           # the contract to pull from the platform
        format: csv             # "csv" (default) or "parquet"
        filters:
          year: [2023, 2024, 2025]
        # aggregation: ...      # optional, see the registry tutorial
```

A few things worth knowing:

- **`name` is required on the package** but **optional on a resource** — a
  resource's name defaults to the name of the contract it fetches from.
- **`data_instructions.fetch`** is the bridge to the platform. Its `contract`,
  `filters`, `aggregation`, and `format` are the same fetch-and-shape
  directives the registry uses, so the data is pushed-down and shrunk *before*
  it crosses the wire.
- **Dimensions are added automatically.** You only list the value contracts you
  want; the dimensions they reference (e.g. country, year) are resolved and
  bundled for you.
- **The schema comes from the contract.** You do not author field definitions in
  the release spec — each resource embeds the schema of its underlying contract
  from the platform as the Frictionless `schema`, so the published data is fully
  described and validatable.
- **Metadata is inherited from the contract.** Descriptive fields that a contract
  already carries — `title`, `description`, `contributors`, `licenses`, and
  `sources` — are filled in automatically from that contract when you don't
  supply them in the release spec. Anything you *do* set in the spec **overrides**
  the contract's value, so the specification only has to state what differs.

### What is taken from the contract vs. the specification

For each resource, the released metadata is the contract's metadata with the
specification overlaid on top:

| Field | If set in the spec | If omitted in the spec |
| --- | --- | --- |
| `schema` | always taken from the contract — not authorable in the spec | taken from the contract |
| `name` | (reserved — currently always the contract name) | the contract's name |
| `title`, `description` | the spec value | the contract's value |
| `contributors`, `licenses`, `sources` | the spec value | the contract's value |

The same overlay applies at the package level: package-wide `licenses`,
`contributors`, and other metadata you author in the spec describe the release as
a whole, independently of the per-resource fallbacks above.

## What CROSS standardizes

The release specification is intentionally **permissive**: it accepts any extra
keys and passes them straight through into the descriptor, so you can enrich a
package with whatever metadata your consumers expect. On top of that, CROSS
**narrows** a few parts of the Frictionless standard to keep releases
consistent:

- **Contributors with a restricted role.** The Frictionless standard treats a
  contributor's `role` as a free-form string. CROSS restricts it to one of
  **`author`**, **`maintainer`**, or **`contributor`** (defaulting to
  `contributor`), so the meaning of a role is unambiguous across every release.
  A contributor still carries `title`, `email`, `organization`, and `path`.
- **Resource-level contributors.** Upstream Frictionless allows `contributors`
  only on the package. CROSS additionally permits them on each resource, because
  a single contract may have its own authors and maintainers distinct from the
  package as a whole.
- **Validated licenses and sources.** `licenses` and `sources` follow the
  Frictionless rules strictly — e.g. a license must define at least one of
  `name` (an [Open Definition](http://licenses.opendefinition.org/) identifier)
  or `path`.
- **Citation via `citeas` (recommended pass-through).** CROSS does not (yet)
  formally model a citation field, but because the specification is permissive,
  a `citeas` key authored at the package (or resource) level is carried through
  verbatim into the descriptor. We **recommend** adding `citeas` to every
  release so downstream users have an authoritative way to cite the data.

Beyond metadata, CROSS also guarantees a few **content** invariants on every
release:

- **Self-contained by default.** Referenced dimensions are bundled, so a
  package needs no platform access to be understood. Foreign keys whose target
  is *not* in the package (e.g. when `resolve_references=False`) are dropped so
  the descriptor stays Frictionless-compliant.
- **Scenario/model dimensions are pruned.** The `dim_model` and `dim_scenario`
  dimensions are reduced to exactly the rows the released data references, so a
  single-scenario release never ships the full platform catalog.

## The output package

The resulting `.zip` is a standard Frictionless Data Package:

```
my_release.zip
├── datapackage.json     # the package descriptor
├── datapackage.yaml     # the same descriptor, as YAML
├── gdp.csv              # one file per released resource …
├── dim_country.csv      # … including the auto-resolved dimensions
└── dim_year.csv
```

It can be opened by any Frictionless-compatible tooling, archived, or handed to
a consumer who has never touched the CROSS platform.
