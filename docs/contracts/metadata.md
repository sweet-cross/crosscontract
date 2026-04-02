# Metadata

## CROSS Metadata

The CROSS metadata are the metadata standard defined for CrossContracts.

<!-- They are
compliant with the [DCAT-CH v.2](https://www.dcat-ap.ch/) vocabulary which itself
is compliant with [DCAT-AC](https://op.europa.eu/en/web/eu-vocabularies/dcat-ap). -->

The current CROSS metadata include

| Attribute | Type | Required | Description |
|-----------|------|----------|-------------|
| `name` | `str` | Yes | Unique identifier for the data contract |
| `title` | `str` | Yes | A human-readable title for the data. Think of this as the label that will be used in graphs and tables. |
| `description` | `str` | Yes | A human-readable description of the data. This should explain what the data contain. It gives the data a semantic meaning. |
| `tags` | `list[str]` | No | A list of tags that can be used to categorize the table.  Defaults to an empty list. |
| `contract_type` | str | No | The type of the contract. Either *Dimension*, *ValueVariable* or *General* |

For more information on contract types, see the [separate section](contract_types.md).

## Custom Metadata

This package allow to define your own metadata standard for contracts. The implementation
of your own standard is simple and comes in two steps:

1. Create a class that defines your metadata standard
2. Create a contract based on your metadata standard.

### Create your metadata standard

To create your own standard, create a class that inherits from the `BaseMetaData` class.
The `BaseMetaData` is a pydantic model that defines only attribute, i.e., metadata entry,
that must be implemented by all contract: the *name* attribute.

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
