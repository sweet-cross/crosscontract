# Metadata

## CROSS Metadata

The CROSS metadata are the metadata standard defined for CrossContracts. They
follow the [Frictionless Data](https://specs.frictionlessdata.io/) vocabulary
(with a few deliberate departures, see below). A
[DCAT-CH](https://www.dcat-ap.ch/) / [DCAT-AP](https://op.europa.eu/en/web/eu-vocabularies/dcat-ap)
adapter is planned for a later release.

The current CROSS metadata include

| Attribute | Type | Required | Description |
|-----------|------|----------|-------------|
| `name` | `str` | Yes | Unique identifier for the data contract. Must be a Frictionless-compliant identifier: lowercase letters, digits, `.`, `_`, and `-` only (no uppercase, no `/`), max 100 characters. |
| `title` | `str` | Yes | A human-readable title for the data. Think of this as the label that will be used in graphs and tables. |
| `description` | `str` | Yes | A human-readable description of the data. This should explain what the data contain. It gives the data a semantic meaning. |
| `tags` | `list[str]` | No | A list of tags that can be used to categorize the table.  Defaults to an empty list. |
| `contributors` | `list[Contributor] \| None` | No | The people or organizations who contributed to the data contract. Defaults to `None`. |
| `sources` | `list[DataSource] \| None` | No | The raw data sources the data is derived from. Defaults to `None`. |
| `licenses` | `list[License] \| None` | No | The license(s) under which the **data** associated with the contract is published. Defaults to `None`. |
| `contract_type` | `str` | No | The type of the contract. Either *Dimension*, *ValueVariable*, *FlexibleDimension* or *General* |

For more information on contract types, see the [separate section](contract_types.md).

## Provenance and licensing metadata

The `contributors`, `sources`, and `licenses` fields capture provenance and
licensing information. They follow the
[Frictionless Data](https://specs.frictionlessdata.io/) vocabulary, with a few
deliberate departures described below.

### Contributors

A `Contributor` records a person or organization involved in the contract.

| Attribute | Type | Required | Description |
|-----------|------|----------|-------------|
| `title` | `str` | Yes | The name of the contributor. |
| `email` | `str \| None` | No | The email of the contributor. |
| `path` | `str \| None` | No | A URL to the contributor's profile or homepage. |
| `role` | `str` | No | One of `author`, `maintainer`, `contributor`. Defaults to `contributor`. |
| `organization` | `str \| None` | No | The organization the contributor is affiliated with. |

```python
from crosscontract.contracts.contracts.metadata_models import Contributor

Contributor(
    title="Jane Doe",
    email="jane.doe@example.com",
    role="author",
    organization="Example Office of Statistics",
)
```

### Sources

A `DataSource` records a raw source the data is derived from.

| Attribute | Type | Required | Description |
|-----------|------|----------|-------------|
| `title` | `str` | Yes | The name of the data source. |
| `path` | `str \| None` | No | A URL or file path to the data source. |
| `email` | `str \| None` | No | The email of the data source contact. |

```python
from crosscontract.contracts.contracts.metadata_models import DataSource

DataSource(
    title="World Bank and OECD",
    path="https://data.worldbank.org/indicator/NY.GDP.MKTP.CD",
)
```

### Licenses

A `License` records the terms under which the **data** is published. A license
object must define at least a `name` or a `path`.

| Attribute | Type | Required | Description |
|-----------|------|----------|-------------|
| `name` | `str \| None` | Conditional | An [Open Definition](http://licenses.opendefinition.org/) license identifier, e.g. `CC-BY-4.0`. |
| `path` | `str \| None` | Conditional | A fully qualified URL, or a POSIX file path to the license text. |
| `title` | `str \| None` | No | A human-readable title for the license. |

```python
from crosscontract.contracts.contracts.metadata_models import License

License(
    name="CC-BY-4.0",
    path="https://creativecommons.org/licenses/by/4.0/",
    title="Creative Commons Attribution 4.0",
)
```

### Relationship to the Frictionless standard

These fields stay close to the Frictionless vocabulary but differ on purpose:

- **Resource-level scope.** In Frictionless, `contributors` lives at the
  *data package* level (and `sources`/`licenses` at both package and resource
  level). CrossContract attaches all three at the **contract (resource) level**
  so each contract can carry its own provenance and licensing.
- **`licenses` describes the data, not the contract.** The license applies to
  the data associated with the contract, not to the contract document itself.
  As in Frictionless, this metadata is informational and not legally binding.
- **Narrower `role` set.** `role` is restricted to `author`, `maintainer`, and
  `contributor` (Frictionless also allows `publisher` and `wrangler`).
- **No extra fields.** `Contributor`, `DataSource`, and `License` reject
  unknown keys, so a misspelled attribute fails validation rather than being
  silently dropped.
- **Empty lists are treated as absent.** Passing `[]` for `contributors`,
  `sources`, or `licenses` is normalized to `None`, so the field is omitted from
  serialized output rather than emitted as an (invalid) empty array.

## Custom Metadata

This package allow to define your own metadata standard for contracts. The implementation
of your own standard is simple and comes in two steps:

1. Create a class that defines your metadata standard
2. Create a contract based on your metadata standard.

### Create your metadata standard

To create your own standard, create a class that inherits from the `BaseMetaData` class.
The `BaseMetaData` is a pydantic model that defines only attribute, i.e., metadata entry,
that must be implemented by all contract: the *name* attribute. The *name* must be a
Frictionless-compliant identifier (lowercase letters, digits, `.`, `_`, and `-`; no
uppercase or `/`), so contracts stay release-compliant by construction.

``` py
from crosscontract.contracts.contracts import BaseMetaData

class MyMetaData(BaseMetaData):
    """My MetaData standard. The name attribute is already inherited from
    BaseMetaData
    """

    description: str
    owner: str
```

### Create your contract

In the second step you create your contract class that inherits from `BaseContract`
and your created `MyMetaData` class. While the metadata class determines the metadata,
the basic contract class enforces the frictionless schema and provides the validation
functionalities:

```python
from crosscontract.contracts import BaseContract

class MyContract(BaseContract, MyMetaData):
    """A custom contract blueprint with custom metadata"""
    pass
```

That's it. You now have an contract blueprint `MyContract` that enforces that each
contract must have a name, description, and owner attribute and, in addition, a
tableschema entry that enforces the frictionless table schema.
