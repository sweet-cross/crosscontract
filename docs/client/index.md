# CrossClient

The CrossClient facilitates interaction with the CROSS data platform with your
Python routines. It allows to create and retrieve CrossContracts on/from the platform.
It further allows to submit and validate data to the platform.

To use CrossClient you must be a registered user of the platform. You can register
your account here: [Register User](https://sweet-cross.ch/register).


## Overview

The basic idea behind CrossClient is simple. It uses the API endpoints of the platform
to conveniently interact with it. It follows a resource-oriented design with three
main components:
- **CrossClient** The basic client to connect with the API. It handles authentication
and basic configurations.
- **Service** The service layer allows management of the basic objects. Most notably, the
`ContractService` allows to create, retrieve, and delete CrossContracts.
- **Resource** A resource is your local representation of an object stored at the CROSS
platform. The `ContractResource` is the representation of a CrossContract retrieved from
the platform. It allows to inspect and manipulate the contract and to
validate local data against the contract. Moreover, it allows to submit and retrieve
data associated with the contract and saved at the CROSS platform.

The [tutorial](../notebooks/client_tutorial.ipynb) provides another overview of these basic principles with a code example.

## Deleting data

The `ContractResource` exposes two distinct methods for removing data from the
CROSS platform. They cover different use cases and are not interchangeable:

| Method | Scope | Required status | Reversible? |
| --- | --- | --- | --- |
| `delete_data(filters=...)` | Deletes rows matching the given equality filters | `Active` | No, but other rows are preserved |
| `drop_data()` | Drops the entire storage table backing the contract | `Retired` | No — all data is lost |

Use `delete_data` for routine cleanup of subsets — for example, removing all
rows for a specific country or a stale reporting year. Filters are required
and must be non-empty; values may be `str`, `int`, `float`, `bool`, or a list
of any of these (a list produces a multi-value equality match):

```python
resource = client.contracts.get("my_contract")
resource.delete_data(filters={"country": "US"})
resource.delete_data(filters={"year": [2019, 2020]})
```

Use `drop_data` only as part of contract decommissioning: the contract must
already have been transitioned to `Retired`, and the entire data table is
discarded.

See the [API reference](../reference/client.md) for full signatures.
