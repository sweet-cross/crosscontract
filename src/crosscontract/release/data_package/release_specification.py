"""Release specification models determine data resources and packages
together with the instruction how to get the data from the server."""

from pydantic import BaseModel, ConfigDict, Field

from ...transformations import FetchSpecMixin
from .data_resource import CrossDataResource
from .meta_data import CrossDataPackageMetaData


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


class CrossDataResourceReleaseSpec(CrossDataPackageMetaData):
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

    resource: CrossDataResource = Field(
        description=(
            "The data resource for which this release specification applies. It "
            "contains metadata about the resource, such as its name, description, "
            "and schema."
        )
    )
    data_instructions: DataInstructions = Field(
        description=("Instructions for fetching the data for the data resource."),
    )


class CrossDataPackageReleaseSpec(CrossDataPackageMetaData):
    """Release specification for a data package.

    Bundles a `CrossDataPackage` (the package's metadata and resources) with the
    `DataInstructions` describing how to fetch the data for each resource from
    the platform. This is a build recipe, not a Frictionless descriptor: a later
    build step pairs it with a resolver to fetch the data and materialize the
    package..
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    resources: list[CrossDataResourceReleaseSpec] = Field(
        min_length=1,
        description=(
            "A list of release specifications for the data resources included in the "
            "data package. Each resource specification describes a specific dataset "
            "and its associated metadata and data-fetching instructions. A package "
            "MUST contain at least one resource specification."
        ),
    )
