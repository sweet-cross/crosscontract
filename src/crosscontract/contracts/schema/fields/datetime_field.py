from typing import Literal

from pydantic import Field

from .base import BaseConstraint, BaseField


class DateTimeConstraint(BaseConstraint):
    minimum: str | None = Field(
        default=None,
        description="The minimal datetime for data values in the format specified.",
    )
    maximum: str | None = Field(
        default=None,
        description="The maximal datetime for data values in the format specified.",
    )


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
