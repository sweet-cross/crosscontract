# Adapter orchestration: create_data_package (fetch, guard, zip)

## Context
**Part of PRD:** [2026-06-14-release-data-package-adapter.md](../../prds/2026-06-14-release-data-package-adapter.md)

The public entry point that ties the spec, the Registry fetch layer, and the build
helpers together and writes the zip to disk. This is the function consumers call.

## Acceptance Criteria
- [ ] `create_data_package(spec: DataPackageSpec, source: CrossClient | CrossRegistry,
      fn_out: Path | str) -> DataPackage`.
- [ ] `source` resolution: a `CrossRegistry` is used as-is; a `CrossClient` is promoted
      via `CrossRegistry(client=source)`.
- [ ] Per resource: `variable = registry.get_variable(fetch.contract)`, then
      `df = variable.get_data(**fetch.get_data_kwargs)` (machine names, `use_titles=False`).
- [ ] **Dimension guard (edge 4):** if the fetched variable is a `CrossBaseDimension`
      and `fetch.filters` or `fetch.aggregation` is non-empty, raise `ValueError`
      (those are silently ignored by dimension `get_data`). Plain dimension fetch allowed.
- [ ] `get_variable` failures are re-raised wrapped with the resource name (`from e`).
- [ ] Empty DataFrame → still written, with a `warnings.warn` (edge 6).
- [ ] `_write_zip(fn_out, descriptor, files)`: normalize `fn_out` (append `.zip` if no
      suffix; raise on a non-`.zip` suffix), `mkdir(parents=True, exist_ok=True)` on the
      parent, overwrite if present. Zip contains `datapackage.json` (root) + `data/<name>.<ext>`.
- [ ] Returns the in-memory `DataPackage`.

## Implementation Details
- **Modify:** `src/crosscontract/release/data_package/create_data_package.py` (add the
  public function + `_resolve_registry`, `_write_zip`).
- Data writing: `df.to_csv(index=False)` (utf-8) / `df.to_parquet`; write into the zip
  via `zipfile.ZipFile` using the derived relative path as the arcname.
- `datapackage.json`: `json.dumps(package.model_dump(mode="json", exclude_none=True),
  indent=2, ensure_ascii=False)` (serialize-by-alias is already on the `_standards`
  models, so `schema` is emitted correctly).
- Depends on **tasks 01 and 02**.
