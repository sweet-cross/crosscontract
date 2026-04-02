from typing import Any, Literal

from pydantic import Field, model_validator

from ..schema import TableSchema

ID_PATTERN = r"^[a-z][a-z0-9_]*$"

DIMENSION_SCHEMA_TEMPLATE = {
    "primaryKey": ["id"],
    "foreignKeys": [{"fields": ["parent_id"], "reference": {"fields": ["id"]}}],
    "fields": [
        {
            "name": "id",
            "type": "string",
            "description": (
                "Unique name of the element (only lowercase letters, numbers, "
                "and underscores; must start with a letter). "
            ),
            "constraints": {
                "required": True,
                "maxLength": 100,
                # as we have a single id as primary key, it must be unique across
                # the entire table
                "unique": True,
                "pattern": ID_PATTERN,
            },
        },
        {
            "name": "level",
            "type": "integer",
            "title": "Hierarchical level",
            "description": "The level within the classification hierarchy",
            "constraints": {
                "required": True,
                "minimum": 0,
            },
        },
        {
            "name": "parent_id",
            "type": "string",
            "title": "Link to parent",
            "constraints": {"maxLength": 100, "pattern": ID_PATTERN},
        },
        {
            "name": "label",
            "type": "string",
            "description": "Labels used in graphs etc. to denote the element",
            "constraints": {"maxLength": 255},
        },
        {
            "name": "description",
            "type": "string",
            "description": "Description of a single element",
        },
    ],
}


class DimensionSchema(TableSchema):
    """
    A specialized schema for dimension tables in the CrossContract system.

    This schema extends the base `TableSchema` by adding specific constraints
    and conventions for dimension tables.

    A Dimension is a hierarchical structure that organizes data into levels,
    where each level represents a different granularity of information.
    For example, a "Location" dimension might have levels for "Country", "State",
    and "City".

    Dimensions have the following fields:
    - "id":
        - required
        - Type: string (max length 100 characters)
        - Description: A unique identifier for each entry in the dimension table.
        - Constraints: Must be unique across the entire table and serves as the
                       primary key.
    - "parent_id":
        - optional (required for levels > 0)
        - Type: string (max length 100 characters)
        - Description: A reference to the "id" of the parent entry in the same table
    - "level":
        - required
        - Type: integer (non-negative, >= 0)
        - Description: Indicates the hierarchy level of the dimension, starting at 0
                       for the top level.
    - "label":
        - optional
        - Type: string (max length 255 characters)
        - Description: A human-readable label for the dimension entry.
                       This is the default fallback label for plotting etc.
                       purposes if no other label is provided.
    - "description":
        - optional
        - Type: string
        - Description: A detailed description of the dimension entry.

    At the data level, dimensions receive more checks to ensure the hierarchy is
    consistent and valid.

    1. At level 0, no parent_id can be provided
    2. A row at level N (N > 0) must reference a parent at level N-1
    3. Each row at level N (N > 0) must have a parent_id
    4. The root level of the dimension hierarchy should have an entry with id "other".
       Each sub-level should have a sibling entry with id "other_<parent_id>" to
       capture uncategorized entries at that level.
    """

    # ignore type error as we want to enforce the table_type for this schema
    # for the pydantic discriminator to work correctly
    table_type: Literal["Dimension"] = Field(  # type: ignore[assignment]
        default="Dimension",
        description="Type of the table determines the structure of the schema.",
        exclude=True,
        repr=False,
    )

    @model_validator(mode="before")
    @classmethod
    def _inject_dimension_template(cls, data: Any) -> Any:
        """
        If the user provides an empty dict (or minimal data),
        we automatically merge the template into it before Pydantic parses it.
        """
        # 1. If it's garbage (list, string, etc.), pass it down so Pydantic
        # can throw a standard ValidationError. (Pydantic already intercepted valid
        # instances).
        if not isinstance(data, dict):
            return data

        # custom data can only be the table_type, which is set to "Dimension"
        # by default, so we check for any other keys and reject them to avoid
        # confusion about where to put metadata
        user_provided_keys = set(data.keys()) - {"table_type"}
        if user_provided_keys:
            raise ValueError(
                f"DimensionSchema is rigidly defined and cannot accept custom data. "
                f"Found restricted keys: {', '.join(user_provided_keys)}. "
                "Please put all metadata (title, description, etc.) on the "
                "Contract level."
            )
        return {**DIMENSION_SCHEMA_TEMPLATE}
