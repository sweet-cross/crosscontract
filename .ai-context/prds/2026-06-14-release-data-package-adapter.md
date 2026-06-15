# Release Data Package Adapter PRD

> Status: draft · Date: 2026-06-14 · Scope: `crosscontract.release.data_package`

## 1. Overview

The **Release adapter** turns CROSS **Contracts** into a Frictionless-compliant
**Data Package** (a zip on disk), parameterised by how each resource's data is
obtained. A data consumer/curator writes a **Release spec** — a `DataPackageSpec`
(authored package metadata) plus a list of `DataResourceSpec` (per-resource
metadata overrides, a chosen `format`, and fetch instructions) — and calls a
single function `create_data_package(spec, source, fn_out)`. The function fetches
each resource's data and its underlying contract through the **Registry**, builds
the Frictionless descriptors directly (the `_standards.frictionless` models), and
writes `datapackage.json` plus the data files into one zip.

This replaces the half-built, descriptor-heavy approach (bespoke
`CrossDataResource` / `CrossDataPackage` classes) with a thin adapter. It is for
the three-person team and downstream consumers who need self-contained,
standard-compliant data packages exported from the platform.

The design was settled in a grilling session; see **ADR 0003** and the
**Release adapter** / **Release spec** glossary entries in `CONTEXT.md`.

## 2. Core Requirements

- **`DataResourceSpec`** — per-resource build recipe:
  - Descriptive **overrides** (all optional): `name`, `title`, `description`,
    `homepage`, `sources`, `licenses`, and arbitrary extra keys (`extra="allow"`).
    Absent ⇒ inherit the fetched contract's value. `name` defaults to the contract
    name.
  - **File binding**: `format: Literal["csv", "parquet"]` (default `"csv"`).
    `encoding` is fixed `utf-8`, not exposed. `path` is **not** authored.
  - **Data instructions**: `data_instructions: DataInstructions` wrapping a
    `FetchSpecMixin` (`contract`, `filters`, `aggregation`) — unchanged from today.
- **`DataPackageSpec`** — authored package metadata: required `name`, `title`,
  `description`; optional `id`, `homepage`, `keywords`, `contributors`, `sources`,
  `licenses`, extra keys; and `resources: list[DataResourceSpec]` (`min_length=1`).
- **`create_data_package(spec, source, fn_out) -> DataPackage`**:
  - `source: CrossClient | CrossRegistry`; a client is promoted via
    `CrossRegistry(client=source)`.
  - For each resource: fetch data via `registry.get_variable(fetch.contract)
    .get_data(**fetch.get_data_kwargs)` (machine names, `use_titles=False`); read
    the contract via `variable.contract_resource.contract`.
  - **Resource metadata = field-by-field override**: contract defaults overlaid by
    the spec's *explicitly set* fields (must respect `model_fields_set` /
    `exclude_unset`, so an unset optional never clobbers a contract default with
    `None`).
  - **Embed `schema`** from the (trusted, `from_server`) contract's `tableschema` —
    no `from_contract` round-trip.
  - Derive `path = data/<name>.<ext>` and `profile` (csv → `tabular-data-resource`,
    parquet → `data-resource`) from `format`.
  - Assemble `_standards.frictionless.DataResource` / `DataPackage`.
  - Write the data files + `datapackage.json` into a single zip at `fn_out`.
  - Return the in-memory `DataPackage`.
- **Retire** `CrossDataResource`, `CrossDataPackage`, `CrossDataResourceReleaseSpec`,
  `CrossDataPackageReleaseSpec`, and the curated `CrossData*MetaData` on the release
  path. **Leave untouched**: `ContractResource` (the fetch handle) and
  `CrossContract.to_server` / `from_server`.
- **Output is Frictionless-valid**: the produced `datapackage.json` round-trips
  through `_standards.frictionless.DataPackage.model_validate`.

## 3. Edge Cases & Error Handling

