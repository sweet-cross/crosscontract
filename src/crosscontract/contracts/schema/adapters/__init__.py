"""Adapters take a schema and convert it to a different format.
For example, the PydanticAdapter converts a schema into a corresponding pydantic
model that allows to validate a single row of data against the schema. Likewise,
the PanderaAdapter converts a schema into a corresponding pandera schema that allows
to validate a dataframe against the schema."""
