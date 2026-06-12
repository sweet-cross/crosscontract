"""The DataPackageReleaseSpec model, which defines the
schema for a data package release specification. It takes the same fields as a
CrossDataPackage but adds additional information how to fetch the data
from the server."""

from pydantic import ConfigDict, Field

from ...transformations import FetchSpecMixin
from .data_resource import CrossDataResource


class CrossDataResourceReleaseSpec(CrossDataResource):
    """A data package release specification. A release specification is the same
    as the DataResource model but with additional information about how to
    fetch the data from the server.

    Note that in principle all the metadata information is taken from the
    specification. However, if it is not provided, it will be filled from the
    contract.
    """

    config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    data: FetchSpecMixin = Field(
        default_factory=FetchSpecMixin,
        description=(
            "The data fetching specification, which defines how to retrieve the "
            "data for this resource from the server. If not provided, it defaults "
            "to an empty FetchSpecMixin, which yields the get_data bypass sentinels."
        ),
    )
