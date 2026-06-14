"""Frictionless Data Resource and Data Package descriptor models.

A faithful, *permissive* pydantic representation of the Frictionless **Data
Resource** and **Data Package** descriptors.

The descriptors themselves are deliberately thin: they compose the reusable
metadata building blocks in `metadata.py`. A resource is its descriptive
metadata plus a file binding; a package is its descriptive metadata plus a
`resources` array:

- `DataResource(ResourceMetaData, FileMetaData)`
- `DataPackage(PackageMetaData)` + `resources`

This mirrors the *upstream* standard, not the stricter CROSS models in
`crosscontract.contracts.contracts.metadata_models` (`extra="forbid"`) or the
CROSS-opinionated `crosscontract.release.data_package`. Every model sets
`extra="allow"` so the standard's extensibility rides through losslessly. Wiring
this layer to the CROSS models is left for later.
"""

from pydantic import Field

from .metadata import (
    Contributor,
    FileMetaData,
    License,
    PackageMetaData,
    ResourceMetaData,
    Source,
)

__all__ = [
    "DataResource",
    "DataPackage",
    "Source",
    "License",
    "Contributor",
]


class DataResource(ResourceMetaData, FileMetaData):
    """A Frictionless Data Resource descriptor.

    A composition of `ResourceMetaData` (the descriptive metadata: `profile`,
    `name`, `schema`, `title`, ...) and `FileMetaData` (the data binding: `path`
    or inline `data`, `format`, `encoding`, ...). The standard's `name`-plus-
    (`data` xor `path`) requirement is enforced across the two: `name` is
    required by `ResourceMetaData`, and `FileMetaData` rejects a resource that
    declares neither `data` nor `path`.
    """


class DataPackage(PackageMetaData):
    """A Frictionless Data Package descriptor.

    Adds the required, non-empty `resources` array to `PackageMetaData`. This is
    the only field the standard requires of a package.
    """

    resources: list[DataResource] = Field(
        min_length=1,
        description="An array of Data Resource objects (at least one).",
    )
