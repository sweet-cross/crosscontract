# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

The project uses `uv` for package management and Python 3.11+.

```bash
# Install dependencies (including dev group)
uv sync --group dev

# Run all tests
uv run pytest

# Run a single test file
uv run pytest src/tests/contracts/schema/test_schema.py

# Run a single test by name
uv run pytest src/tests/contracts/schema/test_schema.py::test_name

# Lint (check only)
uv run ruff check src/

# Lint with auto-fix
uv run ruff check --fix src/

# Format
uv run ruff format src/

# Type-check
uv run mypy src/crosscontract/

# Run coverage
uv run coverage run -m pytest && uv run coverage report

# Build docs (requires docs group)
uv run mkdocs serve
```

Pre-commit hooks run `ruff check` (F401 + isort) and `ruff-format` on commit.

### Do not run validation automatically

Do **not** run tests, linting, type-checking, coverage, or any other validation
command (`pytest`, `ruff`, `mypy`, `coverage`, etc.) on your own initiative. After
making changes, stop and **ask for permission** before running any of them. Only run
a validation command when the user has explicitly asked for it or granted permission
in the current exchange.

### Implement only what was asked, as simply as possible

When handed a scoped change, implement **exactly** that change and nothing adjacent.
Acceptance criteria in a task or PRD file you happened to read, and findings from your
own earlier review, are **not** authorization — they stay open until handed over
separately. State the requested change in one line before editing, and let only that
line justify each edit; everything else you noticed goes in the reply as a note, never
into the code. If a fix seems to require adjacent work, say so and ask rather than
bundling it in.

Prefer the simplest implementation that satisfies the request. Do not add helper
functions, module constants, curated error messages, or defensive branches unless the
change cannot be expressed without them — a one-line change should land as a one-line
change. The house style is deliberately plain (pure function plus thin pydantic model,
`apply()` a single delegating call); match it. If you think an abstraction is
warranted, propose it and let the user decide.

## Branching and releases

- `main` is the public release branch. Pushes to main publish to PyPI (gated by the `pypi` GitHub Environment) and deploy the docs.
- `dev` is the integration branch and the default branch on GitHub. Versioning happens here: every push to dev runs `python-semantic-release`, which bumps the version and creates a `vX.Y.Z` tag based on conventional-commit messages.
- Feature branches **squash-merge** into `dev`. The PR title must be a valid conventional commit (`feat:`, `fix:`, etc.) — it becomes the squash commit message that PSR analyzes. Hotfixes follow the same path.
- `dev` **fast-forwards** into `main`. The version commits and tags created on dev carry over to main as-is. No version bumps happen on the dev → main promotion.

## Deferred work

`.ai-context/TODO.md` is **deprecated** — do not add to it or propose adding to it.

Do not route every out-of-scope observation into a backlog. Mention it in the reply
and let the user decide. Only when the user wants something done later does it go
into [`.ai-context/ideas/`](../.ai-context/ideas/) as a draft PRD (one file per idea,
with enough context to act on it cold).

## Architecture

The public surface — `contracts/`, `crossclient/`, and `services/` — is re-exported from `crosscontract/__init__.py`. `_standards/` is an internal module (not re-exported) holding faithful models of the upstream Frictionless standard.

### `contracts/` — The declarative layer: contracts and the specs that name them

**`contracts/contracts/`** — The contract classes:
- `BaseContract` (Pydantic model): minimal contract with `name` + `tableschema`. Intended for custom contract definitions outside the CROSS platform. Loads from YAML/JSON via `from_file()`.
- `CrossContract(BaseContract, CrossMetaData)`: the full contract for the CROSS platform, adding `title`, `description`, `tags`, and `contract_type`. The `contract_type` field (`"General"` | `"Dimension"` | `"ValueVariable"` | `"FlexibleDimension"` | `"Submission"`) drives a discriminated union: it is resolved through `CONTRACT_TYPE_TO_TABLE_TYPE` and the resulting `table_type` is injected into the `tableschema` dict before validation, so callers never set `table_type` manually.
- `CrossContract.from_server()` / `to_server()`: strip/restore the `tableschema` for `Dimension` contracts because the server owns that schema.
- `ContractResolver` protocol: used to look up contracts by name during `validate_references()`.

