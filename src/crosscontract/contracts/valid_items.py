"""This module contains the standards used across the contract models."""

from typing import Annotated

from pydantic import StringConstraints

valid_field_name_pattern = None
max_field_name_length = None
ValidFieldName = Annotated[
    str,
    StringConstraints(
        pattern=valid_field_name_pattern, max_length=max_field_name_length
    ),
]
