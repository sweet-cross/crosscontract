# refactor!: remove the SQLAlchemy adapter and the sqlalchemy dependency

## Summary
`TableSchema.to_sa_table()` and the `SQLAlchemyPostgresAdapter` behind it had no callers left. Only crosscontract's own tests used them. The CROSS backends now build their `dct_*` tables with their own column builder. Even so, every install of crosscontract pulled in `sqlalchemy`, and with it `greenlet`. This branch deletes the adapter and its public entry points, and drops `sqlalchemy` from the runtime dependencies. This is a breaking change for anyone who still calls the removed API.

## Changes
- **Removed public API**
  - `TableSchema.to_sa_table()`.
  - `convert_schema_to_sqlalchemy`, previously re-exported from `crosscontract.contracts.schema`.
  - `SQLAlchemyPostgresAdapter`, previously exported from `contracts.schema.adapters`.
- **Deleted modules**
  - `contracts/schema/adapters/sqlalchemy_adapter.py`.
  - Its test module `test_sqlaqlchemy_adapter.py`.
  - The `TestToSaTable` class in `test_schema.py`.
- **Dependencies**
  - `sqlalchemy>=2.0.45` is removed from `[project].dependencies`.
  - `uv.lock` is regenerated. The only packages that leave the lock are `sqlalchemy` and `greenlet`, since nothing else depended on either.
- **`AbstractAdapter.convert_schema`**
  - Its default body (`return cls(schema).convert(...)`) is now a bare `pass`, matching `convert()`.
  - The SQLAlchemy adapter was the only subclass that reached the old body, through `super().convert_schema(...)`. `PydanticAdapter` and `PanderaAdapter` each override `convert_schema` and never call `super()`. Without this change the line would be dead and show up as uncovered.
  - The class itself stays. It is still the base of both remaining adapters, and `PanderaAdapter` inherits its `__init__`.
  - Its docstring gains the `Args:` and `Returns:` sections the docstring convention requires.
- **Docstrings and docs**
  - SQLAlchemy mentions are removed from the `contracts/schema` module docstring and the `AbstractAdapter` docstring.
  - The `contracts/schema` module docstring now names `convert_schema_to_pydantic` as the only re-exported convenience.
  - `docs/index.md` no longer lists SQLAlchemy as a dependency.
- **Project context**
  - `.claude/CLAUDE.md` no longer lists `to_sa_table()` or the `SQLAlchemyPostgresAdapter`.
  - The docs-overhaul PRD and its issue `02-landing-and-contributing.md` drop SQLAlchemy from the dependency list the landing page must name.

## Testing
- The author reported the test suite, `ruff check` and `mypy` green after the `AbstractAdapter.convert_schema` change to `pass`.
- The `convert_schema` docstring edit came after that run and was not re-checked.
- A grep for `sqlalchemy` and `to_sa_table` across `src/`, `docs/`, `pyproject.toml`, `uv.lock`, `README.md`, `.claude/CLAUDE.md` and `.ai-context/` finds nothing.
- The CI test jobs install only `-e . --group test` and ignore the lock (#114). A leftover `sqlalchemy` import anywhere in `src/` would therefore fail them.

## Notes for reviewer
- **Release.** Removing public API is breaking, hence the `!` in the title. Because `major_on_zero = false`, the release tool bumps the version from 0.26.1 to 0.27.0, not to 1.0.0.
- **Downstream check.** I searched the local clones of every repo under `~/git` that depends on crosscontract, including `.py` files and notebooks:
  - No repo calls `to_sa_table`, `convert_schema_to_sqlalchemy` or `SQLAlchemyPostgresAdapter`.
  - `cross_back` and `cross_back_new` build their `dct_*` tables with their own `core/services/contract/data_table_columns.py`, and both declare `sqlalchemy` in their own `pyproject.toml`. Neither is affected.
- **Migration.** Anyone outside these repos who called `to_sa_table()` has to build the table themselves. The backend's `data_table_columns.py` shows how. The removed method added a surrogate `_id` integer primary key, and used `dct_<name>` as the default table name.
- **Left unchanged.** `CHANGELOG.md` and `.github/PRs/clean_dependencies.md` still mention SQLAlchemy. Both are history, so they stay as written.

BREAKING CHANGE: `TableSchema.to_sa_table()`, `convert_schema_to_sqlalchemy` and `SQLAlchemyPostgresAdapter` are removed, and `sqlalchemy` is no longer installed with crosscontract.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
