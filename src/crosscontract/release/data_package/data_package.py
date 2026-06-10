import json
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field

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
    list of resources (tables)

    Attributes:
        title (str): A human-readable title for the data.
        description (str): A human-readable description of the data.
        tags (list[str] | None): A list of tags for categorization and filtering.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(
        pattern=r"^([-a-z0-9._/])+$",
        description=(
            "A unique identifier for the data package. This should be a slug or "
            "machine-readable name that can be used as an identifier in code. "
            "Must consist only of lowercase alphanumeric characters, '.', '_', '-',"
            " and '/'."
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
        description=(
            "A list of data resources (tables) included in the data package. Each "
            "resource describes a specific dataset and its associated metadata."
        )
    )

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
            by_alias=True, exclude_none=True, exclude={"resources"}
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
