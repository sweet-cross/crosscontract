from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, create_model, field_validator
from pydantic.fields import FieldInfo

from crosscontract.contracts.schema.fields import (
    DateTimeField,
    IntegerField,
    ListField,
    NumberField,
    StringField,
)
from crosscontract.contracts.schema.fields.base import BaseField
from crosscontract.contracts.schema.schema import TableSchema

from .utils import parse_datetime


def convert_schema_to_pydantic(
    schema: TableSchema,
    name: str = "ConvertedModel",
    base_class: type[BaseModel] = BaseModel,
) -> type[BaseModel]:
    """Convert the schema into a corresponding pydantic model.

    Args:
        name (str): The name of the resulting pydantic model.
        base_class (type[BaseModel]): The base class for the resulting pydantic
            model.

    Returns:
        type[BaseModel]: The resulting pydantic model.

    Raises:
        NotImplementedError: If the schema contains a field type that is not yet
            supported.
    """
    return PydanticAdapter(schema).convert(name=name, base_class=base_class)


class PydanticAdapter:
    """Adapter to convert a schema into a pydantic model."""

    def __init__(self, schema: TableSchema):
        self.schema = schema

        # collectors for the field definitions and validators
        self._field_definitions: dict[str, Any] = {}
        self._validators: dict[str, Any] = {}

    def convert(
        self, name: str = "ConvertedModel", base_class: type[BaseModel] = BaseModel
    ) -> type[BaseModel]:
        """Convert the schema into a corresponding pydantic model.

        Args:
            name (str): The name of the resulting pydantic model.
            base_class (type[BaseModel]): The base class for the resulting pydantic
                model.

        Returns:
            type[BaseModel]: The resulting pydantic model.

        Raises:
            NotImplementedError: If the schema contains a field type that is not yet
                supported.
        """
        for field in self.schema.field_iterator():
            match field:
                case IntegerField() | NumberField():
                    python_type, field_info = self._convert_number_field(field)
                case StringField():
                    python_type, field_info = self._convert_string_field(field)
                case DateTimeField():
                    python_type, field_info = self._convert_datetime_field(field)
                case ListField():
                    python_type, field_info = self._convert_list_field(field)
                case _:
                    raise NotImplementedError(
                        f"Field type '{field.type}' not yet supported"
                    )
            self._field_definitions[field.name] = (python_type, field_info)
        return create_model(
            name,
            __base__=base_class,
            __validators__=self._validators,
            **self._field_definitions,
        )

    @staticmethod
    def _create_field_definition(
        python_type: type, required: bool, kwargs: dict[str, Any]
    ) -> tuple[type | Any, FieldInfo]:
        """Create a pydantic field definition for a given field.

        Args:
            python_type (type): The Python type of the field.
            required (bool): Whether the field is required or not.
            kwargs (dict[str, Any]): The keyword arguments for the pydantic Field.

        Returns:
            tuple[type, FieldInfo]: A tuple containing the Python type and the
                pydantic FieldInfo.
        """
        if required:
            return (python_type, Field(..., **kwargs))
        else:
            return (python_type | None, Field(default=None, **kwargs))

    @staticmethod
    def _setup_kwargs(field: BaseField) -> dict[str, Any]:
        """Setup the basic kwargs for a pydantic field definition based on the
        field's properties."""
        return {
            "title": field.title,
            "description": field.description,
            "json_schema_extra": {"name": field.name},
        }

    @staticmethod
    def _make_enum_validator(allowed: list):
        def _validate(v):
            if v not in allowed:
                raise ValueError(f"Value '{v}' not in enum {allowed}")
            return v

        return _validate

    def _convert_number_field(
        self, field: NumberField | IntegerField
    ) -> tuple[type, FieldInfo]:
        """Convert a NumberField to a pydantic field definition.

        Args:
            field (NumberField | IntegerField): The field to convert.

        Returns:
            tuple[type, FieldInfo]: A tuple containing the Python type and the pydantic
                FieldInfo for the field.
        """
        # get the correct python type
        python_type: type
        if isinstance(field, IntegerField):
            python_type = int
        elif isinstance(field, NumberField):
            python_type = float
        else:
            raise ValueError(f"Unsupported field type: {type(field)}")

        # get the basic field kwargs
        kwargs = self._setup_kwargs(field)

        # parse the constraints
        if field.constraints.minimum is not None:
            kwargs["ge"] = field.constraints.minimum
        if field.constraints.maximum is not None:
            kwargs["le"] = field.constraints.maximum

        # handle enum constraint
        if enum_constraint := getattr(field.constraints, "enum", None):
            self._validators[f"validate_enum_{field.name}"] = field_validator(
                field.name, mode="before"
            )(self._make_enum_validator(enum_constraint))

        return self._create_field_definition(
            python_type, field.constraints.required, kwargs
        )

    def _convert_string_field(self, field: StringField) -> tuple[type, FieldInfo]:
        """Convert a StringField to a pydantic field definition.

        Args:
            field (StringField): The field to convert.

        Returns:
            tuple[type, FieldInfo]: A tuple containing the Python type and the pydantic
                FieldInfo for the field.
        """
        python_type = str

        kwargs = self._setup_kwargs(field)
        if field.constraints.pattern is not None:
            kwargs["pattern"] = field.constraints.pattern
        if field.constraints.minLength is not None:
            kwargs["min_length"] = field.constraints.minLength
        if field.constraints.maxLength is not None:
            kwargs["max_length"] = field.constraints.maxLength
        if enum_constraint := getattr(field.constraints, "enum", None):
            self._validators[f"validate_enum_{field.name}"] = field_validator(
                field.name, mode="before"
            )(self._make_enum_validator(enum_constraint))

        return self._create_field_definition(
            python_type, field.constraints.required, kwargs
        )

    def _convert_datetime_field(self, field: DateTimeField) -> tuple[type, FieldInfo]:
        """Convert a DateTimeField to a pydantic field definition.

        Args:
            field (DateTimeField): The field to convert.

        Returns:
            tuple[type, FieldInfo]: A tuple containing the Python type and the pydantic
                FieldInfo for the field.
        """
        python_type = datetime

        kwargs = self._setup_kwargs(field)

        # parse constraints
        if field.constraints.minimum is not None:
            kwargs["ge"] = parse_datetime(field.constraints.minimum, field.format)
        if field.constraints.maximum is not None:
            kwargs["le"] = parse_datetime(field.constraints.maximum, field.format)

        # add a validator to parse the datetime string into a datetime object
        self._validators[f"check_datetime_format_{field.name}"] = field_validator(
            field.name, mode="before"
        )(lambda x, fmt=field.format: parse_datetime(x, fmt))  # type: ignore[arg-type]

        return self._create_field_definition(
            python_type, field.constraints.required, kwargs
        )

    def _convert_list_field(self, field: ListField) -> tuple[type, FieldInfo]:
        """Convert a ListField to a pydantic field definition.

        Args:
            field (ListField): The field to convert.

        Returns:
            tuple[type, FieldInfo]: A tuple containing the Python type and the pydantic
                FieldInfo for the field.
        """
        item_type_mapping: dict[str, type] = {
            "string": str,
            "integer": int,
            "number": float,
            "boolean": bool,
        }

        item_python_type = item_type_mapping.get(field.itemType)
        if item_python_type is None:  # pragma: no cover
            # this is already validated at the schema level, so this should never
            # happen but we add this check for type safety
            raise ValueError(f"Unsupported itemType: {field.itemType}")

        python_type = list[item_python_type]

        kwargs = self._setup_kwargs(field)

        # Handle constraints
        if field.constraints.minLength is not None:
            kwargs["min_length"] = field.constraints.minLength
        if field.constraints.maxLength is not None:
            kwargs["max_length"] = field.constraints.maxLength

        return self._create_field_definition(
            python_type, field.constraints.required, kwargs
        )