**`contracts/schema/`** — The schema classes:
- `TableSchema`: base Frictionless-compatible schema with `fields`, `primaryKey`, `foreignKeys`, and optional `fieldDescriptors`. Supports `__getitem__` (by index or name) and provides conversion helpers: `to_pandera_schema()`, `to_pydantic_model()`, `validate_dataframe()`.
- Discriminated union via `table_type`: `TableSchema` ("General") | `DimensionSchema` ("Dimension") | `ValueVariableSchema` ("ValueVariable") | `FlexibleDimensionSchema` ("FlexibleDimension").
- `BaseDimensionSchema` (abstract): enforces self-only foreign keys and a required primary key. Subclassed by `DimensionSchema` and `FlexibleDimensionSchema`.
- `DimensionSchema`: rigid template (id, level, parent_id, label, description). Rejects any user-provided fields.
- `FlexibleDimensionSchema`: user-defined fields, but mandates `label` and `description` fields.
- `_mandatory_fields` class variable: list of `MandatoryField` specs validated at schema construction time.
- Vendored copies of the upstream Frictionless JSON Schemas (`table-schema.json`, `data-resource.json`, `data-package.json`, `tabular-data-resource.json`) live in `.ai-context/additional_info/` — the authoritative reference for what fields, types, and constraints the schema layer must stay compatible with. Reference only; no code loads them at runtime. The `_standards/frictionless/` package (below) is a faithful pydantic mirror of these.

**`contracts/schema/adapters/`** — Converts `TableSchema` to external formats:
- `pandera_pandas/`: `PanderaAdapter` builds a `pandera.DataFrameSchema` in two halves — `create_base_schema()` for the columns, `_derive_checks()` for the checks the schema requires of its own data. `field_convertors.py` holds one converter class per field type behind the `get_field_converter` factory. Reached publicly through `TableSchema.to_pandera_schema()`; the adapter class itself is not re-exported from `contracts/schema/`.
- `PydanticAdapter`: generates a dynamic Pydantic model class.

**`contracts/schema/validation/`** — Runs a schema against a DataFrame:
- `checks/`: a check is a pydantic model holding what it needs, callable as `__call__(df) -> pd.Series`, rendering itself via `to_pandera() -> list[pa.Check]`. `base_checks.py` (`IsUnique`, `IsIn`, `IsNotIn`, `IsNotNull`, `IsSubsetOf`) names mechanics rather than meanings — what a rule means on a given schema is a `label` supplied at derivation. `reference_checks.py` (`IsValidPrimaryKey`) and `dimension_checks.py` (`IsValidCrossDimension`) are composites that unpack into one pandera check per sub-rule, so a report names the rule that broke.
- `validate_dataframe.py`: executes a `pa.DataFrameSchema` and translates pandera exceptions into `SchemaValidationError`.
- `PanderaAdapter._derive_checks` is the only place a schema becomes checks, and it takes existing values as optional arguments. **The key checks are opt-in**: `None` for `primary_key_values` / `foreign_key_values` leaves those checks out entirely, while an empty collection runs them with nothing to compare against. A `Dimension`'s hierarchy and the field constraints run either way. See ADR 0006.

**`contracts/schema/fields/`** — Field types (`IntegerField`, `NumberField`, `StringField`, `DateTimeField`, `ListField`), all discriminated by `type`. Each carries a typed `constraints` submodel (e.g. `min`/`max` for numbers, `pattern`/`maxLength` for strings).

**`contracts/submission/`** — The submission contract and its declarative specs (see ADR 0010):
- `submission_contract.py` — `SubmissionContract`: a contract whose `tableschema` describes the bundle itself, plus `project_name`, an `extraction` block, a `replace_key`, and an optional `excel_processor`. The `tableschema` must declare neither `primaryKey` nor `foreignKeys` — nothing is stored under a bundle's name, so those belong to the contracts its targets name. Field constraints are unaffected. `excel_processor` (an `ExcelProcessor` from `contracts/readers/`) is checked here: each wide sheet's `header_field` and `value_field` must be `tableschema` fields. Without it, an Excel bundle is still accepted and read from its first sheet as one long sheet.
- `extraction/` — the declarative split instructions: `Target` (which rows go to which target contract, and the transformations applied on the way) and `ExtractionInstructions` (the routing column, the reusable transformation profiles, and the targets).

