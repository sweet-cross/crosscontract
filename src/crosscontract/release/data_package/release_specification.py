"""Release specification models determine data resources and packages
together with the instruction how to get the data from the server."""

from pydantic import BaseModel, ConfigDict, Field

from ...transformations import FetchSpecMixin
from .data_resource import CrossDataResource


class DataInstructions(BaseModel):
    """A data fetching specification, which defines how to retrieve the data for
    a resource from the server. It is a subclass of FetchSpecMixin, which provides
    the same fields and validation logic.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    fetch: FetchSpecMixin = Field(
        description=(
            "The data fetching specification, which defines how to retrieve the "
            "data for this resource from the server."
        )
    )


class CrossDataResourceReleaseSpec(BaseModel):
    """A data package release specification. A release specification is the same
    as the DataResource model but with additional information about how to
    fetch the data from the server.

    Note that in principle all the metadata information is taken from the
    specification. However, if it is not provided, it will be filled from the
    contract.
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
        description=(
            "Instructions how to fetch and transform the data for the data resource."
        ),
    )
