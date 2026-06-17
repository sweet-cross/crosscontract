import warnings
from typing import Any

import pandas as pd

from ..._standards.frictionless import (
    DataResource,
    FileMetaData,
)
from ...registry import CrossRegistry
from ...registry.variables import (
    CrossBaseDimension,
    CrossBaseVariable,
    CrossDataVariable,
)
from ...transformations import FetchSpecMixin
from .release_specification import (
    CrossDataPackageReleaseSpec,
    CrossDataResourceReleaseSpec,
    DataInstructions,
)


def fetch_data(
    registry: CrossRegistry,
    fetch_spec: FetchSpecMixin,
) -> tuple[CrossBaseVariable, pd.DataFrame]:
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
    resource_spec: CrossDataResourceReleaseSpec, var: CrossBaseVariable
) -> DataResource:
    """Build a Frictionless `DataResource` from a `CrossDataResourceReleaseSpec` by
    pairing the release specification with the fetched data.

    Args:
        resource_spec (CrossDataResourceReleaseSpec): The release specification for
            the data resource, including both the descriptive metadata and the
            data fetching instructions.
        var (CrossBaseVariable): The fetched data variable (only its
            `contract_resource.contract` is read here).

    Returns:
        DataResource: A Frictionless `DataResource` that pairs the descriptive
            metadata from the release specification with the fetched data.
    """
    # `name` is guaranteed non-None after `_fill_name_from_contract`.
    name = resource_spec.name
    assert name is not None

    # resolve the data according to the instructions in the release spec
    format_spec = resource_spec.data_instructions.fetch.format
    match format_spec:
        case "csv":
            file_metadata = FileMetaData(path=[f"{name}.csv"], format="csv")
            profile = "tabular-data-resource"
        case "parquet":
            file_metadata = FileMetaData(path=[f"{name}.parquet"], format="parquet")
            profile = "data-resource"
        case _:
            raise ValueError(
                f"Unsupported data format '{format_spec}' for "
                f"resource '{resource_spec.name}'"
            )

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


def collect_dimensions(
    registry: CrossRegistry, variables: list[CrossBaseVariable]
) -> dict[str, CrossBaseDimension]:
    """Collect the dimensions referenced by the given variables, deduplicated by name.

    Walks each variable's foreign keys and resolves every referenced contract via
    the registry, keeping those that are dimensions. Keying by contract name means a
    dimension referenced by several variables is collected only once.

    Args:
        registry (CrossRegistry): The registry used to resolve referenced contracts.
        variables (list[CrossBaseVariable]): The (included) fact variables whose
            foreign keys are scanned.

    Returns:
        dict[str, CrossBaseDimension]: Referenced dimensions keyed by contract name.
    """
    dimensions: dict[str, CrossBaseDimension] = {}
    for var in variables:
        for fk in var.foreign_keys:
            ref = fk.reference.resource
            if ref is None or ref in dimensions:  # self-ref or already collected
                continue
            target = registry[ref]
            if isinstance(target, CrossBaseDimension):
                dimensions[ref] = target
    return dimensions


def resolve_resources(
    registry: CrossRegistry, release_spec: CrossDataPackageReleaseSpec
) -> dict[str, dict[str, Any]]:
    """Resolve the data for each resource according to the release specification.

    Args:
        registry (CrossRegistry): The registry to use for validating contract
            references.
        release_spec (CrossDataPackageReleaseSpec): The release specification for
            the data package, including the metadata and data fetching instructions
            for each resource.

    Returns:
        dict[str, dict[str, Any]]: A dictionary mapping resource names to their
            resolved data and metadata.
            Each value is a dictionary with keys "data_resource" (the Frictionless
            `DataResource` for the resource) and "data" (the fetched data as a pandas
            DataFrame).
    """
    my_resources: dict[str, dict[str, Any]] = {}
    included_vars: list[CrossBaseVariable] = []
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
        name = resource_spec.name
        assert name is not None  # guaranteed by _fill_name_from_contract
        if name in my_resources:
            raise ValueError(f"Duplicate resource name '{name}' found.")
        my_resources[name] = {
            "data_resource": data_resource,
            "data": df,
        }
        included_vars.append(var)

    if not my_resources:
        raise ValueError(
            "No resources to release: every resource resolved to empty data."
        )

    # collect the dimensions referenced by the included variables
    dimensions = collect_dimensions(registry, included_vars)
    for dim_name, dim in dimensions.items():
        if dim_name in my_resources:
            # Already resolved in the first pass: the dimension was listed
            # explicitly as a resource. Contract names are server-unique, so this
            # is necessarily the same dimension; the explicit spec wins.
            continue
        dim_df = dim.data
        if dim_df.empty:
            warnings.warn(
                f"Dimension '{dim_name}' has no data. Skipping this resource.",
                stacklevel=2,
            )
            continue
        # build a ReleaseSpec and re-use the existing build_data_resource function
        # to create a Frictionless DataResource for the dimension
        dim_spec = CrossDataResourceReleaseSpec(
            data_instructions=DataInstructions(
                fetch=FetchSpecMixin(contract=dim_name, format="csv")
            )
        )
        my_resources[dim_name] = {
            "data_resource": build_data_resource(dim_spec, dim),
            "data": dim_df,
        }

    return my_resources