**`contracts/release/`** — The release specs (see ADR 0012). `release_specification.py` holds the build-recipe models: `CrossDataResourceReleaseSpec` (per-resource descriptive overrides + a `DataInstructions` wrapping the `FetchSpecMixin`; `name` defaults to the fetch contract) and `CrossDataPackageReleaseSpec` (authored package metadata + `resources`, with a unique-resource-name validator). Both specs are re-exported from `contracts/` and the top-level package; `DataInstructions` only from `contracts/release/`.

**`contracts/readers/`** — The reader specs. `specs.py` holds `ExcelProcessor` / `ExcelSheet` / `WideLayout`: the optional declaration of an Excel bundle's sheets and which of them are laid out wide. Reached through `SubmissionContract.excel_processor`; executed by `handlers/readers/excel_reader.py`.

### `_standards/frictionless/` — Faithful, permissive Frictionless models (internal)

A pydantic mirror of the upstream Frictionless standard, distinct from the stricter `contracts/` layer: every model is `extra="allow"` and carries no CROSS domain logic, so the standard's extensibility rides through losslessly. Internal — not re-exported from the top-level package; sibling modules import from `crosscontract._standards.frictionless`.

- `fields.py` — permissive field models (`StringField`, `IntegerField`, … discriminated by `type`) with typed `constraints` submodels.
- `table_schema.py` — the permissive `TableSchema` (`fields`, `primaryKey`, `foreignKeys`, `missingValues`). Shares its bare name with the strict contract `TableSchema`; disambiguate by module.
- `metadata.py` — reusable metadata building blocks composed by the descriptors: `BaseMetaData` (fields identical in both descriptors), `ResourceMetaData` / `PackageMetaData` (descriptive parts), `FileMetaData` (the physical data binding), plus the permissive leaf models `Source`, `License`, `Contributor`. Also defines `FRICTIONLESS_NAME_PATTERN` (the resource/package `name` pattern, which permits `/`).
- `descriptors.py` — thin compositions: `DataResource(ResourceMetaData, FileMetaData)` and `DataPackage(PackageMetaData)` (adds the required `resources` array). The Frictionless `schema` key maps to a `table_schema` field (via `alias`) to avoid shadowing `BaseModel.schema`.

### `crossclient/` — HTTP client for the CROSS platform

