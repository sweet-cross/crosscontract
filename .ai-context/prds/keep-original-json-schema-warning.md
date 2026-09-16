# `KEEP_ORIGINAL` breaks JSON schema generation — problem and fix

Status: **proposed**, not implemented. Written 2026-09-16, from a finding in `cross_back`
while adding a route whose request body is a `SubmissionContract`.

---

## The problem

`MapColumnValues.default_value` defaults to the module-level sentinel
`KEEP_ORIGINAL = object()`
([`column_transformations.py`](../../src/crosscontract/transformations/transformation/column_transformations.py)).
Pydantic copies a field's default into the generated JSON schema, and a bare `object()`
has no JSON form, so every schema generation that reaches this model emits:

```
PydanticJsonSchemaWarning: Default value <object object at 0x…> is not JSON serializable;
excluding default from JSON schema [non-serializable-default]
```

The schema is still produced — the default is simply left out, which is the right
outcome — but the warning fires every time.

### Where it surfaces

Any consumer that generates a JSON schema for a contract containing transformations. The
concrete case: `cross_back` declares a FastAPI route whose body is `SubmissionContract`,
so building the OpenAPI document warns. That document is built on every `/docs` request
and in the app's schema tests, where the warning shows up in the test summary of a
suite that is otherwise clean:

```
backend/tests/maintenance/test_route.py::TestSchemaVisibility::test_visibility_follows_the_environment
  pydantic/json_schema.py:2448: PydanticJsonSchemaWarning: Default value <object object …>
```

Consumers can only silence it globally (a `filterwarnings` entry), which would also
hide genuine non-serializable defaults introduced later.

### What is already correct

Serialization was solved deliberately and needs no change: the field carries
`exclude=True`, and the `_restore_default_value` wrap serializer re-adds
`default_value` only when it holds a real value. An omitted key on reload means "keep the
original values", which round-trips through `model_dump` / `model_validate`. The problem
is confined to the **schema**, where the default is read off the field itself and never
passes through a serializer.

## Requirements

- Generating a JSON schema for `MapColumnValues` — alone or nested in a contract — emits
  no warning.
- `KEEP_ORIGINAL` stays the default: `MapColumnValues(column_name=…, mapping=…)`
  keeps unmapped values unchanged, and `spec.default_value is KEEP_ORIGINAL` still holds.
- Serialization is unchanged: the key is omitted for the sentinel and present for every
  real value, including `None`.
- The public API does not change: `KEEP_ORIGINAL` keeps its identity semantics, so
  `default_value is KEEP_ORIGINAL` comparisons in client code keep working.

## Options considered

| Option | Warning gone | API impact |
|---|---|---|
| **A. `default_factory` returning the sentinel** | yes | none |
| B. `json_schema_extra` stripping `default` | **no** — the warning fires before the hook runs | none |
| C. `Annotated[Any, WithJsonSchema(...)]` | **no** — same reason | none |
| D. Replace the sentinel with a marker string (`"__keep_original__"`) | **no** — it is a valid default value in its own right, so a user could pass it by accident, and the field default still lands in the schema | breaking |

Verified against pydantic 2.12 by generating `model_json_schema()` for each variant and
counting warnings.

## Proposed fix (option A)

```python
default_value: Any = Field(
    default_factory=lambda: KEEP_ORIGINAL,
    exclude=True,
    description=...,  # unchanged
)
```

Pydantic does not put a `default_factory` result into the JSON schema — it cannot call the
factory during schema generation — so the non-serializable default never reaches the
encoder. The produced schema is byte-for-byte what it is today (the default was being
dropped anyway), the factory returns the same singleton, so identity comparisons are
unaffected, and the wrap serializer keeps working untouched.

The comment above the field should say why the factory is there, otherwise the next
reader will "simplify" it back to `default=KEEP_ORIGINAL`.

## Testing

- Extend `src/tests/transformations/transformation/test_column_transformations.py`:
  - `MapColumnValues.model_json_schema()` produces no `PydanticJsonSchemaWarning`
    (`warnings.catch_warnings(record=True)` plus `simplefilter("always")`), and the same
    for a contract that embeds a transformation, which is the shape consumers hit;
  - `MapColumnValues(column_name=…, mapping=…).default_value is KEEP_ORIGINAL`, pinning
    the identity the factory must preserve.
- The existing round-trip and apply tests cover the rest and must stay green unchanged.

## Out of scope

- The sentinel pattern itself. It is the right shape here: `None` is a legitimate default
  value, so "no default given" needs a value of its own.
- Any change to serialization or to the YAML authoring format.
