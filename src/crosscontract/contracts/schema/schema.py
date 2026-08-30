from collections.abc import Iterator
from functools import cached_property
from pathlib import Path
from typing import Annotated, Any, ClassVar, Literal, Self

import pandas as pd
import pandera.pandas as pa
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import MetaData, Table

from ..._helpers import read_yaml_or_json_file
from .adapters import PanderaAdapter
from .field_descriptors import FieldDescriptors
from .fields import DateTimeField, IntegerField, ListField, NumberField, StringField
from .reference import ForeignKeys, PrimaryKey
from .validation import validate_dataframe as validate_dataframe_schema

FieldUnion = Annotated[
    IntegerField | NumberField | StringField | DateTimeField | ListField,
    Field(discriminator="type"),
]


class MandatoryField(BaseModel):
    """
    A helper class to define mandatory fields in the schema. This is used for
    validation purposes to ensure that certain fields are always present in the
    schema.
    """

    name: str = Field(description="The name of the mandatory field.")
    type: Literal["integer", "number", "string", "datetime", "list"] | None = Field(
        default=None, description="The type of the mandatory field."
    )
    description: str = Field(
        description="A description of the mandatory field and its purpose."
    )


class TableSchema(BaseModel):
    """
    A Frictionless Table Schema compatible schema definition.
    Includes fields, primary keys, foreign keys, and field descriptors.
    """

    _mandatory_fields: ClassVar[list[MandatoryField]] = []
    """Fields that a schema subclass is required to declare.

    Override in subclasses to enforce domain-specific invariants.
    """

    table_type: Literal["General"] = Field(
        default="General",
        description="Type of the table determines the structure of the schema.",
        exclude=True,
        repr=False,
    )

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
    def _validate_mandatory_fields(self) -> Self:
        """Validate that all mandatory fields are present and of the correct type."""
        errors: list[str] = []
        for spec in self._mandatory_fields:
            field = self.get(spec.name)
            if field is None:
                errors.append(f"missing field '{spec.name}' — {spec.description}")
            elif spec.type is not None and field.type != spec.type:
                errors.append(
                    f"field '{spec.name}' must be of type '{spec.type}', "
                    f"got '{field.type}' — {spec.description}"
                )
        if errors:
            raise ValueError(
                f"Mandatory field validation failed for "
                f"'{type(self).__name__}':\n  - " + "\n  - ".join(errors)
            )
        return self

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
        from .adapters import SQLAlchemyPostgresAdapter

        if metadata is None:
            metadata = MetaData()
        if table_name is None:
            table_name = f"dct_{getattr(self, 'name', 'contract_table')}"
        return SQLAlchemyPostgresAdapter.convert_schema(
            self, metadata=metadata, table_name=table_name
        )

    def to_pandera_schema(
        self,
        primary_key_values: list[tuple[Any, ...]] | None = None,
        foreign_key_values: dict[tuple[str, ...], list[tuple[Any, ...]]] | None = None,
    ) -> pa.DataFrameSchema:
        """Convert the TableSchema to a Pandera DataFrameSchema. The schema includes
        all column level checks but does not include any checking of external
        or cross-table checks.

        Args:
            primary_key_values (list[tuple[Any, ...]] | None, optional): The
                primary keys already stored for this contract. With `None` the
                key is checked within the DataFrame alone.
                Defaults to `None`.
            foreign_key_values (dict[tuple[str, ...], list[tuple[Any, ...]]] |
                None, optional): The referenced values already stored, keyed by
                the tuple of referring fields. With `None` a self-referencing
                key is checked against the DataFrame's own rows and an external
                reference is not checked at all.
                Defaults to `None`.

        Returns:
            pa.DataFrameSchema: The converted Pandera DataFrameSchema.
        """
        return PanderaAdapter.convert_schema(
            self,
            primary_key_values=primary_key_values,
            foreign_key_values=foreign_key_values,
        )

    def to_pydantic_model(
        self, model_name: str | None = None, base_class: type[BaseModel] = BaseModel
    ) -> type[BaseModel]:
        from .adapters import PydanticAdapter

        if model_name is None:
            model_name = getattr(self, "name", "ContractModel")
        return PydanticAdapter.convert_schema(
            self, name=model_name, base_class=base_class
        )

    def validate_dataframe(
        self,
        df: Any,
        primary_key_values: list[tuple[Any, ...]] | None = None,
        foreign_key_values: dict[tuple[str, ...], list[tuple[Any, ...]]] | None = None,
        lazy: bool = True,
    ) -> pd.DataFrame:
        """Validate a DataFrame against the schema.

        The checks the schema requires of its own data always run and cannot be
        switched off: the primary key must be non-null and unique within the
        DataFrame, a self-referencing foreign key must resolve against the
        DataFrame's own rows, and a `Dimension` must form a valid hierarchy.

        Beyond those, existing primary key and foreign key values may be provided.
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
                With None the key is still checked within the DataFrame alone.
                Default is None.
            foreign_key_values (dict[tuple[str, ...], list[tuple[Any, ...]]] | None):
                Existing foreign key values to check against. This is provided as a
                dictionary where the keys are the tuples of fields that refer to the
                referenced values, and the values are lists of tuples representing the
                existing referenced values.
                Note: In the case of self-referencing foreign keys, the values in the
                    DataFrame are considered automatically, i.e., the referring fields
                    are validated against the union of the provided values and the
                    values in the DataFrame.
                With None a self-referencing key is still checked against the
                DataFrame's own rows; an external reference is not checked.
                Default is None.
            lazy (bool): Whether to perform lazy validation, collecting all errors.
                Defaults to True.

        Raises:
            SchemaValidationError: If the DataFrame does not conform to the
                schema. This exception wraps underlying `pandera` validation
                errors raised during DataFrame validation.

        Returns:
            pd.DataFrame: The validated DataFrame. If validation fails, an exception
                is raised and this return value is not reached.
        """
        pandera_schema = self.to_pandera_schema(
            primary_key_values=primary_key_values,
            foreign_key_values=foreign_key_values,
        )

        df = validate_dataframe_schema(
            df=df,
            pandera_schema=pandera_schema,
            lazy=lazy,
        )
        return df