| # | Case | Handling |
|---|---|---|
| 1 | **Duplicate resource names** in a package (two specs default to the same contract, or explicit collision) | After name resolution, assert uniqueness; raise `ValueError("resource names must be unique: <dup>")`. |
| 2 | **Unset vs. explicit `None`** in a resource override | Override merge uses `spec.model_dump(exclude_unset=True)`; only keys the author actually set win. An optional left absent inherits the contract value. |
| 3 | **Contract not found / auth/network error** | `registry.get_variable` raises `KeyError`/transport error; wrap with the resource name for context, re-raise (`from e`). |
| 4 | **Resource references a Dimension contract** | `CrossBaseDimension.get_data` ignores `filters`/`aggregation` — silent data surprise. If `fetch.filters` or `fetch.aggregation` is non-empty for a dimension resource, raise `ValueError`. A plain dimension fetch (no filters/aggregation) is allowed. |
| 4b | **Dangling foreign keys** (a released resource's schema references a dimension not in the package) | v1: the spec author owns completeness — no auto-inclusion of referenced dimensions. Document it; allowed by Frictionless (external `foreignKeys`). Auto-include is a deferred enhancement. |
| 5 | **Empty `resources`** | `min_length=1` on `DataPackageSpec.resources` rejects at validation. |
| 6 | **Empty DataFrame returned** | Write the (header-only) file and include the resource; emit a `warnings.warn` noting zero rows. Not an error. |
| 7 | **`filters`/`aggregation` reference unknown columns** | Propagated from `get_data` as its existing error; do not swallow. |
| 8 | **`fn_out` parent dir missing** | Create parents (`Path(fn_out).parent.mkdir(parents=True, exist_ok=True)`). |
| 9 | **`fn_out` exists** | Overwrite (it's an explicit output path). |
| 10 | **`fn_out` suffix not `.zip`** | Normalize: if no suffix, append `.zip`; if a different suffix, raise `ValueError` (avoid writing a zip under a misleading name). |
| 11 | **Authored resource `name` contains `/` or path chars** | Validate against `CONTRACT_NAME_PATTERN` (no `/`) so the derived `data/<name>.<ext>` stays flat — prevents zip path traversal. |
| 12 | **Missing required package metadata** (`name`/`title`/`description`) | Pydantic validation error at `DataPackageSpec` construction. |
| 13 | **`created` not supplied** | Optional; if desired, the adapter sets `created` to current UTC RFC3339. (Decision: set it, for reproducible provenance.) |
| 14 | **`tags` → `keywords` leakage** | Out of scope; tracked as a separate TODO. The adapter does not remap `tags`. |
| 15 | **parquet write without engine** (`pyarrow`/`fastparquet` absent) | Let `df.to_parquet` raise its `ImportError`; document `pyarrow` as the expected engine. |

## 4. Implementation Decisions & File Paths

**Pattern:** a stateless module-level **adapter function** over the Registry, with
two Pydantic v2 spec models. No classes for the output descriptors — they are the
`_standards.frictionless` models, assembled procedurally so the file-correctness
guard is structural (strict `format`, derived `path`/`profile`) rather than
enforced by a bespoke class.

**Files to create:**
- `src/crosscontract/release/data_package/specs.py` — `DataInstructions`,
  `DataResourceSpec`, `DataPackageSpec`. Specs inherit from the
  `_standards.frictionless` metadata (`ResourceMetaData` / `PackageMetaData`) with
  partial overrides (`name` optional, `format` added/strict, descriptive fields
  optional).
- `src/crosscontract/release/data_package/create_data_package.py` — the
  `create_data_package` function plus private helpers (`_resolve_registry`,
  `_build_resource`, `_override_metadata`, `_derive_path`, `_write_zip`).

**Files to modify:**
- `src/crosscontract/release/data_package/__init__.py` — export
  `DataPackageSpec`, `DataResourceSpec`, `create_data_package`; drop
  `CrossDataResource`, `CrossDataPackage`.
- `src/crosscontract/release/__init__.py` — same re-export surface.

**Files to delete (retired):**
- `data_resource.py` (`CrossDataResource` + `from_contract`)
- `data_package.py` (`CrossDataPackage` + `to_descriptor`/`to_file`)
- `models_resource.py` (`CrossDataResourceMetaData`, the release `FileMetaData`)
- `models_package.py` (`CrossDataPackageMetaData`)
- `release_specification.py` (`CrossData*ReleaseSpec`)

**Reasoning:** one module owns the recipe (`specs.py`), one owns the
build-and-write (`create_data_package.py`). The output type is reused from
`_standards`, eliminating the triplicated metadata models and the dimension-egress
corner. `ContractResource` and `CrossContract.to_server/from_server` are
explicitly out of the blast radius — release must not perturb the fetch layer.

## 5. Data & Schema Changes

No database changes. Pydantic v2 models only.

**Input contract — `create_data_package`:**
```python
def create_data_package(
    spec: DataPackageSpec,
    source: CrossClient | CrossRegistry,
    fn_out: Path | str,
) -> DataPackage: ...
```

**`DataResourceSpec` (overrides + binding + fetch):** fields per §2; `extra="allow"`;
`format: Literal["csv","parquet"] = "csv"`; `name` validated by
`CONTRACT_NAME_PATTERN`.

**`DataPackageSpec`:** authored package metadata per §2; `extra="allow"`;
`resources: list[DataResourceSpec]` (`min_length=1`).

**Output contract:** a `_standards.frictionless.DataPackage` (returned) and, on
disk, a zip containing:
```
datapackage.json          # canonical name, package root
data/<resource_name>.csv  # or .parquet
...
```
The descriptor's `schema` comes from the trusted contract `tableschema`; `path`,
`profile`, `encoding` are adapter-derived.

## 6. Related ADRs

- **ADR 0003 — Release is a contract → Frictionless adapter, with no bespoke
  descriptor classes.** This PRD *is* the implementation of 0003: function-based
  adapter, `_standards` output, structural file-correctness guard, retirement of
  `CrossDataResource`/`CrossDataPackage`, fetch through the Registry's trusted
  path. Fully compliant.
- **ADR 0002 — Contract metadata follows Frictionless, with deliberate deviations.**
  The release path consumes the *faithful, permissive* `_standards` metadata (full
  `role` set, `extra="allow"`) as 0002's "two layers" note prescribes; the curated
  `metadata_models.py` deviations remain on `CrossContract`, untouched. Compliant.
- **ADR 0001 — Hierarchical Dimensions are strict trees.** Dimension schemas are
  embedded only via the trusted `from_server` regeneration (Registry path), never
  re-admitted through a local round-trip — preserving the rigidity guard. Edge
  cases 4/4b respect that dimensions are self-referential anchors. Compliant.

## 7. Testing Strategy

Tests live in `src/tests/release/data_package/`, mirroring the module. Rewrite
`test_data_resource.py` / `test_data_package.py` (now testing specs + adapter); add
`test_specs.py` and `test_create_data_package.py`.

**Unit — specs (`test_specs.py`):**
- `name` optional and defaults to contract name; `CONTRACT_NAME_PATTERN` rejects
  `/` and uppercase.
- `format` Literal rejects unknown formats; default `csv`.
- `resources` `min_length=1`; missing `name`/`title`/`description` on package fails.
- `extra="allow"` carries unknown descriptive keys through.

**Unit — adapter helpers (`test_create_data_package.py`):**
- `_override_metadata`: explicit field wins; unset optional inherits contract
  (assert via `model_fields_set`); extra key appended.
- `_derive_path`: `csv → data/<name>.csv`, `parquet → data/<name>.parquet`; profile
  mapping.
- unique-name check raises on collision (edge 1).
- dimension resource with `filters`/`aggregation` raises (edge 4); plain dimension
  fetch allowed.
- `fn_out` suffix normalization/rejection (edge 10); parent dir creation (edge 8).

**Integration (`test_create_data_package.py`):**
- A **fake Registry** (or fake `CrossClient` whose `contracts.get` returns a stub
  `ContractResource`) yielding a known `CrossContract` + a small DataFrame. Use the
  existing `CrossContractFactory` (`conftest.py`) for the contract.
- Assert: zip contains `datapackage.json` + `data/<name>.csv`; the data file matches
  the fetched DataFrame; the descriptor's `schema` equals the contract `tableschema`;
  resource metadata reflects overrides; `created` is set.
- **Round-trip**: `DataPackage.model_validate(json.loads(datapackage.json))` succeeds
  — proves Frictionless validity.
- A two-resource package; a parquet resource (skip if `pyarrow` unavailable).

**Mocks/data:** no live platform. Stub the fetch layer at `ContractService.get` /
`CrossRegistry.get_variable` so `filters`/`aggregation` plumbing
(`get_data_kwargs`) is asserted without a server.