- `CrossClient`: synchronous `httpx.Client` wrapper. Authenticates on construction (JWT Bearer token), re-authenticates automatically on 401. Exposes `client.contracts` as a `ContractService` and `client.submissions` as a `SubmissionContractService`. Use as a context manager or call `close()` explicitly.
- `services/contract/` holds `ContractService`, `ContractResource` and `CrossContractResolver`; `services/submission/` the submission counterparts below. Both are re-exported from `crossclient.services` and `crossclient`.
- `exception_factory.py` holds `raise_from_response`, which turns an error response into the matching `CrossClientError`. The exception classes themselves live in `exceptions/`.
- `ContractService`: CRUD operations on contracts (`create`, `get`, `get_list`, `delete`, `change_status`). Also manages data upload (`_add_data`) and retrieval (`_get_data` — uses parquet format).
- `ContractResource`: per-contract handle returned by the service. Wraps the `CrossContract` instance and `status`. Exposes `add_data(df)` (validates against schema before upload) and `get_data()`.
- `services/submission/` — the `/api/v1/submission` endpoints:
  - `SubmissionContractService`: `create` (POSTs, then re-`get`s, because the POST response carries no contract), `get`, `overview(project_name)` (DataFrame of the project's submission contracts), `delete`, `set_allow_submissions`, `get_submission(uuid)`, `list_submissions(name)`, and the private `_upload_submission(name, file, filename)`, which posts a bundle file unchanged (the platform reads its format from the filename extension). List endpoints are paged on the server; the service sends no `limit`, so one request returns every item.
  - `SubmissionContractResource`: per-submission-contract handle holding the `SubmissionContract`, `project_name` and `allow_submissions` (`title`/`description`/`tags` read through to the contract). Exposes `set_allow_submissions`, `delete`, `refresh`, `submissions()`, `validate_submission(df, ...)` (runs `SubmissionHandler.validate_submission` on the stored contract with a `CrossContractResolver`) and `submit(df, filename=None, validate=True)` (validates with the defaults, then uploads the bundle as delivered as parquet; `filename` is a stem, defaulting to the contract name plus a UTC timestamp).
  - `schemas.py`: `SubmissionContractEntryPayload` (the parsed read response) and `Submission` with its `SubmissionState` literal, mirroring the server's `SubmissionResponse`.

### `handlers/` — Offline execution of specs (see ADR 0011)

Runs what the specs in `contracts/submission/` and `contracts/readers/` declare: reading a delivered bundle — one wide file carrying many variables — splitting it back into per-variable contracts, and validating the result. The ingress mirror of `services/package_creator/`. Depends only on `contracts`, `transformations` and `exceptions`, and reaches the platform only through the `ContractResolver` protocol.

- `readers/` — `read_csv_file_bytes` / `read_csv_file` and `read_parquet_file_bytes` / `read_parquet_file`: a bytes core plus a path wrapper per format, taking no contract. The CSV and Excel readers follow the Frictionless default `missingValues: [""]`, shared as `NA_VALUES` in `constants.py`: `keep_default_na=False` with only the empty cell as a missing value, so any other text (the country code `"NA"`, `"null"`, `"NaN"`) stays a string. The CSV reader also requires UTF-8 and raises on bad lines. The bytes cores raise `FileReadError` for content that cannot be read; any other error, and `FileNotFoundError` from the path wrappers, propagates unchanged.
- `readers/excel_reader.py` — `read_excel_workbook_bytes(processor, field_names, data)` turns a workbook given as bytes into one long frame (a wide sheet keeps the columns in `field_names` as identifiers and melts the rest), reading with the shared NA setting so `"NA"` stays a string. With `processor=None` it reads the first sheet as one long sheet. `read_excel_bundle_bytes(contract, data)` and `read_excel_bundle(contract, filename)` delegate to it with the contract's `excel_processor` (which may be `None`) and `tableschema` field names. All raise `FileReadError` for an unreadable workbook or a layout mismatch.
- `submission_handler.py` — `SubmissionHandler`: the executor that applies a contract's extraction instructions to a delivered bundle. Extraction is `extract_target_data` / `transform_target_data` / `get_target_data` per target, plus `unclaimed_rows` for the bundle rows no target claims. Validation is `validate_target` (one target's extracted rows against the contract it names) and `validate_targets` (every target, or a named selection, collecting each failure into a `TargetValidationError` instead of stopping at the first). `validate_submission(resolver, ...)` runs the full submission validation — the bundle against its own `tableschema`, then unclaimed rows (`UnclaimedRowsError`), then every target — stopping at the first step that fails. It defaults `check_existing_primary_key` to `False`, because a submission replaces the rows stored under its `replace_key`; the other checks default to on. Target contracts arrive from the caller or through a `ContractResolver`; the handler never constructs one.

### `exceptions/` — Package-wide exceptions

Holds every exception class of the package, all exported from `crosscontract.exceptions`. It imports nothing from the rest of the package (only pandas and pandera), so any layer can raise or catch them.

- `schema_exceptions.py` — `SchemaValidationError`, raised by `validate_dataframe`. It parses pandera's failure report into rows (`errors`, `to_list`, `to_pandas`). Its `CHECK_COLUMNS_PATTERN` reads the message format the checks in `contracts/schema/validation/checks/` write (`Columns '<cols>' in check '<label>' …`); change both together.
- `submission_exceptions.py` — `TargetValidationError` (the aggregate raised by `validate_targets`, holding one `SchemaValidationError` per failing target keyed by target name) and `UnclaimedRowsError` (raised when a bundle holds rows no target claims, carrying those rows).
- `reader_exceptions.py` — `FileReadError`, raised by every file reader (CSV, parquet, Excel) for content that cannot be read in its format or a workbook that does not match its Excel layout. The message is the user-facing text.
- `client_exceptions.py` — the `CrossClientError` family (`ValidationError`, `RequestValidationError`, `UnprocessableEntityError`, `AuthenticationError`, `PermissionDeniedError`, `ResourceNotFoundError`, `ServerError`, `ConflictError`), raised by `raise_from_response` in `crossclient/`.

