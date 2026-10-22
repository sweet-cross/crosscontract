from __future__ import annotations

from typing import Annotated

from pydantic import Field

# Import the leaf modules rather than this package's `__init__`, which re-exports
# this union: going through `__init__` would make the import circular.
from .column_transformations import CastColumn, MapColumnValues, ParseDatetimeColumn
from .dataframe_transformations import DropColumns, DropRowsByValue, RenameColumns

TransformationUnion = Annotated[
    # Pydantic will check the 'type' field to decide which class to use
    RenameColumns
    | DropColumns
    | DropRowsByValue
    | MapColumnValues
    | CastColumn
    | ParseDatetimeColumn,
    Field(discriminator="type"),
]
