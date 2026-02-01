# Custom Metadata

This package allow to define your own metadata standard for contracts. The implementation
of your own standard is simple and comes in two steps:

1. Create a class that defines your metadata standard
2. Create a contract based on your metadata standard.

## Create your metadata standard

To create your own standard, create a class that inherits from the `BaseMetaData` class.
The `BaseMetaData` is a pydantic model that defines only attribute, i.e., metadata entry, 
that must be implemented by all contract: the *name* attribute.

```python
from crosscontract.contracts.contracts import BaseMetaData

class MyMetaData(BaseMetaData):
    """My MetaData standard. The name attribute is already inherited from 
    BaseMetaData
    """

    description: str
    owner: str
```

## Create your contract

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
