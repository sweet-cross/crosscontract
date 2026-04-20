from typing import Literal

import pytest
from pydantic import Field

from crosscontract.contracts.schema.subschemas import BaseDimensionSchema

field_data = [
    {"name": "id", "type": "integer"},
    {"name": "parent_id", "type": "integer"},
    {"name": "name", "type": "string"},
]


class ConcreteDimensionSchema(BaseDimensionSchema):
    """Minimal concrete subclass used to exercise BaseDimensionSchema validators."""

    table_type: Literal["ConcreteDimension"] = Field(  # type: ignore[assignment]
        default="ConcreteDimension",
        exclude=True,
        repr=False,
    )


@pytest.fixture
def valid_data():
    """Data that satisfies all BaseDimensionSchema invariants."""
    return {
        "primaryKey": ["id"],
        "foreignKeys": [
            {
                "fields": ["parent_id"],
                "reference": {"resource": None, "fields": ["id"]},
            }
        ],
        "fields": field_data,
    }


class TestAbstractInstantiation:
    def test_direct_instantiation_fails(self):
        """Instantiating the abstract base class directly is rejected."""
        with pytest.raises(TypeError, match="abstract"):
            BaseDimensionSchema.model_validate(
                {"primaryKey": ["id"], "fields": field_data}
            )

    def test_subclass_instantiation_succeeds(self, valid_data):
        """Concrete subclasses bypass the abstract guard."""
        schema = ConcreteDimensionSchema.model_validate(valid_data)
        assert schema.primaryKey.fields == ["id"]


class TestPrimaryKeyValidation:
    def test_missing_primary_key_fails(self):
        """A dimension schema without a primary key is rejected."""
        with pytest.raises(ValueError, match="explicitly defined primary key"):
            ConcreteDimensionSchema.model_validate({"fields": field_data})

    def test_composite_primary_key_passes(self):
        """Composite primary keys are accepted."""
        schema = ConcreteDimensionSchema.model_validate(
            {"primaryKey": ["id", "parent_id"], "fields": field_data}
        )
        assert schema.primaryKey.fields == ["id", "parent_id"]


class TestForeignKeySelfReference:
    def test_external_reference_fails(self):
        """Foreign keys pointing at another resource are rejected."""
        with pytest.raises(ValueError, match="self-referencing foreign"):
            ConcreteDimensionSchema.model_validate(
                {
                    "primaryKey": ["id"],
                    "foreignKeys": [
                        {
                            "fields": ["parent_id"],
                            "reference": {
                                "resource": "other_table",
                                "fields": ["id"],
                            },
                        }
                    ],
                    "fields": field_data,
                }
            )

    def test_self_reference_passes(self, valid_data):
        """Foreign keys with resource=None are accepted as self-references."""
        schema = ConcreteDimensionSchema.model_validate(valid_data)
        assert len(list(schema.foreignKeys)) == 1

    def test_no_foreign_keys_passes(self):
        """A dimension without any foreign keys validates cleanly."""
        schema = ConcreteDimensionSchema.model_validate(
            {"primaryKey": ["id"], "fields": field_data}
        )
        assert not schema.foreignKeys