### `services/` — High-level layer over the CROSS platform

One subpackage per job a user does on the platform, each standing on a `CrossClient` (the package creator through a `CrossReader`): reading data, submitting it, and building a data package. `services/__init__.py` exports `CrossReader`, `CrossRegistry`, `CrossSubmitter` and `create_data_package`; the root re-exports the three classes but not `create_data_package`. Each subpackage exports only its own names.

**`services/reader/`** — the data consumer's entry point:
- `CrossReader` (`reader.py`): wraps a `CrossClient`. Lazy-loads variables by name via `add_variable()` / `get_variable()`. Supports attribute access (`reader.my_variable`) and item access (`reader["my_variable"]`). Automatically resolves foreign key relationships by fetching referenced dimension contracts.
- `CrossRegistry(CrossReader)`: the former name, kept as a plain subclass. Code inside the package uses `CrossReader` only.
- `variables/` — `CrossDataVariable`: holds a fetched `ContractResource` and its resolved `CrossDimension` objects. Main entry point is `get_data()`, which supports filtering, dimension aggregation (by level, target ID list, or custom mapping), title relabeling (`use_titles=True`), and column selection. `CrossDimension`: dimension-specific variable. Exposes `label_map`, `ancestor_maps` (precomputed per-level), and `get_ancestor_map_by_ids()` for aggregation.

**`services/submitter/`** — `CrossSubmitter`: the data provider's entry point, constructed like `CrossReader`. Its methods take the name of a submission contract stored on the platform and pass through to `client.submissions.get(name)`: `validate_submission(name, df, ...)` and `submit(name, df, filename=None, validate=True)`. `submit_file(name, path, filename=None, validate=True)` reads the file with the reader for its extension (`.csv`, `.parquet`, or `.xls/.xlsx/.xlsm/.ods` through `read_excel_bundle` with the fetched contract), rejects any other extension with `ValueError`, and delegates to `submit`. A local `SubmissionContract` is validated with `SubmissionHandler(contract, df).validate_submission(resolver)` directly.

