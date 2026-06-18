from pathlib import Path
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..._helpers import read_yaml_or_json_file
from ..schema import TableSchema
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
