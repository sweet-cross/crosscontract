import pytest
from pydantic import TypeAdapter, ValidationError

from crosscontract.transformations.transformation import (
    CastColumn,
    DropColumns,
    DropRowsByValue,
    MapColumnValues,
    ParseDatetimeColumn,
    RenameColumns,
    TransformationUnion,
)

_adapter: TypeAdapter = TypeAdapter(TransformationUnion)


@pytest.mark.parametrize(
    "payload, expected_cls",
    [
        ({"type": "rename_columns", "mapping": {"A": "col_A"}}, RenameColumns),
        ({"type": "drop_columns", "columns": ["A"]}, DropColumns),
        (
            {"type": "drop_rows_by_value", "column_name": "A", "values": [1]},
            DropRowsByValue,
        ),
        (
            {"type": "map_column_values", "column_name": "A", "mapping": {1: 2}},
            MapColumnValues,
        ),
        (
            {"type": "cast_column", "column_name": "A", "to_type": "integer"},
            CastColumn,
        ),
        (
            {"type": "parse_datetime_column", "column_name": "A"},
            ParseDatetimeColumn,
        ),
    ],
    ids=[
        "rename_columns",
        "drop_columns",
        "drop_rows_by_value",
        "map_column_values",
        "cast_column",
        "parse_datetime_column",
    ],
)
def test_discriminator_resolves_correct_model(payload, expected_cls):
    """The `type` discriminator selects the right model in a union."""
    assert isinstance(_adapter.validate_python(payload), expected_cls)


def test_extra_keys_forbidden():
    """Unknown keys raise a ValidationError (extra='forbid')."""
    with pytest.raises(ValidationError):
        _adapter.validate_python(
            {
                "type": "map_column_values",
                "column_name": "A",
                "mapping": {1: 2},
                "bogus": "x",
            }
        )


def test_unknown_type_rejected():
    """An unknown discriminator value is rejected by the union."""
    with pytest.raises(ValidationError):
        _adapter.validate_python({"type": "does_not_exist", "columns": ["A"]})
