"""Integration tests: validate data against Pydantic models created from schemas."""

import pytest
from pydantic import ValidationError

from crosscontract.contracts.schema import TableSchema
from crosscontract.contracts.schema.adapters.pydantic_adapter import PydanticAdapter


@pytest.fixture
def make_model():
    """Helper to create a Pydantic model from a list of field dicts."""

    def _make(fields: list[dict]) -> type:
        schema = TableSchema.model_validate({"fields": fields})
        return PydanticAdapter(schema).convert()

    return _make


class TestListFieldValidation:
    """Integration tests for list field validation against generated models."""

    def test_list_of_strings_accepts_valid_data(self, make_model):
        Model = make_model(
            [
                {
                    "name": "tags",
                    "type": "list",
                    "itemType": "string",
                    "constraints": {"required": True},
                }
            ]
        )
        instance = Model(tags=["a", "b", "c"])
        assert instance.tags == ["a", "b", "c"]

    def test_list_of_integers_accepts_valid_data(self, make_model):
        Model = make_model(
            [
                {
                    "name": "ids",
                    "type": "list",
                    "itemType": "integer",
                    "constraints": {"required": True},
                }
            ]
        )
        instance = Model(ids=[1, 2, 3])
        assert instance.ids == [1, 2, 3]

    def test_list_of_floats_accepts_valid_data(self, make_model):
        Model = make_model(
            [
                {
                    "name": "scores",
                    "type": "list",
                    "itemType": "number",
                    "constraints": {"required": True},
                }
            ]
        )
        instance = Model(scores=[1.5, 2.7])
        assert instance.scores == [1.5, 2.7]

    def test_list_of_booleans_accepts_valid_data(self, make_model):
        Model = make_model(
            [
                {
                    "name": "flags",
                    "type": "list",
                    "itemType": "boolean",
                    "constraints": {"required": True},
                }
            ]
        )
        instance = Model(flags=[True, False])
        assert instance.flags == [True, False]

    def test_list_rejects_wrong_item_type_in_strict_mode(self, make_model):
        """Strings that aren't valid ints should be rejected."""
        Model = make_model(
            [
                {
                    "name": "ids",
                    "type": "list",
                    "itemType": "integer",
                    "constraints": {"required": True},
                }
            ]
        )
        with pytest.raises(ValidationError):
            Model(ids=["not_a_number"])

    def test_list_min_length_rejects_too_short(self, make_model):
        Model = make_model(
            [
                {
                    "name": "tags",
                    "type": "list",
                    "itemType": "string",
                    "constraints": {"required": True, "minLength": 2},
                }
            ]
        )
        with pytest.raises(ValidationError):
            Model(tags=["only_one"])

    def test_list_max_length_rejects_too_long(self, make_model):
        Model = make_model(
            [
                {
                    "name": "tags",
                    "type": "list",
                    "itemType": "string",
                    "constraints": {"required": True, "maxLength": 2},
                }
            ]
        )
        with pytest.raises(ValidationError):
            Model(tags=["a", "b", "c"])

    def test_optional_list_accepts_none(self, make_model):
        Model = make_model(
            [
                {
                    "name": "tags",
                    "type": "list",
                    "itemType": "string",
                    "constraints": {"required": False},
                }
            ]
        )
        instance = Model(tags=None)
        assert instance.tags is None

    def test_empty_list_accepted_when_no_min_length(self, make_model):
        Model = make_model(
            [
                {
                    "name": "tags",
                    "type": "list",
                    "itemType": "string",
                    "constraints": {"required": True},
                }
            ]
        )
        instance = Model(tags=[])
        assert instance.tags == []


class TestMixedSchemaValidation:
    """Integration tests for schemas combining list fields with other field types."""

    @pytest.fixture
    def mixed_model(self, make_model):
        return make_model(
            [
                {
                    "name": "name",
                    "type": "string",
                    "constraints": {"required": True, "minLength": 1},
                },
                {
                    "name": "score",
                    "type": "number",
                    "constraints": {"required": True, "minimum": 0.0},
                },
                {
                    "name": "tags",
                    "type": "list",
                    "itemType": "string",
                    "constraints": {"required": True},
                },
                {"name": "year", "type": "integer", "constraints": {"required": True}},
            ]
        )

    def test_valid_mixed_data(self, mixed_model):
        instance = mixed_model(name="test", score=9.5, tags=["a", "b"], year=2024)
        assert instance.tags == ["a", "b"]
        assert instance.name == "test"

    def test_invalid_list_in_mixed_schema_raises(self, mixed_model):
        with pytest.raises(ValidationError):
            mixed_model(name="test", score=9.5, tags="not_a_list", year=2024)

    def test_missing_required_list_raises(self, mixed_model):
        with pytest.raises(ValidationError):
            mixed_model(name="test", score=9.5, year=2024)
