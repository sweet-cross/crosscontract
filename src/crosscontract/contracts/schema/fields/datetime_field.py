from datetime import UTC, datetime
from typing import Any, Literal

import pandera.pandas as pa
from pandera.engines import pandas_engine
from pydantic import Field

from .base import BaseConstraint, BaseField


def parse_datetime(value: str | datetime | None, format: str) -> datetime | None:
    """Parses a datetime string into a datetime object. That is
    timezone aware.

    Args:
        value: The datetime string or datetime object to parse.
        format: The format string to use for parsing.

    Returns:
        A timezone-aware datetime object or None if parsing fails.
    """
    if value is None:
        return None
    # convert to datetime
    if isinstance(value, str):
        val = datetime.strptime(value, format)
    elif isinstance(value, datetime):
        val = value
    else:
        raise ValueError("Value must be a string or datetime object.")

    # check the time zone
    if val.tzinfo is None:
        val = val.replace(tzinfo=UTC)
    else:
        val = val.astimezone(UTC)
    return val


class DateTimeConstraint(BaseConstraint):
    minimum: str | None = Field(
        default=None,
        description="The minimal datetime for data values in the format specified.",
    )
    maximum: str | None = Field(
        default=None,
        description="The maximal datetime for data values in the format specified.",
    )

    def get_pandera_kwargs(self) -> dict[str, Any]:
        """Returns the keyword arguments to create a pandera Column for
        this constraint."""
        # handling in parent to have access to format parameter
        return super().get_pandera_kwargs()


class DateTimeField(BaseField):
    type: Literal["datetime"] = Field(
        default="datetime",
        description="The type of the field, which is 'datetime' for this class.",
    )

    format: str = Field(
        default="%Y-%m-%d %H:%M",
        description=(
            "The format of the datetime field given following the date "
            "formatting syntax of C / Python [strftime](http://strftime.org/). "
            "Default: %Y-%m-%d %H:%M, i.e., YYYY-MM-DD HH:MM. "
            "Note: All datetimes are assumed to be given as UTC time."
        ),
    )
    constraints: DateTimeConstraint = Field(
        default_factory=DateTimeConstraint,
        description="Constraints for the datetime field.",
    )

    @property
    def python_type(self) -> type:  # type: ignore
        """Returns the Python type of the field."""
        return datetime

    def get_pandera_kwargs(self) -> dict[str, Any]:
        """Returns the pandera field kwargs for the field."""
        kwargs = super().get_pandera_kwargs()

        kwargs["dtype"] = pandas_engine.DateTime(
            tz=UTC,
            to_datetime_kwargs={"format": self.format},  # type: ignore
        )
        # add the constraints here since we need access to the format option
        if self.constraints.minimum is not None:
            kwargs["checks"].append(
                pa.Check.ge(
                    datetime.strptime(self.constraints.minimum, self.format).replace(
                        tzinfo=UTC
                    )
                )
            )
        if self.constraints.maximum is not None:
            kwargs["checks"].append(
                pa.Check.le(
                    datetime.strptime(self.constraints.maximum, self.format).replace(
                        tzinfo=UTC
                    )
                )
            )
        # kwargs["to_datetime_kwargs"] = {"format": self.format, "utc": True}
        return kwargs