**`services/package_creator/`** — Contract → Frictionless Data Package adapter. A stateless adapter that turns CROSS contracts into a Frictionless Data Package (a zip on disk). It assembles the permissive `_standards.frictionless` `DataResource` / `DataPackage` models directly — there are no bespoke descriptor classes (see ADR 0003). The spec models come from `contracts/release/`.
- `create_data_package.py` — `create_data_package(registry, release_spec, fn_out)`: the slim orchestrator. `registry` is a `CrossReader`. Loads the spec from a YAML/JSON path (or accepts an instance), then delegates.
- `_resolve_resource.py` — `fetch_data` (fetch via the reader's trusted path), `build_data_resource` (overlay contract metadata with the spec field-by-field, embed the contract `schema`, derive `path`/`profile` from `format`), and `resolve_resources` (the per-resource loop: empty data is warned-and-skipped; an all-empty release raises).
- `_resolve_package.py` — `save_data_package`: writes each resource's data file plus `datapackage.json` and `datapackage.yaml` into the output zip.

The import graph runs one way — `constants`, `exceptions` ← `transformations` ← `contracts` ← `handlers` ← `crossclient` ← `services`. The specs live in `contracts/`, their execution in `handlers/` (submission) or `services/package_creator/` (release, which fetches through the reader), the transport in `crossclient/`, and `services/` holds the high-level entry points. Inside `services/`, `package_creator/` imports `reader/`. `exceptions/`, like `constants`, is a base: it imports nothing from the rest of the package. Never import `services/` from any other package (only the root `__init__.py` re-exports it), never import `crossclient/` from `handlers/`, and never import any other package from `exceptions/`.

### `_helpers/` — Internal, dependency-free helpers

Not re-exported from the top-level package. `_pydantic.py` holds reusable pydantic types (`OptionalNonEmptyList`, which collapses `[]`→`None` for Frictionless `minItems: 1` optional arrays); `_io.py` holds `read_yaml_or_json_file` and `dump_to_file`.

### Key design patterns

- **Discriminated unions**: `contract_type` on `CrossContract` selects the schema's `table_type` via the `CONTRACT_TYPE_TO_TABLE_TYPE` table in `contracts/contracts/cross_contract.py`. The mapping is **not** the identity: `Submission` resolves to the `General` table type, because a submission bundle needs its own contract type but not its own schema. The two vocabularies are deliberately separate so several contract types can share one schema — never assume the two strings are equal, and never add an empty schema class just to give a contract type a discriminator target. The `_inject_table_type` validator bridges them automatically.
- **Adapters are stateless class methods**: call `Adapter.convert_schema(schema, ...)` directly; the adapter pattern exists for extensibility but doesn't require instantiation in practice.
- **Two `name` patterns, deliberately distinct**: `CONTRACT_NAME_PATTERN` (in the dependency-free `constants.py`, so every package can import it) is the strict contract/field identifier — no `/`; `FRICTIONLESS_NAME_PATTERN` (in `_standards/frictionless/metadata.py`) is the looser standard resource/package identifier that permits `/`. The contract pattern is a subset, so any contract name is also a valid Frictionless name.
- **Two packages named `submission`**: `crosscontract.contracts.submission` holds the declarative specs (`SubmissionContract`, `ExtractionInstructions`, `Target`), executed offline by `SubmissionHandler` in `crosscontract.handlers`; `crosscontract.crossclient.services.submission` the HTTP transport (`SubmissionContractService`, `SubmissionContractResource`, `Submission`). The high-level `CrossSubmitter` lives in `crosscontract.services.submitter`. Name the full path when referring to any of them.
- **Two packages named `services`**: `crosscontract.crossclient.services` is the transport (`ContractService`, `SubmissionContractService` and their resources, reached as `client.contracts` / `client.submissions`); `crosscontract.services` is the high-level layer (`CrossReader`, `CrossSubmitter`, `create_data_package`). Name the full path when referring to either.
- **Tests live in `src/tests/`**, mirroring the `src/crosscontract/` structure. `pythonpath = "src"` in `pyproject.toml` means imports use `from crosscontract import ...` without editable install, though the package should be installed via `uv sync`.

## Docstring convention

All Python docstrings in this package use **Google style** (rendered by mkdocs via mkdocstrings). **Markdown formatting only** — single-backtick `code`, dashes for bullet lists, and **no reStructuredText syntax of any kind**: no ``double-backtick literals``, no `:param:` / `:returns:` / `:raises:` field markers, no `:attr:` / `:class:` / `:meth:` / `:func:` roles, no rST directives.

**Every docstring** carries `Args:`, `Returns:`, and `Raises:` sections — each when applicable (e.g. no `Returns:` on `__init__`, no `Args:` on a no-argument method) — with parameter types in parentheses, e.g. `value (str | None): ...`.

Standard sections (omit any that don't apply):

```python
def f(x: int, y: str | None = None) -> bool:
    """One-line summary in the imperative.

    Optional longer description in plain prose. Reference symbols with
    backticks, e.g. `PlotSpec`, `value_column`, `pd.DataFrame`.

    Args:
        x (int): What it is.
        y (str | None, optional): What it is. Defaults to `None`.

    Returns:
        bool: What comes back.

    Raises:
        ValueError: When and why.
    """
```

Rules of thumb:

- Docstrings are user-facing. Write what the thing does, and where a caller needs it, how to use it. Do **not** write *why it was built that way* — design rationale, rejected alternatives, comparisons to how a sibling class is built, or a justification for something the class deliberately does not have. A reader calling the code has no use for it and it obscures what they came for. Rationale belongs in commit messages, PRs, ADRs, or `.ai-context/`.
- For the same reason, do **not** reference internal notes (ADRs, issue numbers, task numbers, migration cycles) from a docstring.
- A consequence a caller must act on is *not* rationale and belongs in the docstring — e.g. "validation here is advisory; the platform re-validates on ingest" tells them their data can still be rejected. State the consequence, not the decision behind it.
- For Pydantic field descriptions, use the `Field(description=...)` argument with the same markdown conventions; no Args block on the field itself.
- For `@model_validator` / `@model_serializer` methods, document the invariant they enforce in the summary, plus `Returns:` (typically `Self`) and `Raises:` where applicable.
- Properties: document via `Returns:` rather than restating the property name.
