from typing import Annotated, Any, Literal

from pydantic import ConfigDict, Field, model_validator

from ..schema import DimensionSchema, TableSchema, ValueVariableSchema  # noqa: F401
from .base_contract import BaseContract, BaseMetaData

AnyTableSchema = Annotated[
    TableSchema | DimensionSchema | ValueVariableSchema,
    Field(discriminator="table_type"),
]


class CrossMetaData(BaseMetaData):
    """
    Metadata specific to the CrossContract system,
    extending the base metadata requirements

    Attributes:
        title (str): A human-readable title for the data.
        description (str): A human-readable description of the data.
        tags (list[str] | None): A list of tags for categorization and filtering.
    """

    model_config = ConfigDict(str_strip_whitespace=True)
    title: str = Field(
        description=(
            "A human-readable title for the data."
            "Think of this as the label that will be used in graphs and tables."
        ),
    )

    description: str = Field(
        description=(
            "A human-readable description of the data. This should explain what "
            " the data is about."
        )
    )

    tags: list[str] = Field(
        default_factory=list,
        description=(
            "A list of tags that can be used to categorize the table. "
            "This can be used to filter tables in the UI."
        ),
    )


class CrossContract(BaseContract, CrossMetaData):
    """
    A concrete implementation of a data contract for the CrossContract system.

    This class extends `BaseContract` by adding tagging capabilities.
    It serves as the standard contract definition for resources within the
    CrossContract ecosystem.

    Attributes:
        name (str): A unique identifier for the data contract.
            Must contain only alphanumeric characters, underscores, or hyphens.
            Inherited from BaseContract.
        title (str): A human-readable title for the data.
        description (str): A human-readable description of the data.
        tags (list[str] | None): A list of tags used for categorization and filtering.
        tableschema (Schema): The Frictionless Table Schema definition.
            Accessible via the `tableschema` property as well.
            This is the core schema definition that describes the structure of the data,
            including fields, types, and constraints. It changes based on the contract
            type (e.g., Table, Dimension, ValueVariable).
    """

    model_config = ConfigDict(
        populate_by_name=True,
        extra="forbid",
        serialize_by_alias=True,
    )

    contract_type: Literal["General", "Dimension", "ValueVariable"] = Field(
        default="General",
        description=(
            "The type of the contract, which determines the structure of the "
            "tableschema."
        ),
    )
    tableschema: AnyTableSchema = Field(
        description="The Frictionless Table Schema definition."
    )

    @model_validator(mode="before")
    @classmethod
    def _inject_table_type(cls, data: Any) -> Any:
        """We inject the table_type into the tableschema based on the contract_type
        Generally, the table schema name is the same as the contract type,
        but we want to keep them separate in case we want to have multiple contract
        types based on the same schema.

        The injection is necessary because the tableschema uses the table_type
        as a discriminator to determine which schema to use, and we want to avoid
        requiring the user to manually specify it."""
        # check the input type as we need a dictionary
        # 1. If Pydantic is re-validating an already built CrossContract, let it pass
        # -> not needed pydantic 2.0 automatically bypasses before validators on
        # already validated instances, but we keep it here for clarity and to
        # ensure it works as expected
        if isinstance(data, cls):
            return data  # pragma: no cover - this is just a safety check

        # 2. Fail fast if the user passes an unsupported object (like an ORM model)
        if not isinstance(data, dict):
            raise TypeError(
                f"CrossContract must be initialized with a dictionary or keyword "
                f"arguments, got {type(data).__name__}."
            )

        return cls._inject_table_type_to_schema(data)

    @staticmethod
    def _inject_table_type_to_schema(data: dict[str, Any]) -> dict[str, Any]:
        """Helper method to inject the table_type into the tableschema.

        Args:
            data (dict[str, Any]): The input data dictionary to be processed.

        Returns:
            dict[str, Any]: The processed data dictionary with the table_type injected.
        """
        contr_type = data.get("contract_type", "General")
        schema_data = data.get("tableschema")

        # check existence and type of tableschema before proceeding
        if not schema_data:
            raise ValueError("The 'tableschema' field is required")
        if isinstance(schema_data, TableSchema):
            if schema_data.table_type != contr_type:
                raise ValueError(
                    f"Mismatch between contract_type '{contr_type}' and "
                    f"tableschema.table_type '{schema_data.table_type}'."
                )
            # If it's already a TableSchema instance, we can skip injection
            return data
        if not isinstance(schema_data, dict):
            raise TypeError(
                f"Expected 'tableschema' to be a dictionary, got "
                f"{type(schema_data).__name__}."
            )

        # Fail fast if the user tries to be too clever and provides a table_type
        # in the tableschema
        if "table_type" in schema_data:
            raise ValueError(
                "Do not define 'table_type' inside the tableschema. "
                "It is automatically inferred from the root contract level."
            )

        # insert the table_type into the tableschema for the discriminator
        schema_copy = dict(schema_data)
        schema_copy["table_type"] = contr_type

        # add the new schema back into the data
        data_copy = dict(data)
        data_copy["tableschema"] = schema_copy
        return data_copy
