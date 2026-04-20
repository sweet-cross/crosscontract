import pytest

from crosscontract.contracts.schema import FlexibleDimensionSchema

base_fields = [
    {"name": "id", "type": "integer"},
    {"name": "label", "type": "string"},
    {"name": "description", "type": "string"},
]


@pytest.fixture
def valid_data():
    """Data that satisfies all FlexibleDimensionSchema invariants."""
    return {
        "primaryKey": ["id"],
        "fields": base_fields,
    }


class TestMandatoryFields:
    def test_valid_schema_passes(self, valid_data):
        """A schema with label and description as strings validates cleanly."""
        schema = FlexibleDimensionSchema.model_validate(valid_data)
        assert schema.has_fields(["label", "description"])
        assert schema.table_type == "FlexibleDimension"

    def test_missing_label_fails(self):
        """Omitting the mandatory label field is rejected."""
        with pytest.raises(ValueError, match="missing field 'label'"):
            FlexibleDimensionSchema.model_validate(
                {
                    "primaryKey": ["id"],
                    "fields": [
                        {"name": "id", "type": "integer"},
                        {"name": "description", "type": "string"},
                    ],
                }
            )

    def test_missing_description_fails(self):
        """Omitting the mandatory description field is rejected."""
        with pytest.raises(ValueError, match="missing field 'description'"):
            FlexibleDimensionSchema.model_validate(
                {
                    "primaryKey": ["id"],
                    "fields": [
                        {"name": "id", "type": "integer"},
                        {"name": "label", "type": "string"},
                    ],
                }
            )

    def test_wrong_type_fails(self):
        """A mandatory field with the wrong type is rejected."""
        with pytest.raises(ValueError, match="must be of type 'string'"):
            FlexibleDimensionSchema.model_validate(
                {
                    "primaryKey": ["id"],
                    "fields": [
                        {"name": "id", "type": "integer"},
                        {"name": "label", "type": "integer"},
                        {"name": "description", "type": "string"},
                    ],
                }
            )

    def test_extra_user_fields_allowed(self, valid_data):
        """User-defined fields beyond the mandatory ones are permitted."""
        valid_data["fields"] = [
            *base_fields,
            {"name": "custom_attribute", "type": "number"},
        ]
        schema = FlexibleDimensionSchema.model_validate(valid_data)
        assert schema.has_fields(["label", "description", "custom_attribute"])


class TestInheritedInvariants:
    def test_missing_primary_key_fails(self):
        """The primary key requirement inherited from BaseDimensionSchema applies."""
        with pytest.raises(ValueError, match="explicitly defined primary key"):
            FlexibleDimensionSchema.model_validate({"fields": base_fields})

    def test_external_foreign_key_fails(self, valid_data):
        """The self-reference-only rule from BaseDimensionSchema applies."""
        valid_data["fields"] = [
            *base_fields,
            {"name": "parent_id", "type": "integer"},
        ]
        valid_data["foreignKeys"] = [
            {
                "fields": ["parent_id"],
                "reference": {"resource": "other_table", "fields": ["id"]},
            }
        ]
        with pytest.raises(ValueError, match="self-referencing foreign"):
            FlexibleDimensionSchema.model_validate(valid_data)
