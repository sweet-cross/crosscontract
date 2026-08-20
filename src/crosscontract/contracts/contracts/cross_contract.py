from typing import Annotated, Any, Literal

from pydantic import ConfigDict, Field, model_validator

from ..._helpers import OptionalNonEmptyList
from ..schema import (
    DimensionSchema,
    FlexibleDimensionSchema,
    TableSchema,
    ValueVariableSchema,
)
from .base_contract import BaseContract, BaseMetaData
from .metadata_models import Contributor, License, Source
from .resolvers import ContractResolver

AnyTableSchema = Annotated[
    TableSchema | DimensionSchema | ValueVariableSchema | FlexibleDimensionSchema,
    Field(discriminator="table_type"),
]

ContractType = Literal[
    "General", "Dimension", "ValueVariable", "FlexibleDimension", "Submission"
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

    # `contributors` and `licenses` are Frictionless `minItems: 1`, so an empty
    # list is collapsed to `None` (via `OptionalNonEmptyList`) and dropped under
    # `exclude_none`. `sources` is `minItems: 0`: an empty list is valid, so it is
    # left as-is.
    contributors: OptionalNonEmptyList[Contributor] = Field(
        default=None, description="A list of contributors to the data contract."
    )

    sources: list[Source] | None = Field(
        default=None, description="A list of data sources for the data contract."
    )

    licenses: OptionalNonEmptyList[License] = Field(
        default=None,
        description="A list of licenses for the data associated with the contract.",
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
            type (e.g., Table, Dimension, ValueVariable, FlexibleDimension).
    """

    model_config = ConfigDict(
        populate_by_name=True,
        extra="forbid",
        serialize_by_alias=True,
    )

    contract_type: ContractType = Field(
        default="General",
        description=(
            "The type of the contract, which determines the structure of the "
            "tableschema."
        ),
    )
    tableschema: AnyTableSchema = Field(
        description="The Frictionless Table Schema definition."
    )

    @classmethod
    def from_server(cls, data: dict[str, Any]) -> "CrossContract":
        """
        Server responses include the materialized `tableschema` for all contract
        types so consumers can work with it. For Dimension contracts the schema
        is derived from a fixed template and the public validator forbids it as
        input; this method strips it before validation so the template injection
        can rebuild it cleanly.

        Use this for any dict coming from the server or from stored server
        payloads (e.g. a DB row). For user-authored dicts, use the standard
        constructor.

        Args:
            data (dict[str, Any]): A dictionary containing the data for the
                CrossContract.

        Returns:
            CrossContract: An instance of CrossContract initialized with the
                provided data.
        """
        # as dimensions do not allow for a tableschema to be provided
        # we strip it during construction
        if data.get("contract_type") == "Dimension":
            data = {k: v for k, v in data.items() if k != "tableschema"}
        return cls.model_validate(data)

    def to_server(self) -> dict[str, Any]:
        """Serializes the CrossContract instance into a dictionary format suitable for
        server communication.

        This method converts the CrossContract instance into a dictionary that can be
        easily serialized to JSON for API requests. It ensures that all necessary
        fields are included and properly formatted according to the server's
        expectations.

        Returns:
            dict[str, Any]: A dictionary representation of the CrossContract instance.
        """
        data = self.model_dump(mode="json")
        # server will create the tableschema for dimensions, so we remove it from
        # the payload if it's a dimension
        if self.contract_type == "Dimension":
            data.pop("tableschema", None)
        return data

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

        # if not schema provided, create an empty one
        if schema_data is None:
            schema_data = {}

        # check existence and type of tableschema before proceeding
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

    def validate_references(
        self,
        resolver: ContractResolver,
        enforce_star_schema: bool = True,
    ) -> None:
        """Validate references with star-schema enforcement on by default.

        CrossContract models a star schema: external foreign keys must point to
        contracts whose tableschema is a BaseDimensionSchema. Users achieve this
        by choosing a dimension-flavored contract_type (Dimension or
        FlexibleDimension), which binds the corresponding schema subclass via
        the discriminator. The default of ``enforce_star_schema=True`` reflects
        this invariant, so callers get the canonical check when they omit that
        optional argument and provide only the required ``resolver``.
        Delegates to BaseContract.validate_references; see there for
        implementation details.

        Args:
            resolver: Lookup for referenced contracts by name.
            enforce_star_schema: If True (default), require that every external
                reference points to a contract whose tableschema is a
                BaseDimensionSchema. The check is on the schema type, not the
                contract type — users pick contract types (e.g. Dimension,
                FlexibleDimension) that in turn enforce the schema constraint.
                Pass False to run only the existence + field integrity check —
                see BaseContract.validate_references for that topology-agnostic
                mode.

        Raises:
            ValueError: If any reference validation checks fail, with details on
                the specific errors. All failures are collected and reported in
                a single exception.
        """
        super().validate_references(resolver, enforce_star_schema=enforce_star_schema)
