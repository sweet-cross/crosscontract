"""Reusable Frictionless metadata building blocks.

The Frictionless **Data Resource** and **Data Package** descriptors share a large
descriptive core (`title`, `description`, `licenses`, ...). Rather than repeat it,
this module factors the standard's metadata into small, composable models that
`descriptors.py` assembles into the concrete `DataResource` / `DataPackage`:

- `BaseMetaData` — descriptive fields *identical* in both schemas.
- `ResourceMetaData(BaseMetaData)` — adds the resource-only descriptive fields
  (`profile`, `name`, `schema`).
- `PackageMetaData(BaseMetaData)` — adds the package-only descriptive fields
  (`profile`, `name`, `id`, `created`, `contributors`, `keywords`, `image`).
- `FileMetaData` — the *physical* data binding (`path`, `data`, `format`,
  `mediatype`, `encoding`, `bytes`, `hash`), kept orthogonal to the descriptive
  metadata so a resource can mix the two in (`DataResource(ResourceMetaData,
  FileMetaData)`), echoing the layering in `crosscontract.release.data_package`.

Everything here stays *permissive* (`extra="allow"`) and faithful to the upstream
Frictionless JSON Schemas, with no CROSS-specific domain logic.
The `resources` array of a package is intentionally **not** modelled here — it
lives on the concrete `DataPackage` in `descriptors.py`, so this module never has
to reference `DataResource` and the two files stay free of circular imports.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ..._helpers import OptionalNonEmptyList
from .table_schema import TableSchema

# Shared config: permissive and whitespace-trimming, matching `fields.py` /
# `table_schema.py`. `populate_by_name` + `serialize_by_alias` let the `schema`
# field (see `ResourceMetaData.table_schema`) round-trip under its Frictionless
# wire name while staying addressable by its safe python name.
_MODEL_CONFIG = ConfigDict(
    extra="allow",
    str_strip_whitespace=True,
    populate_by_name=True,
    serialize_by_alias=True,
)

# The Frictionless `name` pattern, shared by Resource and Package and reused by
# other modules. It contains no look-arounds, so pydantic-core's Rust regex engine
# accepts it as-is (unlike the `path` pattern — see `FileMetaData.path`). Note this
# is the resource/package variant, which permits `/`; the contract/field-name
# variant in `contracts.contracts.base_contract` does not.
FRICTIONLESS_NAME_PATTERN = r"^([-a-z0-9._/])+$"


def _to_list(value: Any) -> Any:
    """Normalize a bare string to a one-element list.

    The Frictionless `path` property accepts either a string or an array of
    strings. We canonicalize to a list so downstream code sees one shape.

    Returns:
        Any: A one-element list when a bare string was given, else `value`
        unchanged (non-string/list inputs are left for validation to reject).
    """
    if isinstance(value, str):
        return [value]
    return value


class Source(BaseModel):
    """A raw source for a resource or package (the `sources[]` items)."""

    model_config = _MODEL_CONFIG

    title: str = Field(description="A human-readable title for the source.")
    path: str | None = Field(
        default=None,
        description="A fully qualified URL, or a POSIX file path, to the source.",
    )
    email: str | None = Field(
        default=None,
        description="An email address for the source contact.",
    )


class License(BaseModel):
    """A license under which a resource or package is published.

    The standard requires *at least one* of `name` or `path`.
    """

    model_config = _MODEL_CONFIG

    name: str | None = Field(
        default=None,
        pattern=r"^([-a-zA-Z0-9._])+$",
        description=(
            "An Open Definition license identifier, see "
            "http://licenses.opendefinition.org/"
        ),
    )
    path: str | None = Field(
        default=None,
        description="A fully qualified URL, or a POSIX file path, to the license text.",
    )
    title: str | None = Field(
        default=None,
        description="A human-readable title for the license.",
    )

    @model_validator(mode="after")
    def _require_name_or_path(self) -> "License":
        """Enforce the standard's `anyOf` constraint: `name` or `path` is present.

        Returns:
            License: The validated instance.

        Raises:
            ValueError: If neither `name` nor `path` is set.
        """
        if not self.name and not self.path:
            raise ValueError("A license must define at least one of `name` or `path`.")
        return self


class Contributor(BaseModel):
    """A contributor to a package descriptor (the `contributors[]` items).

    `role` is a free-form string per the standard (defaulting to `contributor`);
    the curated CROSS `Contributor` narrows it to a `Literal`.
    """

    model_config = _MODEL_CONFIG

    title: str = Field(description="A human-readable name for the contributor.")
    path: str | None = Field(
        default=None,
        description="A URL or POSIX path for the contributor.",
    )
    email: str | None = Field(
        default=None,
        description="An email address for the contributor.",
    )
    organization: str | None = Field(
        default=None,
        description="An organizational affiliation for the contributor.",
    )
    role: str = Field(
        default="contributor",
        description="The contributor's role, e.g. `author`, `maintainer`.",
    )


class BaseMetaData(BaseModel):
    """Descriptive metadata shared by the Resource and Package descriptors.

    Only the fields whose definition is *identical* in both upstream schemas live
    here. `profile` and `name` are deliberately left to the subclasses: their
    defaults and optionality differ between resource and package, so a shared
    definition would misrepresent one of them.
    """

    model_config = _MODEL_CONFIG

    title: str | None = Field(
        default=None,
        description="A human-readable title.",
    )
    description: str | None = Field(
        default=None,
        description="A text description. Markdown is encouraged.",
    )
    homepage: str | None = Field(
        default=None,
        description="The home on the web related to this descriptor.",
    )
    sources: list[Source] = Field(
        default_factory=list,
        description="The raw sources for this descriptor.",
    )
    licenses: OptionalNonEmptyList[License] = Field(
        default=None,
        description="The license(s) under which this descriptor is published.",
    )


class FileMetaData(BaseModel):
    """The physical binding of a resource to its data.

    Orthogonal to the descriptive metadata: where the bytes live (`path` /
    inline `data`) and how to read them (`format`, `mediatype`, `encoding`,
    `bytes`, `hash`). A resource composes this with `ResourceMetaData`.
    """

    model_config = _MODEL_CONFIG

    # The Frictionless `path` pattern uses look-arounds, which pydantic-core's
    # Rust regex engine rejects. Staying permissive, we accept any string(s) and
    # only canonicalize a bare string to a list (the standard allows both forms).
    path: list[str] = Field(
        default_factory=list,
        description="A path or array of paths/URLs to the resource's data.",
    )
    data: Any | None = Field(
        default=None,
        description="Inline data for this resource (alternative to `path`).",
    )
    format: str | None = Field(
        default=None,
        description="The file format of this resource, e.g. `csv`, `xls`, `json`.",
    )
    mediatype: str | None = Field(
        default=None,
        pattern=r"^(.+)/(.+)$",
        description="The IANA media type of this resource, e.g. `text/csv`.",
    )
    encoding: str = Field(
        default="utf-8",
        description="The file encoding of this resource.",
    )
    bytes: int | None = Field(
        default=None,
        description="The size of this resource in bytes.",
    )
    hash: str | None = Field(
        default=None,
        pattern=r"^([^:]+:[a-fA-F0-9]+|[a-fA-F0-9]{32}|)$",
        description=(
            "The MD5 hash of this resource, or `{algorithm}:{hash}` for others."
        ),
    )

    @field_validator("path", mode="before")
    @classmethod
    def _path_to_list(cls, value: Any) -> Any:
        """Normalize a single `path` string to a one-element list.

        Returns:
            Any: A list when a bare string was given, else `value` unchanged.
        """
        return _to_list(value)

    @model_validator(mode="after")
    def _require_data_or_path(self) -> "FileMetaData":
        """Enforce the standard's `oneOf`: a resource has `data` or `path`.

        Returns:
            FileMetaData: The validated instance.

        Raises:
            ValueError: If neither `data` nor `path` is provided.
        """
        if self.data is None and not self.path:
            raise ValueError("A data resource must define either `data` or `path`.")
        return self


class ResourceMetaData(BaseMetaData):
    """The descriptive metadata of a Data Resource (everything but the file).

    Adds the resource-only descriptive fields on top of `BaseMetaData`. The file
    binding (`path`, `format`, ...) is supplied separately by `FileMetaData`.
    """

    profile: str = Field(
        default="data-resource",
        description="The profile of this descriptor.",
    )
    name: str = Field(
        pattern=FRICTIONLESS_NAME_PATTERN,
        description=(
            "An identifier string: lower-case characters with `.`, `_`, `-`, `/`."
        ),
    )
    # Frictionless wire name is `schema`; we cannot name the field `schema`
    # because it shadows the deprecated `BaseModel.schema` method (UserWarning +
    # mypy `[assignment]`). The field is `table_schema`, exposed via its `schema`
    # alias. `serialize_by_alias`/`populate_by_name` (see `_MODEL_CONFIG`) keep
    # the round-trip symmetric. The standard also allows a string (a path to an
    # external schema), so the type is `str | TableSchema | None`.
    table_schema: str | TableSchema | None = Field(
        default=None,
        alias="schema",
        description="A `TableSchema` for this resource, or a path to one.",
    )


class PackageMetaData(BaseMetaData):
    """The descriptive metadata of a Data Package.

    Adds the package-only descriptive fields on top of `BaseMetaData`. The
    `resources` array is *not* defined here — it lives on the concrete
    `DataPackage` so this module need not import `DataResource`.
    """

    profile: str = Field(
        default="data-package",
        description="The profile of this descriptor.",
    )
    name: str | None = Field(
        default=None,
        pattern=FRICTIONLESS_NAME_PATTERN,
        description=(
            "An identifier string: lower-case characters with `.`, `_`, `-`, `/`."
        ),
    )
    id: str | None = Field(
        default=None,
        description="A globally unique identifier, e.g. a UUID or DOI.",
    )
    # Kept as a string to round-trip the RFC3339 value verbatim; the standard
    # only constrains the format, not the timezone or precision.
    created: str | None = Field(
        default=None,
        description="The RFC3339 datetime on which this descriptor was created.",
    )
    contributors: OptionalNonEmptyList[Contributor] = Field(
        default=None,
        description="The contributors to this descriptor.",
    )
    keywords: OptionalNonEmptyList[str] = Field(
        default=None,
        description="A list of keywords that describe this package.",
    )
    image: str | None = Field(
        default=None,
        description="An image to represent this package.",
    )
