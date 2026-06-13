import json
from pathlib import Path
from typing import Any, Self

import yaml
from pydantic import ConfigDict, Field, field_validator

from .data_resource import CrossDataResource
from .models_package import CrossDataPackageMetaData


class CrossDataPackage(CrossDataPackageMetaData):
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

    resources: list[CrossDataResource] = Field(
        min_length=1,
        description=(
            "A list of data resources (tables) included in the data package. Each "
            "resource describes a specific dataset and its associated metadata. A "
            "package MUST contain at least one resource."
        ),
    )

    @property
    def profile(self) -> str:
        """The profile of the data package, which is always 'data-package'."""
        return "data-package"

    @field_validator(mode="after")
    def _validate_resource_names(self) -> Self:
        """Validate that all resource names are unique within the package."""
        resource_names = [resource.name for resource in self.resources]
        if len(resource_names) != len(set(resource_names)):
            raise ValueError("All resource names within a data package must be unique.")
        return self

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
            path.write_text(
                json.dumps(descriptor, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        elif suffix in (".yaml", ".yml"):
            # safe_dump refuses to emit non-standard `!!python/...` tags, so a stray
            # non-primitive in the descriptor fails loudly rather than producing an
            # unportable document. UTF-8 + allow_unicode keeps the output readable and
            # symmetric with read_yaml_or_json_file (which reads UTF-8).
            with path.open("w", encoding="utf-8") as f:
                yaml.safe_dump(descriptor, f, sort_keys=False, allow_unicode=True)
        else:
            raise ValueError(
                f"Unsupported extension '{suffix}'. Use .json, .yaml, or .yml."
            )
