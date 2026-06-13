from datetime import datetime
from typing import Any

from pydantic import (
    AnyUrl,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)

from ...contracts.contracts.base_contract import FRICTIONLESS_NAME_PATTERN
from ...contracts.contracts.metadata_models import (
    Contributor,
    DataSource,
    License,
)


class CrossDataPackageMetaData(BaseModel):
    """The metadata for a data package including its name, title, description,
    and other optional fields."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(
        pattern=FRICTIONLESS_NAME_PATTERN,
        description=(
            "A unique identifier for the data package. This should be a slug or "
            "machine-readable name that can be used as an identifier in code. "
            "Must consist only of lowercase alphanumeric characters, '.', '_', "
            "and '-'."
        ),
    )
    id: str | None = Field(
        default=None,
        description=(
            "A globally unique identifier for the data package, such as a UUID or "
            "DOI. Optional. While global uniqueness cannot be validated here, "
            "consumers that rely on `id` MUST ensure it is globally unique."
        ),
    )
    title: str = Field(
        description=("A human-readable title for the data package."),
    )

    description: str = Field(
        description=(
            "A human-readable description of the data package. "
            "This should explain what the data package is about."
        )
    )
    homepage: AnyUrl | None = Field(
        default=None,
        description="A URL for the web home related to this data package.",
    )
    created: datetime | None = Field(
        default=None,
        description=(
            "The datetime on which this descriptor was created, serialized as an "
            "RFC3339 string."
        ),
    )
    contributors: list[Contributor] | None = Field(
        default=None, description="A list of contributors to the data package."
    )

    sources: list[DataSource] | None = Field(
        default=None, description="A list of data sources for the data package."
    )

    licenses: list[License] | None = Field(
        default=None,
        description="A list of licenses for the data associated with the data package.",
    )

    @field_validator("contributors", "sources", "licenses", mode="before")
    @classmethod
    def _empty_list_to_none(cls, value: Any) -> Any:
        """Normalize an empty optional list to `None`.

        Frictionless requires `minItems: 1` on `contributors`, `sources`, and
        `licenses`, so an empty list would be non-compliant. Collapsing `[]` to
        `None` lets `to_descriptor`'s `exclude_none` drop the key entirely rather
        than emit an invalid empty array.

        Args:
            value (Any): The raw field value before validation.

        Returns:
            Any: `None` if `value` is an empty list, otherwise `value` unchanged.
        """
        if isinstance(value, list) and not value:
            return None
        return value
