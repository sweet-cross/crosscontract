import pytest

from crosscontract.contracts.schema import ValueVariableSchema

base_fields = [
    {"name": "country", "type": "string"},
    {"name": "year", "type": "integer"},
    {"name": "unit", "type": "string"},
    {"name": "value", "type": "number"},
]


@pytest.fixture
def valid_data():
    """Data that satisfies all ValueVariableSchema invariants."""
    return {
        "primaryKey": ["country", "year", "unit"],
        "fields": base_fields,
    }


class TestValueVariableInvariants:
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
        assert ValueVariableSchema.model_validate(valid_data).has_fields(["value"])

        valid_data["primaryKey"] = [field["name"] for field in base_fields]

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
        valid_data["fields"] = [*base_fields, {"name": "source", "type": field_type}]

        with pytest.raises(ValueError, match="Non-primary key columns 'source'"):
            ValueVariableSchema.model_validate(valid_data)
