from pathlib import Path

from ..._helpers import read_yaml_or_json_file
from ...registry import CrossRegistry
from ._resolve_package import save_data_package
from ._resolve_resource import resolve_resources
from .release_specification import CrossDataPackageReleaseSpec


def create_data_package(
    registry: CrossRegistry,
    release_spec: Path | CrossDataPackageReleaseSpec | str,
    fn_out: Path | str,
    resolve_references: bool = True,
) -> None:
    """Create a data package release specification from a dictionary or a YAML/JSON
    file.

    Args:
        registry (CrossRegistry): The registry to use for validating contract
            references.
        release_spec (Path | CrossDataPackageReleaseSpec | str): The release
            specification as a `CrossDataPackageReleaseSpec` instance or a path
            to a YAML/JSON file containing the release specification.
        fn_out (Path | str): File path to write the data package containing the
            data as well as the data package descriptor (a YAML and JSON file) to.
        resolve_references (bool, optional): Whether to resolve and include
            referenced resources (e.g., dimensions) in the package. When `False`,
            foreign keys to excluded resources are dropped from the released schemas
            to keep the package Frictionless-compliant. Defaults to `True`.
    """
    if isinstance(release_spec, (str, Path)):
        release_spec_dict = read_yaml_or_json_file(release_spec)
        release_spec = CrossDataPackageReleaseSpec.model_validate(release_spec_dict)

    # get the data for each resource according to the release specification
    my_resources = resolve_resources(
        registry, release_spec, resolve_references=resolve_references
    )

    # dump files and create the package descriptor
    save_data_package(release_spec, my_resources, fn_out)
