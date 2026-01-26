from collections.abc import Iterator
from functools import cached_property
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any, Literal

try:
    from typing import Self
except ImportError:
    from typing_extensions import Self

import pandera.pandas as pa
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import MetaData, Table

from ..utils import read_yaml_or_json_file
from .field_descriptors import FieldDescriptors
from .fields import (
    DateTimeField,
    IntegerField,
    NumberField,
    StringField,
)
from .reference import ForeignKeys, PrimaryKey

if TYPE_CHECKING:  # pragma: no cover
    pass

FieldUnion = Annotated[
    IntegerField | NumberField | StringField | DateTimeField,
    Field(discriminator="type"),
]


class TableSchema(BaseModel):
    """
    A Frictionless Table Schema compatible schema definition.
    Includes fields, primary keys, foreign keys, and field descriptors.
    """

    model_config = ConfigDict(
        title="TableSchema", ignored_types=(cached_property,), str_strip_whitespace=True
    )

    fields: list[FieldUnion] = Field(
        default_factory=list,
        description="An `array` of Table Schema Field objects.",
        min_length=1,
    )
    primaryKey: PrimaryKey = Field(
        default_factory=PrimaryKey,
        description=(
            "The primary key definition. Primary keys are used to uniquely "
            "identify records in the data."
        ),
    )
    foreignKeys: ForeignKeys = Field(
        default_factory=ForeignKeys,
        description=(
            "The foreign key definitions. Foreign keys are used to establish "
            "relationships between tables."
        ),
    )
    fieldDescriptors: FieldDescriptors | None = None

    # def __iter__(self) -> Iterator[FieldUnion]:
    #     return iter(self.fields)

    def field_iterator(self) -> Iterator[FieldUnion]:
        """Returns an iterator over the fields in the schema."""
        return iter(self.fields)

    def __getitem__(self, key: int | str) -> FieldUnion:
        if isinstance(key, int):
            return self.fields[key]
        try:
            return self._name_index[key]
        except KeyError as e:
            raise KeyError(f"Field '{key}' not found in Schema.") from e

    def __len__(self) -> int:
        return len(self.fields)

    @cached_property
    def _name_index(self) -> dict[str, FieldUnion]:
        """
        Creates a dictionary mapping field names to field objects.
        This runs only once when accessed, providing O(1) lookups thereafter.
        """
        return {field.name: field for field in self.fields}

    @property
    def field_names(self) -> list[str]:
        """Returns a list of all field names."""
        return list(self._name_index)

    def get(self, name: str) -> FieldUnion | None:
        """Returns the field by name, or None if it doesn't exist."""
        return self._name_index.get(name)

    def has_fields(self, field_names: str | list[str]) -> bool:
        """Check if a field with the given name exists in the data contract."""
        if isinstance(field_names, str):
            return field_names in self.field_names
        else:
            return all(name in self.field_names for name in field_names)

    @model_validator(mode="after")
    def validate_structural_integrity(self) -> "TableSchema":
        """
        Validates that all key definitions refer to fields that actually
        exist in the schema.
        """
        valid_fields = self.field_names

        if self.primaryKey:
            self.primaryKey.validate_fields(valid_fields)

        if self.foreignKeys:
            for fk in self.foreignKeys:
                fk.validate_fields(valid_fields)
                if fk.reference.resource is None:
                    fk.validate_referenced_fields(valid_fields)

        if self.fieldDescriptors is not None:
            self.fieldDescriptors.validate_all_exist(valid_fields)
        return self

    @classmethod
    def from_file(cls, file_path: str | Path) -> Self:
        data = read_yaml_or_json_file(file_path)
        return cls.model_validate(data)

    def to_sa_table(
        self, metadata: MetaData | None = None, table_name: str | None = None
    ) -> Table:
        from .converter import convert_schema_to_sqlalchemy

        if metadata is None:
            metadata = MetaData()
        if table_name is None:
            table_name = f"dct_{getattr(self, 'name', 'contract_table')}"
        return convert_schema_to_sqlalchemy(
            self, metadata=metadata, table_name=table_name
        )

    def to_pandera_schema(
        self,
        name: str | None = None,
    ) -> pa.DataFrameSchema:
        from .converter import convert_schema_to_pandera

        if name is None:
            name = getattr(self, "name", "contract_schema")

        pandera_schema: pa.DataFrameSchema = convert_schema_to_pandera(self, name=name)

        return pandera_schema

    def to_pydantic_model(
        self, model_name: str | None = None, base_class: type[BaseModel] | None = None
    ) -> type[BaseModel]:
        from .converter import convert_schema_to_pydantic

        if model_name is None:
            model_name = getattr(self, "name", "ContractModel")
        return convert_schema_to_pydantic(self, name=model_name, base_class=base_class)

    def validate_dataframe(
        self,
        df: Any,
        primary_key_values: list[tuple[Any, ...]] | None = None,
        foreign_key_values: dict[tuple[str, ...], list[tuple[Any, ...]]] | None = None,
        skip_primary_key_validation: bool = False,
        skip_foreign_key_validation: bool = False,
        lazy: bool = True,
        backend: Literal["pandas"] = "pandas",
    ) -> None:
        """Validate a DataFrame against the schema.
        It allows to provide existing primary key and foreign key values for validation.
        If provided, the primary key uniqueness is checked against the union of the
        existing and the DataFrame values. Similarly, foreign key integrity is checked
        against the union of existing and DataFrame values in case of self-referencing
        foreign keys.

        Args:
            df (Any): The DataFrame to validate.
            primary_key_values (list[tuple[Any, ...]] | None): Existing primary key
                values to check for uniqueness.
                Note: The uniqueness of the primary key is validated is checked against
                    the union of the provided values and the values in the DataFrame.
            foreign_key_values (dict[tuple[str, ...], list[tuple[Any, ...]]] | None):
                Existing foreign key values to check against. This is provided as a
                dictionary where the keys are the tuples of fields that refer to the
                referenced values, and the values are lists of tuples representing the
                existing referenced values.
                Note: In the case of self-referencing foreign keys, the values in the
                    DataFrame are considered automatically, i.e., the referring fields
                    are validated against the union of the provided values and the
                    values in the DataFrame.
            skip_primary_key_validation (bool): Whether to skip primary key validation.
            skip_foreign_key_validation (bool): Whether to skip foreign key validation.
            lazy (bool): Whether to perform lazy validation, collecting all errors.
                Defaults to True.
            backend (Literal["pandas"]): The backend to use for validation.
                Currently, only "pandas" is supported.
        Raises:
            pandera.errors.SchemaErrors: If the DataFrame does not conform to the
            schema.
        """
        if backend == "pandas":
            from .validation.validate_pandas_dataframe import (
                validate_pandas_dataframe,
            )

            validate_pandas_dataframe(
                schema=self,
                df=df,
                primary_key_values=primary_key_values,
                foreign_key_values=foreign_key_values,
                skip_primary_key_validation=skip_primary_key_validation,
                skip_foreign_key_validation=skip_foreign_key_validation,
                lazy=lazy,
            )
        else:
            raise ValueError(
                f"Unsupported backend '{backend}' for DataFrame validation."
            )
