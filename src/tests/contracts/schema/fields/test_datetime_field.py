from datetime import UTC, datetime

import pandas as pd
import pandera.pandas as pa
import pytest
from sqlalchemy import DateTime

from crosscontract.contracts.schema.fields.datetime_field import (
    DateTimeConstraint,
    DateTimeField,
    parse_datetime,
)


def test_parse_datetime():
    assert parse_datetime("2023-01-01 00:00", "%Y-%m-%d %H:%M") == datetime(
        2023, 1, 1, 0, 0, tzinfo=UTC
    )
    assert parse_datetime(datetime(2023, 1, 1, 0, 0), "%Y-%m-%d %H:%M") == datetime(
        2023, 1, 1, 0, 0, tzinfo=UTC
    )
    assert parse_datetime(
        datetime(2023, 1, 1, 0, 0, tzinfo=UTC), "%Y-%m-%d %H:%M"
    ) == datetime(2023, 1, 1, 0, 0, tzinfo=UTC)
    assert parse_datetime(None, "%Y-%m-%d %H:%M") is None
    with pytest.raises(ValueError):
        parse_datetime(12, "%Y-%m-%d %H:%M")


class TestDateTimeField:
    def test_datetime_field(self):
        field = DateTimeField(name="test_datetime")
        assert field.python_type == datetime
        assert field.name == "test_datetime"
        assert field.format == "%Y-%m-%d %H:%M"
        assert field.constraints == DateTimeConstraint()
        kwargs = field.get_pydantic_field_kwargs()
        assert "ge" not in kwargs
        assert "le" not in kwargs
        assert "parse_datetime" in field.get_pydantic_validators()

    def test_minimum_constraint(self):
        constraint = DateTimeConstraint(
            minimum="2023-01-01 00:00", maximum="2023-10-10 00:00"
        )
        field = DateTimeField(name="test_datetime", constraints=constraint)
        kwargs = field.get_pydantic_field_kwargs()
        assert "ge" in kwargs
        assert kwargs["ge"] == datetime.strptime(
            "2023-01-01 00:00", field.format
        ).replace(tzinfo=UTC)
        assert "le" in kwargs
        assert kwargs["le"] == datetime.strptime(
            "2023-10-10 00:00", field.format
        ).replace(tzinfo=UTC)


class TestPanderaKwargs:
    def test_pandera_kwargs(self):
        constraint = DateTimeConstraint(
            minimum="2023-01-01 00:00", maximum="2023-10-10 00:00"
        )
        field = DateTimeField(name="test_datetime", constraints=constraint)
        kwargs = field.get_pandera_kwargs()
        assert "checks" in kwargs
        assert len(kwargs["checks"]) == 2
        assert kwargs["checks"][0] == pa.Check.ge(
            datetime.strptime("2023-01-01 00:00", field.format).replace(tzinfo=UTC)
        )
        assert kwargs["checks"][1] == pa.Check.le(
            datetime.strptime("2023-10-10 00:00", field.format).replace(tzinfo=UTC)
        )

    def test_pandera_kwargs_no_constraint(self):
        field = DateTimeField(name="test_datetime")
        kwargs = field.get_pandera_kwargs()
        assert "checks" in kwargs
        assert len(kwargs["checks"]) == 0

    def test_pandera_validation(self):
        field = DateTimeField(name="test_datetime")
        kwargs = field.get_pandera_kwargs()
        col = pa.Column(**kwargs)
        schema = pa.DataFrameSchema(columns={col.name: col}, name="test", coerce=True)

        df = pd.DataFrame(
            {
                "test_datetime": [
                    "2023-01-01 00:00",
                    "2023-10-10 00:00",
                    "2023-05-05 12:30",
                ]
            }
        )
        df = schema.validate(df)
        df_expected = df.assign(
            test_datetime=pd.to_datetime(
                df["test_datetime"], format="%Y-%m-%d %H:%M", utc=True
            )
        )
        pd.testing.assert_frame_equal(df, df_expected)

        # raise validation error
        df = pd.DataFrame(
            {
                "test_datetime": [
                    "01-01-2023 00:00",
                    "10-10-2023 00:00",
                    "05-05-2023 12:30",
                ]
            }
        )
        with pytest.raises(pa.errors.SchemaError):
            schema.validate(df)

    def test_pandera_validation_with_constraint(self):
        constraint = DateTimeConstraint(
            minimum="2023-01-01 00:00", maximum="2023-10-10 00:00"
        )
        field = DateTimeField(name="test_datetime", constraints=constraint)
        kwargs = field.get_pandera_kwargs()
        col = pa.Column(**kwargs)
        schema = pa.DataFrameSchema(columns={col.name: col}, name="test", coerce=True)

        df = pd.DataFrame(
            {
                "test_datetime": [
                    "2023-01-01 00:00",
                    "2023-10-10 00:00",
                    # "2023-05-05 12:30",
                ]
            }
        )
        df = schema.validate(df)
        df_expected = df.assign(
            test_datetime=pd.to_datetime(
                df["test_datetime"], format="%Y-%m-%d %H:%M", utc=True
            )
        )
        pd.testing.assert_frame_equal(df, df_expected)

        # raises as to late
        df = pd.DataFrame(
            {
                "test_datetime": [
                    "2023-01-01 00:00",
                    "2023-10-10 00:00",
                    "2024-05-05 12:30",
                ]
            }
        )
        with pytest.raises(pa.errors.SchemaError):
            schema.validate(df)

        # raises as to early
        df = pd.DataFrame(
            {
                "test_datetime": [
                    "2023-01-01 00:00",
                    "2023-10-10 00:00",
                    "2020-05-05 12:30",
                ]
            }
        )
        with pytest.raises(pa.errors.SchemaError):
            schema.validate(df)

    def test_pandera_validation_schema_settings(self):
        field = DateTimeField(name="test_datetime", format="%d-%m-%Y %H:%M")
        kwargs = field.get_pandera_kwargs()
        col = pa.Column(**kwargs)
        schema = pa.DataFrameSchema(columns={col.name: col}, name="test", coerce=True)

        # raises as wrong format
        df = pd.DataFrame(
            {
                "test_datetime": [
                    "2023-01-01 00:00",
                    "2023-10-10 00:00",
                    "2023-05-05 12:30",
                ]
            }
        )
        with pytest.raises(pa.errors.SchemaError):
            schema.validate(df)

        # correct format
        df = pd.DataFrame(
            {
                "test_datetime": [
                    "01-01-2023 00:00",
                    "10-10-2023 00:00",
                    "05-05-2023 12:30",
                ]
            }
        )
        df = schema.validate(df)
        df_expected = df.assign(
            test_datetime=pd.to_datetime(
                df["test_datetime"], format="%Y-%m-%d %H:%M", utc=True
            )
        )
        pd.testing.assert_frame_equal(df, df_expected)


class TestToColumn:
    def test_to_sqlalchemy_column(self):
        field = DateTimeField(name="test_datetime")
        column = field.to_sqlalchemy_column()
        assert column.name == "test_datetime"
        assert isinstance(column.type, DateTime)
        assert column.type.timezone is True
        assert column.nullable is True

    def test_to_sqlalchemy_column_not_nullable(self):
        constraint = DateTimeConstraint(required=True)
        field = DateTimeField(name="test_datetime", constraints=constraint)
        column = field.to_sqlalchemy_column()
        assert column.name == "test_datetime"
        assert isinstance(column.type, DateTime)
        assert column.type.timezone is True
        assert column.nullable is False
