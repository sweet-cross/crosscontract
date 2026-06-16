import warnings
from pathlib import Path
from typing import Any

from ..._helpers import read_yaml_or_json_file
from ...registry import CrossRegistry
from ._resolve_package import save_data_package
from ._resolve_resource import build_data_resource, fetch_data
from .release_specification import CrossDataPackageReleaseSpec


def create_data_package(
    registry: CrossRegistry,
    release_spec: Path | CrossDataPackageReleaseSpec | str,
    fn_out: Path | str,
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
    """
    if isinstance(release_spec, (str, Path)):
        release_spec_dict = read_yaml_or_json_file(release_spec)
        release_spec = CrossDataPackageReleaseSpec.model_validate(release_spec_dict)

    # get the data for each resource according to the release specification
    my_resources: dict[str, dict[str, Any]] = {}
    for resource_spec in release_spec.resources:
        fetch_spec = resource_spec.data_instructions.fetch
        var, df = fetch_data(registry, fetch_spec)
        if df.empty:
            warnings.warn(
                f"Fetched data for contract '{fetch_spec.contract}' is empty. "
                "Skipping this resource.",
                stacklevel=2,
            )
            continue
        data_resource = build_data_resource(resource_spec, var)
        if resource_spec.name in my_resources:
            raise ValueError(f"Duplicate resource name '{resource_spec.name}' found.")
        my_resources[resource_spec.name] = {
            "data_resource": data_resource,
            "data": df,
        }
    # todo: Collect dimensions to also export them
    # dump files and create the package descriptor
    save_data_package(release_spec, my_resources, fn_out)
