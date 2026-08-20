from __future__ import annotations

from typing import Annotated

from pydantic import Field

from . import (
    CastType,
    DropColumns,
    DropRowsByValues,
    MapColumnValues,
    ParseDatetimeColumn,
    RenameColumns,
)

TransformationUnion = Annotated[
    # Pydantic will check the 'type' field to decide which class to use
    RenameColumns
    | DropColumns
    | DropRowsByValues
    | MapColumnValues
    | CastType
    | ParseDatetimeColumn,
    Field(discriminator="type"),
]
