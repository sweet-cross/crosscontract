from pathlib import Path
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..schema import TableSchema
from ..utils import read_yaml_or_json_file


class BaseMetaData(BaseModel):
    """
    The BaseMetadata class encapsulates the essential metadata attributes
    required for defining a data contract. Every data contract MUST include
    these metadata fields to ensure proper identification and description.
    To extend the metadata for specific use cases, inherit from this class
    and add additional fields as necessary. Then use the extended metadata
    class as a base for your custom contract together with BaseContract.

    Attributes:
        name (str): A unique identifier for the data contract.
            Must contain only alphanumeric characters, underscores, or hyphens.
            Maximum length is 100 characters.
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(
        pattern="^[a-zA-Z0-9_-]+$",
        max_length=100,
        description="A unique identifier for the data contract.",
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
    def validate_self_reference(self) -> Self:
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
