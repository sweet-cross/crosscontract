import shutil
import tempfile
import warnings
from pathlib import Path
from typing import Any

import pandas as pd

from ..._helpers import dump_to_file, read_yaml_or_json_file
from ..._standards.frictionless import (
    DataPackage,
    DataResource,
    FileMetaData,
)
from ...registry import CrossRegistry
from ...registry.variables.data_variable import CrossDataVariable
from ...transformations import FetchSpecMixin
from .release_specification import (
    CrossDataPackageReleaseSpec,
    CrossDataResourceReleaseSpec,
)


def _fetch_data(
    registry: CrossRegistry,
    fetch_spec: FetchSpecMixin,
) -> tuple[CrossDataVariable, pd.DataFrame]:
    """Given a resource release specification, fetch the data according to the
    instructions in the spec.

    Args:
        registry (CrossRegistry): The registry to use for validating contract
            references.
        fetch_spec (FetchSpecMixin): The fetch specification for the data resource,
            including the instructions for fetching its data.

    Returns:
        tuple[CrossDataVariable, pd.DataFrame]: The fetched data variable and the
            data as a pandas DataFrame.
    """
    try:
        var = registry[fetch_spec.contract]
    except KeyError as e:
        raise ValueError(f"Contract '{fetch_spec.contract}' not found") from e

    try:
        if isinstance(var, CrossDataVariable):
            df = var.get_data(**fetch_spec.get_data_kwargs)
        else:
            df = var.data
    except Exception as e:
        raise RuntimeError(
            f"Error fetching data for contract '{fetch_spec.contract}': {e}"
        ) from e
    return var, df


def _build_data_resource(
    resource_spec: CrossDataResourceReleaseSpec, var: CrossDataVariable
) -> DataResource:
    """Build a Frictionless `DataResource` from a `CrossDataResourceReleaseSpec` by
    pairing the release specification with the fetched data.

    Args:
        resource_spec (CrossDataResourceReleaseSpec): The release specification for
            the data resource, including both the descriptive metadata and the
            data fetching instructions.
        var (CrossDataVariable): The fetched data variable

    Returns:
        DataResource: A Frictionless `DataResource` that pairs the descriptive
            metadata from the release specification with the fetched data.
    """
    # resolve the data according to the instructions in the release spec
    match resource_spec.data_instructions.fetch.format:
        case "csv":
            file_metadata = FileMetaData(path=resource_spec.name + ".csv", format="csv")
            profile = "tabular-data-resource"
        case "parquet":
            file_metadata = FileMetaData(
                path=resource_spec.name + ".parquet", format="parquet"
            )
            profile = "data-resource"

    contract_data = var.contract_resource.contract.model_dump(
        exclude={"contract_type"}, exclude_none=True, exclude_unset=True, mode="json"
    )
    contract_data["schema"] = contract_data["tableschema"]
    contract_data.pop("tableschema")
    spec_data = resource_spec.model_dump(
        exclude={"data_instructions"},
        exclude_none=True,
        exclude_unset=True,
        mode="json",
    )
    spec_data["profile"] = profile

    metadata = {
        **contract_data,
        **spec_data,
        **file_metadata.model_dump(exclude_none=True, mode="json"),
    }
    fl_resource = DataResource(**metadata)
    return fl_resource


def _save_data_package(
    release_spec: CrossDataPackageReleaseSpec,
    resources: dict[str, dict[str, Any]],
    fn_out: Path | str,
) -> None:
    """Save the data package to a zip file containing the data files and the
    package descriptor.

    Args:
        release_spec (CrossDataPackageReleaseSpec): The release specification for
            the data package.
        resources (dict[str, dict[str, Any]]): A dictionary mapping resource names
            to their corresponding data resources and data.
        fn_out (Path | str): File path to write the data package containing the
            data as well as the data package descriptor (a YAML and JSON file) to.
    """
    # clean up the output name if it ends with .zip (since shutil.make_archive adds it)
    fn_out = Path(fn_out)
    if fn_out.suffix == ".zip":
        fn_out = fn_out.with_suffix("")
    elif fn_out.suffix != "":
        raise ValueError("Output file must have a .zip extension or no extension")

    with tempfile.TemporaryDirectory() as tmp_dir_path:
        tmp_dir = Path(tmp_dir_path)
        all_resources = []
        for resource_dict in resources.values():
            data_resource: DataResource = resource_dict["data_resource"]
            df: pd.DataFrame = resource_dict["data"]

            out_path = tmp_dir / data_resource.path[0]
            match data_resource.format:
                case "csv":
                    df.to_csv(out_path, index=False, encoding=data_resource.encoding)
                case "parquet":
                    df.to_parquet(out_path, index=False)
            all_resources.append(data_resource)
        package_descriptor = DataPackage(
            **release_spec.model_dump(
                exclude={"resources"},
                exclude_none=True,
                exclude_unset=True,
                mode="json",
            ),
            resources=all_resources,
        )
        _data = package_descriptor.model_dump(exclude_unset=True, mode="json")
        dump_to_file(_data, tmp_dir / "datapackage.json")
        dump_to_file(_data, tmp_dir / "datapackage.yaml")
        shutil.make_archive(fn_out, "zip", tmp_dir_path)


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
        var, df = _fetch_data(registry, fetch_spec)
        if df.empty:
            warnings.warn(
                f"Fetched data for contract '{fetch_spec.contract}' is empty. "
                "Skipping this resource.",
                stacklevel=2,
            )
            continue
        data_resource = _build_data_resource(resource_spec, var)
        if resource_spec.name in my_resources:
            raise ValueError(f"Duplicate resource name '{resource_spec.name}' found.")
        my_resources[resource_spec.name] = {
            "data_resource": data_resource,
            "data": df,
        }
    # todo: Collect dimensions to also export them
    # dump files and create the package descriptor
    _save_data_package(release_spec, my_resources, fn_out)
