import warnings
from typing import Any

import pandas as pd

from ..._standards.frictionless import (
    DataResource,
    FileMetaData,
    TableSchema,
)
from ...registry import CrossRegistry
from ...registry.variables import (
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


def collect_referenced_resources(
    registry: CrossRegistry, variables: list[CrossBaseVariable]
) -> dict[str, CrossBaseVariable]:
    """Collect the resources referenced by the given variables, deduplicated by name.

    Walks each variable's foreign keys and resolves every referenced contract via
    the registry. Keying by contract name means a resource referenced by several
    variables is collected only once.

    Under the platform's star schema these references are always dimensions, but
    nothing here relies on that: any referenced contract is bundled so the released
    data package stays self-contained even if that constraint is relaxed.

    References are resolved one level deep only — a referenced resource's own
    foreign keys are not followed. This is complete under the star schema, where
    referenced resources (dimensions) have no outgoing foreign keys. If the schema
    ever permitted reference chains, this would need to become a transitive walk to
    keep the package self-contained.

    Args:
        registry (CrossRegistry): The registry used to resolve referenced contracts.
        variables (list[CrossBaseVariable]): The (included) variables whose foreign
            keys are scanned.

    Returns:
        dict[str, CrossBaseVariable]: Referenced resources keyed by contract name.
    """
    referenced: dict[str, CrossBaseVariable] = {}
    for var in variables:
        for fk in var.foreign_keys:
            ref = fk.reference.resource
            if ref is None or ref in referenced:  # self-ref or already collected
                continue
            try:
                referenced[ref] = registry[ref]
            except KeyError as e:
                raise ValueError(f"Referenced contract '{ref}' not found") from e
    return referenced


def resolve_resources(
    registry: CrossRegistry,
    release_spec: CrossDataPackageReleaseSpec,
    resolve_references: bool = True,
) -> dict[str, dict[str, Any]]:
    """Resolve the data for each resource according to the release specification.

    Args:
        registry (CrossRegistry): The registry to use for validating contract
            references.
        release_spec (CrossDataPackageReleaseSpec): The release specification for
            the data package, including the metadata and data fetching instructions
            for each resource.
        resolve_references (bool, optional): Whether to resolve and include
            referenced resources (e.g., dimensions) in the returned dictionary.
            Including them keeps the package self-contained, so references are
            resolved by default. When `False`, the referenced resources are left
            out and the now-dangling foreign keys are dropped from the released
            schemas, so the package is no longer self-contained but remains
            Frictionless-compliant. Defaults to `True`.

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

    # collect the resources referenced by the included variables (e.g. dimensions)
    if resolve_references:
        referenced = collect_referenced_resources(registry, included_vars)
        for ref_name, ref_var in referenced.items():
            if ref_name in my_resources:
                # Already resolved in the first pass: the resource was listed
                # explicitly. Contract names are server-unique, so this is
                # necessarily the same resource; the explicit spec wins.
                continue
            ref_df = ref_var.data
            if ref_df.empty:
                warnings.warn(
                    f"Referenced resource '{ref_name}' has no data. Skipping it.",
                    stacklevel=2,
                )
                continue
            # build a ReleaseSpec and re-use the existing build_data_resource
            # function to create a Frictionless DataResource for the referenced
            # resource
            ref_spec = CrossDataResourceReleaseSpec(
                data_instructions=DataInstructions(
                    fetch=FetchSpecMixin(contract=ref_name, format="csv")
                )
            )
            my_resources[ref_name] = {
                "data_resource": build_data_resource(ref_spec, ref_var),
                "data": ref_df,
            }

    # Keep the package self-contained: a released schema may only carry foreign
    # keys whose target resource is also in the package. This drops references to
    # excluded resources (e.g. when resolve_references is False, or a referenced
    # resource was skipped as empty) so the descriptor stays Frictionless-compliant.
    _drop_dangling_foreign_keys(my_resources, warn=resolve_references)

    return my_resources


def _drop_dangling_foreign_keys(
    resources: dict[str, dict[str, Any]], warn: bool = True
) -> None:
    """Strip foreign keys whose target resource is absent from the package.

    Mutates each resource's embedded table schema in place, keeping only foreign
    keys that reference the current resource (an empty `resource`) or another
    resource present in `resources`.

    Args:
        resources (dict[str, dict[str, Any]]): The resolved resources, keyed by
            name. Each value holds the `DataResource` under `"data_resource"`.
        warn (bool, optional): Whether to warn when a resource's foreign keys are
            pruned. Intended for the case where references were meant to be
            included but a target was nonetheless excluded (e.g. skipped as empty);
            leave `False` when references are dropped by design. Defaults to `True`.
    """
    included_names = set(resources)
    for res in resources.values():
        data_resource: DataResource = res["data_resource"]
        schema = data_resource.table_schema
        # `table_schema` may be a string (an external schema reference) per the
        # standard; only an embedded TableSchema carries prunable foreign keys.
        if not isinstance(schema, TableSchema) or not schema.foreignKeys:
            continue
        kept = [
            fk
            for fk in schema.foreignKeys
            # "" is a self-reference (kept); any other target must be present
            if fk.reference.resource in ("", *included_names)
        ]
        if len(kept) != len(schema.foreignKeys):
            if warn:
                warnings.warn(
                    f"Dropping foreign keys from resource '{data_resource.name}' "
                    "whose targets are not included in the package.",
                    stacklevel=2,
                )
            schema.foreignKeys = kept
