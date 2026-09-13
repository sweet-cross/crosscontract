from pathlib import Path
from typing import Self

import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..._helpers import read_yaml_or_json_file
from ..schema import DimensionSchema, TableSchema, ValueVariableSchema
from .resolvers import ContractResolver

# A deliberately strict subset of the Frictionless identifier pattern
# (``^([-a-z0-9._/])+$``, see `FRICTIONLESS_NAME_PATTERN` in
# `_standards.frictionless`): lowercase alphanumeric characters plus '.', '_', and
# '-'. The '/' the standard permits is intentionally excluded. Because this is a
# subset, any accepted name is also a valid Frictionless name, so contracts stay
# release-compliant by construction.
CONTRACT_NAME_PATTERN = r"^([-a-z0-9._])+$"


class BaseMetaData(BaseModel):
    """
    The BaseMetadata class encapsulates the essential metadata attributes
    required for defining a data contract. Every data contract MUST include
    these metadata fields to ensure proper identification and description.
    To extend the metadata for specific use cases, inherit from this class
    and add additional fields as necessary. Then use the extended metadata
    class as a base for your custom contract together with BaseContract.

    Attributes:
        name (str): A unique identifier for the data contract. Must be a
            Frictionless-compliant identifier: lowercase alphanumeric characters
            plus '.', '_', and '-' (no uppercase, no '/'). Maximum length is 100
            characters.
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(
        pattern=CONTRACT_NAME_PATTERN,
        max_length=100,
        description=(
            "A unique identifier for the data contract. Must consist only of "
            "lowercase alphanumeric characters, '.', '_', and '-'."
        ),
    )


class BaseContract(BaseMetaData):
    """
    The BaseContract class is the most basic representation of a data contract.
    It combines the minimum required metadata with the contract structure given by
    Schema.

    It serves as the foundational blueprint for defining data contracts.
    Any custom contract implementation MUST inherit from this class to ensure
    structural consistency and compatibility with the system.

    Attributes:
        name (str): A unique identifier for the data contract.
            Must contain only alphanumeric characters, underscores, or hyphens.
            Maximum length is 100 characters.
        tableschema (TableSchema): The schema defining the structure of the contract
            (fields, primary keys, foreign keys, field descriptors).

    Example:
        To implement a custom contract with additional metadata:

        ```python
        from pydantic import Field
        from crosscontract.contracts import BaseContract

        class MyCustomContract(BaseContract):
            # Add custom metadata fields
            owner: str = Field(description="The owner of this dataset")
            version: str = Field(description="Semantic version of the contract")

            # The 'schema' field is already inherited from BaseContract!
        ```
    """

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    tableschema: TableSchema = Field(
        description="The Frictionless Table Schema definition.",
    )

    @classmethod
    def from_file(cls, file_path: str | Path) -> Self:
        """
        Load a BaseContract from a YAML or JSON file.

        Args:
            file_path (str | Path): The path to the YAML or JSON file.

        Returns:
            Self: An instance of BaseContract loaded from the file.

        Raises:
            FileNotFoundError: If the specified file does not exist.
            ValueError: If the file format is not supported (not .json, .yaml, or .yml).
        """
        data = read_yaml_or_json_file(file_path)
        return cls.model_validate(data)

    @model_validator(mode="after")
    def _validate_self_reference(self) -> Self:
        """Validate that self-referencing foreign keys are given as None on the
        resource field. Raise if a reference has the same name as the contract itself.
        """
        for fk in self.tableschema.foreignKeys:
            if fk.reference.resource == self.name:
                raise ValueError(
                    f"Foreign key reference resource '{fk.reference.resource}' "
                    "cannot be the same as the contract name. Self-references must "
                    "use None for the resource field."
                )
        return self

    def validate_references(
        self,
        resolver: ContractResolver,
        enforce_star_schema: bool = False,
    ) -> None:
        """Validate that every external foreign key resolves to a contract whose
        fields match the reference.

        This check is topology-agnostic by default — it only verifies that
        referenced contracts exist and their fields line up. Subclasses that
        enforce a particular topology (e.g. star schema) may flip the default
        of `enforce_star_schema` to True; see `CrossContract.validate_references`.

        Args:
            resolver: Lookup for referenced contracts by name.
            enforce_star_schema: If True, additionally require that every
                external reference points to a contract whose tableschema is a
                BaseDimensionSchema. The check is on the schema type, not the
                contract type — users pick contract types (e.g. Dimension,
                FlexibleDimension) that in turn enforce the schema constraint.

        Raises:
            ValueError: If any reference validation checks fail, with details on
                the specific errors. All failures are collected and reported in
                a single exception.
        """
        # avoid circular imports by importing here
        from crosscontract.contracts.schema.subschemas import BaseDimensionSchema

        errors: list[str] = []
        for fk in self.tableschema.foreignKeys:
            target = fk.reference.resource
            if target is None or target == self.name:
                continue

            referenced = resolver.resolve(target)
            if referenced is None:
                errors.append(f"Foreign key references unknown contract '{target}'.")
                continue
            if enforce_star_schema and not isinstance(
                referenced.tableschema, BaseDimensionSchema
            ):
                errors.append(
                    f"Foreign key references contract '{target}' with invalid schema "
                    f"type '{type(referenced.tableschema).__name__}'. Expected a "
                    "dimension schema."
                )
                continue
            try:
                fk.validate_referenced_fields(referenced.tableschema.field_names)
            except ValueError as e:
                errors.append(f"Foreign key to '{target}': {e}")

        if errors:
            raise ValueError(
                f"Reference validation failed for '{self.name}':\n  - "
                + "\n  - ".join(errors)
            )

    def validate_data(
        self,
        df: pd.DataFrame,
        resolver: ContractResolver | None = None,
        check_existing_primary_key: bool = False,
        check_existing_foreign_key: bool = False,
        check_dimension_granularity: bool = False,
        lazy: bool = True,
    ) -> pd.DataFrame:
        """Validate the data for this contract.

        The check flags govern only whether the data is additionally compared
        against the values already stored — the contract's own primary keys, and
        the referenced fields of the contracts it points to. Fetching those needs
        a `resolver`; without one the data is validated on its own.

        The primary key is always checked within the data: duplicated or missing
        key values fail regardless of `check_existing_primary_key`. The foreign
        key check is different: `check_existing_foreign_key=False` suppresses it
        *entirely*, so a self-referencing foreign key is not checked against the
        data's own rows either.

        Args:
            df (pd.DataFrame): The data to validate.
            resolver (ContractResolver | None, optional): Supplier of the stored
                values. Required only when one of the check flags is set.
                Defaults to `None`.
            check_existing_primary_key (bool): If True, also check the primary
                key against the values already stored for this contract.
                Defaults to False.
            check_existing_foreign_key (bool): If True, also check the foreign
                keys against the values already stored for the contracts they
                reference. Defaults to False.
            check_dimension_granularity (bool): If True, also check that no group
                of otherwise-identical rows reports a member of a hierarchical
                dimension alongside one of its descendants, which would count
                that member twice when the data is summed. Only a ValueVariable
                is checked, and only its references to a `Dimension`; a
                `FlexibleDimension` is flat and has nothing to check.
                Defaults to False.
            lazy (bool): If True, collect all validation errors and raise them
                together. If False, raise the first error encountered. Defaults
                to True.

        Returns:
            pd.DataFrame: The validated data.

        Raises:
            ValueError: If a check against stored values is requested without a
                `resolver`.
            SchemaValidationError: If the data does not conform to the schema.
        """
        # an empty list still checks the key within the data
        existing_primary_keys: list[tuple] = []
        foreign_key_values: dict[tuple[str, ...], list[tuple]] | None = None
        dimension_hierarchies: dict[str, dict[str, str | None]] | None = None
        if resolver is None:
            if (
                check_existing_primary_key
                or check_existing_foreign_key
                or check_dimension_granularity
            ):
                raise ValueError(
                    f"Contract '{self.name}': checking against existing values requires"
                    " a resolver. Pass resolver=, or leave check_existing_primary_key, "
                    "check_existing_foreign_key, and check_dimension_granularity "
                    "False to validate the data on its own."
                )
        else:
            if check_existing_primary_key and self.tableschema.primaryKey:
                existing_primary_keys = self._get_existing_values(
                    resolver, self.name, list(self.tableschema.primaryKey)
                )

            if check_existing_foreign_key and self.tableschema.foreignKeys:
                foreign_key_values = {}
                for fk in self.tableschema.foreignKeys.root:
                    existing_values = self._get_existing_values(
                        resolver,
                        fk.reference.resource or self.name,
                        fk.reference.fields,
                    )
                    foreign_key_values[tuple(fk.fields)] = existing_values

            if check_dimension_granularity and isinstance(
                self.tableschema, ValueVariableSchema
            ):
                dimension_hierarchies = self._resolve_dimension_hierarchies(resolver)

        df = self.tableschema.validate_dataframe(
            df,
            primary_key_values=existing_primary_keys,
            foreign_key_values=foreign_key_values,
            dimension_hierarchies=dimension_hierarchies,
            lazy=lazy,
        )
        return df

    def _get_existing_values(
        self, resolver: ContractResolver, contract_name: str, columns: list[str]
    ) -> list[tuple]:
        """Get the stored values of the given columns as tuples.

        Serves both the primary key lookup against this contract and the
        foreign key lookups against the contracts it references. The returned
        frame is reindexed by `columns` before tuple-ification, because a
        foreign key's referring and referenced fields correspond by position,
        while a frame's own column order is whatever the resolver returned.

        Args:
            resolver (ContractResolver): Supplier of the stored values.
            contract_name (str): The name of the contract to read from.
            columns (list[str]): The columns to read, in the order the returned
                tuples must follow.

        Returns:
            list[tuple]: One tuple per row, with the values ordered as `columns`.
        """
        df_ = resolver.get_data(
            name=contract_name,
            columns=columns,
            unique=True,
        )[columns]
        return [tuple(row) for row in df_.itertuples(index=False, name=None)]

    def _resolve_dimension_hierarchies(
        self, resolver: ContractResolver
    ) -> dict[str, dict[str, str | None]] | None:
        """Read the hierarchy of every referenced dimension.

        Keys are the foreign key field names, and values map each member of the
        dimension to its parent, or to `None` where it has none.

        Args:
            resolver (ContractResolver): Supplier of the stored values.

        Returns:
            dict[str, dict[str, str | None]] | None: The resolved dimension
                hierarchies. If no dimension hierarchies are found, returns None.

        Raises:
            ValueError: If a referenced contract does not resolve.
        """
        dimension_hierarchies: dict[str, dict[str, str | None]] = {}
        # for each Dimension, get the hierarchy from the resolver
        for fk in self.tableschema.foreignKeys.root:
            if len(fk.fields) > 1 or fk.reference.resource is None:
                # skip composite foreign keys for dimension hierarchy checks
                # and self-references
                continue
            fk_contract = resolver.resolve(fk.reference.resource)
            if fk_contract is None:
                raise ValueError(
                    f"Contract '{self.name}': cannot check the granularity "
                    f"of '{fk.fields[0]}' because the referenced contract "
                    f"'{fk.reference.resource}' does not resolve."
                )
            if not isinstance(fk_contract.tableschema, DimensionSchema):
                # only consider foreign keys referencing dimension tables
                continue

            field = fk.fields[0]
            # the referring key names the column it points at, while 'parent_id'
            # is fixed by the rigid DimensionSchema template
            id_col = fk.reference.fields[0]
            parent_map = (
                resolver.get_data(
                    name=fk_contract.name, unique=True, columns=[id_col, "parent_id"]
                )
                .set_index(id_col)["parent_id"]
                .replace({np.nan: None, pd.NA: None})
                .to_dict()
            )

            dimension_hierarchies[field] = parent_map  # type: ignore[assignment]

        return dimension_hierarchies or None
