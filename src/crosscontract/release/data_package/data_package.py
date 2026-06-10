import json
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml
from pydantic import AnyUrl, BaseModel, ConfigDict, Field, field_validator

from ...contracts.contracts.base_contract import FRICTIONLESS_NAME_PATTERN
from ...contracts.contracts.metadata_models import (
    Contributor,
    DataSource,
    License,
)
from .data_resource import CrossDataResource


class CrossDataPackage(BaseModel):
    """
    A frictionless compliant representation of a data package that contains
    several `CrossDataResource` objects. This is the top-level descriptor for a
    data package, which includes metadata about the package itself as well as a
    list of resources (tables).

    Attributes:
        name (str): A unique, Frictionless-compliant identifier for the package.
        id (str | None): An optional globally unique identifier (e.g. UUID or DOI).
        title (str): A human-readable title for the data package.
        description (str): A human-readable description of the data package.
        homepage (AnyUrl | None): An optional URL for the package's web home.
        created (datetime | None): The datetime the descriptor was created.
        contributors (list[Contributor] | None): Contributors to the package.
        sources (list[DataSource] | None): Data sources for the package.
        licenses (list[License] | None): Licenses for the package's data.
        resources (list[CrossDataResource]): The data resources (tables) in the
            package. At least one is required.
    """

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

    resources: list[CrossDataResource] = Field(
        min_length=1,
        description=(
            "A list of data resources (tables) included in the data package. Each "
            "resource describes a specific dataset and its associated metadata. A "
            "package MUST contain at least one resource."
        ),
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

    @property
    def profile(self) -> str:
        """The profile of the data package, which is always 'data-package'."""
        return "data-package"

    def to_descriptor(self) -> dict[str, Any]:
        """Render the Frictionless data-package descriptor.

        Serializes the package metadata and delegates each resource to
        `CrossDataResource.to_descriptor`, so the internal `tableschema` key is
        remapped to the Frictionless-standard `schema` uniformly. This is the
        single point where the release wire-format is assembled; the model itself
        stays neutral and round-trippable via the ordinary fields, and the
        package `profile` is surfaced here rather than in the model state.

        Returns:
            dict[str, Any]: The Frictionless-compatible data-package descriptor,
                ready to be written alongside the data files in the (zip) archive.
        """
        descriptor = self.model_dump(
            mode="json", by_alias=True, exclude_none=True, exclude={"resources"}
        )
        descriptor["profile"] = self.profile
        descriptor["resources"] = [r.to_descriptor() for r in self.resources]
        return descriptor

    def to_file(self, path: Path | str) -> None:
        """Saves the data package descriptor to a JSON or yaml file at
        the specified path.

        Args:
            path (Path | str): The file path where the data package descriptor
                should be saved.
        """
        path = Path(path)
        suffix = path.suffix.lower()
        descriptor = self.to_descriptor()
        if suffix == ".json":
            path.write_text(json.dumps(descriptor, indent=2))
        elif suffix in (".yaml", ".yml"):
            with path.open("w") as f:
                yaml.dump(descriptor, f, sort_keys=False)
        else:
            raise ValueError(
                f"Unsupported extension '{suffix}'. Use .json, .yaml, or .yml."
            )
