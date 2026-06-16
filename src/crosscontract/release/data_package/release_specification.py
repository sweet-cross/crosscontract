"""Release specification models determine data resources and packages
together with the instruction how to get the data from the server."""

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..._helpers import OptionalNonEmptyList
from ..._standards.frictionless import Contributor, PackageMetaData, ResourceMetaData
from ...contracts.contracts.base_contract import CONTRACT_NAME_PATTERN
from ...transformations import FetchSpecMixin


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


class CrossDataResourceReleaseSpec(ResourceMetaData):
    """Release specification for a single data resource.

    Carries the resource's descriptive metadata (inherited from
    `frictionless.ResourceMetaData`) together with the `DataInstructions` describing
    how to fetch its data from the platform. This is a build recipe, not a
    Frictionless descriptor: a later build step pairs it with a resolver to fetch
    the data and materialize the resource.

    `name` is optional and defaults to the name of the contract used for
    fetching; the remaining descriptive metadata must be supplied by the
    specification.
    """

    model_config = ConfigDict(extra="allow", str_strip_whitespace=True)
    # Deliberately relax the inherited required `name` to optional: it defaults
    # to the contract name in `_fill_name_from_contract`.
    name: str | None = Field(  # type: ignore[assignment]
        default=None,
        pattern=CONTRACT_NAME_PATTERN,
        max_length=100,
        description=(
            "A unique identifier for the data resource. Must consist only of "
            "lowercase alphanumeric characters, '.', '_', and '-'."
            "If not provided, will be the same as the name of the contract "
            "used for fetching the data."
        ),
    )
    # Resource-level contributors are a deliberate CROSS extension (upstream
    # Frictionless places `contributors` on the package only): a contract may
    # carry contributors, so a released resource is allowed to as well.
    contributors: OptionalNonEmptyList[Contributor] = Field(
        default=None, description="A list of contributors to the data resource."
    )
    data_instructions: DataInstructions = Field(
        description=("Instructions for fetching the data for the data resource."),
    )

    @model_validator(mode="after")
    def _fill_name_from_contract(self) -> Self:
        """If the resource name is not provided, fill it from the contract name."""
        if self.name is not None:
            raise NotImplementedError(
                "Explicit resource names are not supported yet. "
                "Automatically filling from contract name."
            )
        self.name = self.name or self.data_instructions.fetch.contract
        return self


class CrossDataPackageReleaseSpec(PackageMetaData):
    """Release specification for a data package.

    Carries the package-level metadata (inherited from `frictionless.PackageMetaData`)
    together with a `CrossDataResourceReleaseSpec` per resource, each bundling the
    resource's metadata with the `DataInstructions` for fetching its data. This is
    a build recipe, not a Frictionless descriptor: a later build step pairs it with
    a resolver to fetch the data and materialize the package.
    """

    model_config = ConfigDict(extra="allow", str_strip_whitespace=True)

    name: str = Field(
        pattern=CONTRACT_NAME_PATTERN,
        max_length=100,
        description=(
            "A unique identifier for the data contract. Must consist only of "
            "lowercase alphanumeric characters, '.', '_', and '-'."
        ),
    )

    resources: list[CrossDataResourceReleaseSpec] = Field(
        min_length=1,
        description=(
            "A list of release specifications for the data resources included in the "
            "data package. Each resource specification describes a specific dataset "
            "and its associated metadata and data-fetching instructions. A package "
            "MUST contain at least one resource specification."
        ),
    )

    @model_validator(mode="after")
    def _validate_unique_resource_names(self) -> Self:
        """Validate that all resource names in the package are unique."""
        resource_names = [res.name for res in self.resources]
        if len(resource_names) != len(set(resource_names)):
            raise ValueError("All resource names in the package must be unique.")
        return self
