import pytest

from crosscontract.contracts.schema import ValueVariableSchema


@pytest.fixture
def valid_data():
    """Data that satisfies all ValueVariableSchema invariants."""
    return {
        "primaryKey": ["country", "year", "unit"],
        "fields": [
            {"name": "country", "type": "string"},
            {"name": "year", "type": "integer"},
            {"name": "unit", "type": "string"},
            {"name": "value", "type": "number"},
        ],
    }


class TestValueVariableInvariants:
    """Test suite for the ValueVariableSchema key-plus-measures invariants."""

    @pytest.mark.parametrize("primary_key", [None, []], ids=["omitted", "empty_list"])
    def test_primary_key_is_required(self, valid_data, primary_key):
        """A ValueVariable without a primary key is rejected.

        The omitted and the empty-list case must not diverge: `primaryKey` has a
        default factory, so omitting it is otherwise silent.
        """
        if primary_key is None:
            del valid_data["primaryKey"]
        else:
            valid_data["primaryKey"] = primary_key

        with pytest.raises(ValueError, match="must have a primary key"):
            ValueVariableSchema.model_validate(valid_data)

    def test_at_least_one_measure_is_required(self, valid_data):
        """A ValueVariable needs a field outside its key, and accepts one."""
        schema = ValueVariableSchema.model_validate(valid_data)
        assert "value" not in schema.primaryKey.fields

        valid_data["primaryKey"] = [field["name"] for field in valid_data["fields"]]

        with pytest.raises(ValueError, match="at least one non-primary key field"):
            ValueVariableSchema.model_validate(valid_data)

    @pytest.mark.parametrize(
        "field_type", ["string", "datetime", "list"], ids=["string", "datetime", "list"]
    )
    def test_fields_outside_the_key_must_be_numeric(self, valid_data, field_type):
        """A non-numeric field outside the key is rejected and named.

        The same types are accepted inside the key: `country` is a string and
        `year` an integer, and the fixture validates.
        """
        valid_data["fields"].append({"name": "source", "type": field_type})

        with pytest.raises(ValueError, match="Non-primary key columns 'source'"):
            ValueVariableSchema.model_validate(valid_data)

    def test_numeric_fields_outside_the_key_are_accepted(self, valid_data):
        """Both `integer` and `number` are measures outside the key."""
        valid_data["fields"].append({"name": "count", "type": "integer"})

        schema = ValueVariableSchema.model_validate(valid_data)

        assert schema["value"].type == "number"
        assert schema["count"].type == "integer"

    def test_all_offending_fields_are_named_in_one_message(self, valid_data):
        """Every non-numeric field outside the key is collected into one message."""
        valid_data["fields"].append({"name": "source", "type": "string"})
        valid_data["fields"].append({"name": "valid_from", "type": "datetime"})

        with pytest.raises(
            ValueError, match="Non-primary key columns 'source', 'valid_from'"
        ):
            ValueVariableSchema.model_validate(valid_data)
