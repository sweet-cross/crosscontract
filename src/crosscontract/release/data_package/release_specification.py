"""Release specification models determine data resources and packages
together with the instruction how to get the data from the server."""

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from crosscontract.contracts.contracts.base_contract import FRICTIONLESS_NAME_PATTERN

from ...transformations import FetchSpecMixin
from .data_resource import CrossDataResource
from .models_package import CrossDataPackageMetaData
from .models_resource import CrossDataResourceMetaData


class DataInstructions(BaseModel):
    """Instructions for obtaining a resource's data from the platform.

    Bundles the fetch specification (`fetch`) describing how to retrieve the
    data. It is the extension point for further data-shaping instructions (e.g.
    transformations) that may be added alongside `fetch` in the future.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    fetch: FetchSpecMixin = Field(
        description=(
            "The data fetching specification, which defines how to retrieve the "
            "data for this resource from the server."
        )
    )


class CrossDataResourceReleaseSpec(CrossDataResourceMetaData):
    """Release specification for a single data resource.

    Bundles a `CrossDataResource` (the resource's metadata and schema) with the
    `DataInstructions` describing how to fetch its data from the platform. This
    is a build recipe, not a Frictionless descriptor: a later build step pairs it
    with a resolver to fetch the data and materialize the resource.

    Note that, in principle, all metadata is taken from the specification;
    however, where it is not provided it is intended to be filled from the
    contract (not yet implemented).
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str | None = Field(
        default=None,
        pattern=FRICTIONLESS_NAME_PATTERN,
        max_length=100,
        description=(
            "A unique identifier for the data resource. Must consist only of "
            "lowercase alphanumeric characters, '.', '_', and '-'."
            "If not provided, will be the same as the name of the contract "
            "used for fetching the data."
        ),
    )
    data_instructions: DataInstructions = Field(
        description=("Instructions for fetching the data for the data resource."),
    )

    @model_validator(mode="after")
    def _fill_name_from_contract(self) -> Self:
        """If the resource name is not provided, fill it from the contract name."""
        self.name = self.name or self.data_instructions.fetch.contract
        return self


class CrossDataPackageReleaseSpec(CrossDataPackageMetaData):
    """Release specification for a data package.

    Carries the package-level metadata (inherited from `CrossDataPackageMetaData`)
    together with a release specification per resource, each pairing a
    `CrossDataResource` with the `DataInstructions` for fetching its data. This is
    a build recipe, not a Frictionless descriptor: a later build step pairs it with
    a resolver to fetch the data and materialize the package.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str | None = Field(
        default=None,
        pattern=FRICTIONLESS_NAME_PATTERN,
        max_length=100,
        description=(
            "A unique identifier for the data contract. Must consist only of "
            "lowercase alphanumeric characters, '.', '_', and '-'."
        ),
    )

    resource: list[CrossDataResourceReleaseSpec] = Field(
        min_length=1,
        description=(
            "A list of release specifications for the data resources included in the "
            "data package. Each resource specification describes a specific dataset "
            "and its associated metadata and data-fetching instructions. A package "
            "MUST contain at least one resource specification."
        ),
    )
