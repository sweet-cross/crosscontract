import pandas as pd

from ..._standards.frictionless import (
    DataResource,
    FileMetaData,
)
from ...registry import CrossRegistry
from ...registry.variables.data_variable import CrossDataVariable
from ...transformations import FetchSpecMixin
from .release_specification import CrossDataResourceReleaseSpec


def fetch_data(
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


def build_data_resource(
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
