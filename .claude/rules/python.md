---
paths:
  - "**/*.py"
---

# Python conventions

These apply to **all** Python code in this repository, application and tests alike.

## Code

- **Type hints** are mandatory everywhere, including test functions (`-> None`) and
  fixtures. Use builtin generics and PEP 604 unions: `list[str]`, `dict[str, Any]`,
  `X | None` — not `List`, `Dict`, `Optional`. mypy does not check `src/tests` (nor
  `main_dev.py`), so in tests this is enforced by review only.
- **Import order**: stdlib → third-party → local.
- **Import root**: imports use `from crosscontract import ...`. `pythonpath = "src"` in
  `pyproject.toml` makes this work without an editable install, though the package
  should be installed via `uv sync`.
- **Logging**: use the standard `logging` library, never `print`. Each module logs
  through its own logger, `logger = logging.getLogger(__name__)`. This is a library:
  the package never configures handlers, formatters or levels — that is the
  application's job.
  - The one exception is the existing named logger `logging.getLogger("crossclient")`
    in `crossclient/logger.py`.

## Docstrings

Every function, method and class carries a docstring — public and private alike.
All docstrings use **Google style**, rendered by mkdocs via mkdocstrings. **Markdown
formatting only** — single-backtick `code`, dashes for bullet lists, and **no
reStructuredText syntax of any kind**: no ``double-backtick literals``, no `:param:` /
`:returns:` / `:raises:` field markers, no `:attr:` / `:class:` / `:meth:` / `:func:`
roles, no rST directives.

**Every docstring** carries `Args:`, `Returns:`, and `Raises:` sections — each when
applicable (e.g. no `Returns:` on `__init__`, no `Args:` on a no-argument method) —
with parameter types in parentheses, e.g. `value (str | None): ...`.

Standard sections (omit any that don't apply):

```python
def f(x: int, y: str | None = None) -> bool:
    """One-line summary in the imperative.

    Optional longer description in plain prose. Reference symbols with
    backticks, e.g. `CrossContract`, `value_column`, `pd.DataFrame`.

    Args:
        x (int): What it is.
        y (str | None, optional): What it is. Defaults to `None`.

    Returns:
        bool: What comes back.

    Raises:
        ValueError: When and why.
    """
```

Add an `Examples:` section

- when a caller cannot use the code correctly from the signature and summary alone:
  context managers and other objects with a lifecycle, dependencies and other pieces
  that are combined with others, and calls whose arguments interact;
- always on the public entry points — `CrossClient`, `CrossReader`, `CrossSubmitter`,
  `create_data_package` and `SubmissionHandler`: show the call and what comes back,
  including the edge case a caller must handle (`None`, the raised error).

Omit it where the signature says it all (properties, simple functions) and on private
helpers.
Put a class's usage example on the class; methods get their own only when the second
trigger above applies. Write examples as fenced `python` code blocks, not `>>>`
doctests.

Rules of thumb:

- Docstrings are user-facing. They describe **what** the code does and, where a caller
  needs it, how to use it. They do **not** explain **why** it was built that way —
  design rationale, rejected alternatives, comparisons to how a sibling class is built,
  or a justification for something the class deliberately does not have. A reader
  calling the code has no use for it and it obscures what they came for. Rationale
  belongs in code comments next to the relevant lines, in commit messages, PRs, ADRs,
  or `.ai-context/`.
- A consequence a caller must act on is *not* rationale and belongs in the docstring —
  e.g. "validation here is advisory; the platform re-validates on ingest" tells them
  their data can still be rejected. State the consequence, not the decision behind it.
- For the same reason, docstrings never reference internal notes: no documents in
  `.ai-context` (ADRs included), issue or task numbers, or migration cycles.
- Pydantic fields: document via `Field(description=...)` with the same markdown
  conventions; no `Args:` block on the field itself.
- `@model_validator` / `@model_serializer` methods: document the invariant they enforce
  in the summary, plus `Returns:` (typically `Self`) and `Raises:` where applicable.
- Properties: document via `Returns:` rather than restating the property name.
