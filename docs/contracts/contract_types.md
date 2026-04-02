# Contract Types

*CrossContracts* know different contract types. Their main purpose is to be able
to enforce the CROSS data model and to facilitate operations on the data like, e.g.,
automatic plotting. The different contract types share the same metadata differ
however in additional requirements and checks for data schema.

In short the CROSS data model is organized as a Kimball star schema. Dimensions such
as countries, generation technologies, or economic sectors are
organized as hierarchies with various sub-levels. Dimensions must not contain foreign
key references to other resources or other dimensions; only self-references within the
same dimension table (for hierarchy, e.g., `parent_id -> id`) are allowed. The actual
data are provided in fact tables that are characterized by one or more column that
contain the numerical values and a set of columns that reference the dimensions. We
therefore differentiate between three main types of contracts:

- *General*: This is the most flexible type. The schema to describe the data is the
 [standard table schema](schema.md)
- *Dimensions*: The dimensions contract is the most rigid form of a contract as dimensions
are highly standardized. This results in a contract that allows the user to only provide
meta-data but the schema of the data is automatically provided.
- *ValueVariable*: The value variable contract, corresponds to what is more commonly
  known as Fact table in data modeling.


## Dimension contracts

The `contract_type` *Dimension* indicates the Dimension contract. It follows the
standard CROSS metadata but is characterized by a highly standardized data schema
and additional data checks that ensure that the hierarchy implemented by the dimension
is meaningful.

The data schema for dimensions narrows the base [`TableSchema`](schema.md)
by adding specific constraints and conventions for dimension tables.

Dimensions have the following fields:

- "id":
    - A unique identifier for each entry in the dimension table.
    - required
    - Type: string (max length 100 characters). Only lower case letters, numbers
        and underscores are allowed. It must start with a lower case letter.
    - Constraints: Must be unique across the entire table and serves as the
                    primary key.
- "parent_id":
    - A reference to the "id" of the parent entry in the same table
    - optional (required for levels > 0)
    - Type: string (max length 100 characters)
- "level":
    - Indicates the hierarchy level of the dimension, starting at 0 for the top level.
    - required
    - Type: integer (non-negative, >= 0)
- "label":
    - A human-readable label for the dimension entry. This is the default fallback
        label for plotting etc purposes if no other label is provided.
    - optional
    - Type: string (max length 255 characters)
- "description":
    - A detailed description of the dimension entry.
    - optional
    - Type: string

At the data level, dimensions receive more checks to ensure the hierarchy is
consistent and valid.

1. At level 0, no parent_id can be provided
2. A row at level N (N > 0) must reference a parent at level N-1
3. Each row at level N (N > 0) must have a parent_id
4. The root level of the dimension hierarchy should have an entry with id "other".
    Each sub-level should have a sibling entry with id "other_<parent_id>" to
    capture uncategorized entries at that level.

