from pydantic import ConfigDict, Field

from .base_contract import BaseContract, BaseMetaData


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
        schema (Schema): The Frictionless Table Schema definition.
            Accessible via the `schema` property as well.
    """

    model_config = ConfigDict(
        populate_by_name=True,
        extra="forbid",
        serialize_by_alias=True,
    )
