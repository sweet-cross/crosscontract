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

## Projects

Data submitted to the CROSS platform is owned by a **project**, and a caller acts on
behalf of one project when writing or deleting data. `add_data` and `delete_data` both
accept an optional `project_name`:

```python
resource.add_data(df, project_name="my_project")
resource.delete_data(filters={"country": "US"}, project_name="my_project")
```

If you belong to exactly one project, you can omit `project_name` — the platform infers
it. If you belong to several, you must name one; omitting it raises a
`PermissionDeniedError` naming the ambiguity. Reading is not scoped this way: reads span
every project you may read, regardless of `project_name`.

## Deleting data

The `ContractResource` exposes three ways to remove data from the CROSS platform. They
cover different use cases, differ in project scope, and are not interchangeable:

| Method | Scope | Required status | Reversible? |
| --- | --- | --- | --- |
| `delete_data(filters=...)` | Rows matching the filters, within your project | `Active` | No, but other rows are preserved |
| `delete_data({}, confirm_delete_all=True)` | Every row **your project** owns under this contract | `Active` | No |
| `drop_data()` | The entire storage table, across **all** projects | `Retired` | No — all data is lost |

Use `delete_data` for routine cleanup of subsets — for example, removing all
rows for a specific country or a stale reporting year. Filters are required
and must be non-empty; values may be `str`, `int`, `float`, `bool`, or a list
of any of these (a list produces a multi-value equality match):

```python
resource = client.contracts.get("my_contract")
resource.delete_data(filters={"country": "US"})
resource.delete_data(filters={"year": [2019, 2020]})
```

To clear every row your project owns under a contract without dropping the table,
pass `confirm_delete_all=True` alongside an empty filter mapping:

```python
resource.delete_data(filters={}, confirm_delete_all=True)
```

`confirm_delete_all` exists because an empty `filters` mapping is exactly the value a
bug produces — for example, a dict comprehension over user input where every value
happened to filter out. Treating `{}` alone as "delete everything" would make that bug
indistinguishable from intent, so the empty-mapping form is rejected unless
`confirm_delete_all=True` is passed explicitly.

Passing both is allowed, and filters win: `confirm_delete_all` governs the empty-filter
case only, so `delete_data(filters={"country": "US"}, confirm_delete_all=True)` removes
the US rows and nothing else.

Use `drop_data` only as part of contract decommissioning, and only if you are an
administrator: the contract must already have been transitioned to `Retired`, and the
entire data table — every project's rows, not only yours — is discarded.

See the [API reference](../reference/client.md) for full signatures.
