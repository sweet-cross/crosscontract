import shutil
import tempfile
from pathlib import Path
from typing import Any

import pandas as pd

from ..._helpers import dump_to_file
from ..._standards.frictionless import (
    DataPackage,
    DataResource,
)
from .release_specification import CrossDataPackageReleaseSpec


def save_data_package(
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
                case _:
                    raise ValueError(
                        f"Unsupported data format '{data_resource.format}' for "
                        f"resource '{data_resource.name}'"
                    )
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
