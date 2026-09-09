# Contract Types

*CrossContracts* know different contract types. Their main purpose is to be able
to enforce the CROSS data model and to facilitate operations on the data (e.g.,
automatic plotting). The different contract types share the same metadata. The however,
differ by having additional requirements on schema and additional checks for the
data schema.

In short the CROSS data model is organized as a Kimball star schema. Dimensions such
as countries, generation technologies, or economic sectors are
organized as hierarchies with various sub-levels. Dimensions must not contain foreign
key references to other resources or other dimensions; only self-references within the
same dimension table (for hierarchy, e.g., `parent_id -> id`) are allowed. The actual
data are provided in fact tables that are characterized by one or more columns holding
numerical values, plus the columns that identify the row — typically references to
dimensions, but not necessarily so (see `unit` below). We differentiate between the
following types of contracts:

- *General*: This is the most flexible type. The schema to describe the data is the
 [standard table schema](schema.md)
- *Dimension* and *FlexibleDimension*: The dimension contracts are the most rigid form
of a contract as dimensions are highly standardized. For *Dimension* this results in a
contract that allows the user to only provide meta-data but the schema of the data is
automatically provided.
- *ValueVariable*: The value variable contract, corresponds to what is more commonly
  known as Fact table in data modeling.
- *Submission*: A contract describing a delivered bundle — one file carrying rows for
many datasets at once — together with the instructions for splitting it back into the
contracts it feeds. It uses the standard table schema.


## Dimension contracts

Dimensions are contracts that are meant to be referenced. They are primarily used
to enforce **Star Schema** requirements. A Star Schema consists of fact and dimension
tables. The start nature is enforced by the requirements that

- Fact tables can only reference dimensions
- Dimensions cannot reference other dimensions

To facilitate this kind of data modeling, CrossContract have dimension contracts
that come in two ways. `Dimension` and `FlexibleDimension`. They follow the
standard CROSS metadata but are characterized by additional requirements:

1. It must have a primary key. The primary key can be a single field or a composite
of several fields.
2. There are no foreign key references except to the table itself (self-reference).

The `FlexibleDimension` contract puts the further requirement that the schema must
have a *label* and a *description* field both of type string.

The `Dimension` contract is more rigid and is the standard way to implement hierarchical
dimensions. It implements additional data checks that ensure that the hierarchy
implemented by the dimension is meaningful.

The data schema for `Dimension` narrows the base [`TableSchema`](schema.md)
by adding specific constraints and conventions for dimension tables.

Dimensions have the following fields:

| Field | Required | Data Type | Description & Constraints |
| :--- | :--- | :--- | :--- |
| `id` | Yes | String (max 100 chars) | A unique identifier for each entry in the dimension table. Only letters (a-z, A-Z), numbers, and underscores are allowed. Must start with a letter. <br><br>**Constraint:** Must be unique across the entire table and serves as the primary key. |
| `parent_id` | Optional* <br>*\* Required for levels > 0* | String (max 100 chars) | A reference to the `id` of the parent entry in the same table.|
| `level` | Yes | Integer (>= 0) | Indicates the hierarchy level of the dimension, starting at `0` for the top level. |
| `label` | Optional | String (max 255 chars) | A human-readable label for the dimension entry. This is the default fallback label for plotting and other purposes if no other label is provided. |
| `description` | Optional | String | A detailed description of the dimension entry. |
| `color` | Optional | String | A hex color that can be used for plotting in stacked bar charts. |

At the data level, dimensions receive more checks to ensure the hierarchy is
consistent and valid.

1. At level 0, no parent_id can be provided
2. A row at level N (N > 0) must reference a parent at level N-1
3. Each row at level N (N > 0) must have a parent_id
4. The root level of the dimension hierarchy must have an entry with id "other".
    Each sub-level must have a sibling entry with id "<parent_id>_other" to
    capture uncategorized entries at that level.

## ValueVariable contracts

A `ValueVariable` is the fact table of the star schema: a primary key that identifies
the row, plus one or more numeric measures. Every field is one or the other, which the
schema enforces at load time with three rules:

1. The schema must declare a non-empty primary key. It can be a single field or a
composite of several fields.
2. At least one field must lie outside that primary key.
3. Every field outside the primary key must be of type `integer` or `number`.

Unlike a `Dimension`, a `ValueVariable` schema is authored in full — nothing is
generated for you.

### Where non-numeric columns go

Rule 3 is the one that requires a decision when authoring a contract. A non-numeric
column has to be part of the row's identity, or it does not belong in the contract:

| Column | Where it belongs | Why |
| :--- | :--- | :--- |
| `country`, `scenario` | Primary key | They identify the observation. |
| `year` | Primary key | Numeric types are allowed inside the key as well. |
| `unit` | Primary key | The same quantity may be delivered in two units, and those are two rows rather than a conflict. |
| `value`, `capacity` | Outside the key | These are the measures. |
| A description of the dataset as a whole | Contract metadata | It does not vary by row. |

Note the consequence for `unit` in particular: with `unit` *outside* the key, a contract
cannot accept the same country/year in two units — the second row is a duplicate primary
key. Putting it in the key removes a restriction rather than adding one.

### Key columns are not necessarily dimensions

A `ValueVariable` is not required to declare any foreign key, and a key column need not
reference a dimension — `unit` is the common example. Being in the primary key therefore
does **not** mean a column is an axis you may aggregate over: summing across `unit` is
meaningless in a way that summing across `country` is not. Code that aggregates has to
know which of the key columns are dimension references; the schema does not say.

