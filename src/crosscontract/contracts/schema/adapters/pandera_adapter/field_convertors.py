from abc import ABC, abstractmethod
from datetime import UTC
from typing import Any, Generic, TypeVar

import pandera.pandas as pa
from pandera.engines import pandas_engine

from crosscontract.contracts.schema import (
    BaseField,
    DateTimeField,
    IntegerField,
    ListField,
    NumberField,
    StringField,
)
from crosscontract.contracts.schema.adapters.utils import parse_datetime

T = TypeVar("T", bound=BaseField)


class BaseFieldConverter(ABC, Generic[T]):
    """Base class for converting schema fields to Pandera Columns."""

    def __init__(self, field: T):
        self.field = field

    @abstractmethod
    def get_pandera_type(self) -> Any:
        """Return the pandera dtype for this field."""
        pass

    def get_checks(self) -> list[pa.Check]:
        """Return a list of base pandera checks."""
        checks = []
        # Handle enum constraint
        if enum_constraint := getattr(self.field.constraints, "enum", None):
            checks.append(pa.Check.isin(enum_constraint))
        return checks

    def get_kwargs(self) -> dict[str, Any]:
        """Assemble the kwargs needed for pa.Column."""
        kwargs: dict[str, Any] = {
            "name": self.field.name,
            "dtype": self.get_pandera_type(),
            "title": self.field.title,
            "description": self.field.description,
            "checks": self.get_checks(),
            "required": self.field.constraints.required,
            "unique": self.field.constraints.unique,
        }

        if not kwargs["required"]:
            kwargs["nullable"] = True

        return kwargs

    def convert(self) -> pa.Column:
        """Convert the field into a Pandera Column."""
        return pa.Column(**self.get_kwargs())


class NumericFieldConverter(BaseFieldConverter[IntegerField | NumberField]):
    def get_pandera_type(self) -> str | type:
        return "Int64" if isinstance(self.field, IntegerField) else float

    def get_checks(self) -> list[pa.Check]:
        checks = super().get_checks()
        if self.field.constraints.minimum is not None:
            checks.append(pa.Check.ge(self.field.constraints.minimum))
        if self.field.constraints.maximum is not None:
            checks.append(pa.Check.le(self.field.constraints.maximum))
        return checks


class StringFieldConverter(BaseFieldConverter[StringField]):
    def get_pandera_type(self) -> type:
        return str

    def get_kwargs(self) -> dict[str, Any]:
        kwargs = super().get_kwargs()
        if self.field.constraints.pattern is not None:
            kwargs["regex"] = self.field.constraints.pattern
        return kwargs

    def get_checks(self) -> list[pa.Check]:
        checks = super().get_checks()
        min_l = self.field.constraints.minLength
        max_l = self.field.constraints.maxLength

        if min_l is not None or max_l is not None:
            checks.append(pa.Check.str_length(min_value=min_l, max_value=max_l))
        return checks


class DateTimeFieldConverter(BaseFieldConverter[DateTimeField]):
    def get_pandera_type(self) -> Any:
        return pandas_engine.DateTime(
            tz=UTC, to_datetime_kwargs={"format": self.field.format}
        )

    def get_checks(self) -> list[pa.Check]:
        checks = super().get_checks()
        fmt = self.field.format

        if self.field.constraints.minimum is not None:
            minimum = self.field.constraints.minimum
            checks.append(
                pa.Check(
                    lambda s: s.apply(
                        lambda dt: parse_datetime(dt, fmt)
                        >= parse_datetime(minimum, fmt)
                    )
                )
            )

        if self.field.constraints.maximum is not None:
            maximum = self.field.constraints.maximum
            checks.append(
                pa.Check(
                    lambda s: s.apply(
                        lambda dt: parse_datetime(dt, fmt)
                        <= parse_datetime(maximum, fmt)
                    )
                )
            )
        return checks


class ListFieldConverter(BaseFieldConverter[ListField]):
    def get_pandera_type(self) -> Any:
        type_mapping: dict[str, type | str] = {
            "string": list[str],
            "integer": list[int],
            "number": list[float],
            "boolean": list[bool],
        }
        pandera_type = type_mapping.get(self.field.itemType)
        if pandera_type is None:
            raise ValueError(f"Unsupported itemType: {self.field.itemType}")
        return pandera_type

    def get_checks(self) -> list[pa.Check]:
        checks = super().get_checks()
        if self.field.constraints.minLength is not None:
            min_l = self.field.constraints.minLength
            checks.append(pa.Check(lambda s: s.apply(lambda lst: len(lst) >= min_l)))

        if self.field.constraints.maxLength is not None:
            max_l = self.field.constraints.maxLength
            checks.append(pa.Check(lambda s: s.apply(lambda lst: len(lst) <= max_l)))
        return checks


def get_field_converter(field: BaseField) -> BaseFieldConverter:
    """Factory method to get the correct converter for a field.

    Args:
        field (BaseField): The field for which to get the converter.

    Returns:
        BaseFieldConverter: The appropriate converter for the given field.

    Raises:
        NotImplementedError: If the field type is not supported.
    """
    match field:
        case IntegerField() | NumberField():
            return NumericFieldConverter(field)
        case StringField():
            return StringFieldConverter(field)
        case DateTimeField():
            return DateTimeFieldConverter(field)
        case ListField():
            return ListFieldConverter(field)
        case _:  # pragma: no cover
            raise NotImplementedError(
                f"Field type '{type(field).__name__}' not yet supported"
            )
