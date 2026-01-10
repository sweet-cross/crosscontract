import pytest

from crosscontract.contracts.schema.reference import PrimaryKey


class TestPrimaryKey:
    def test_primary_key_creation(self):
        pk = PrimaryKey(["id", "email"])
        assert pk.root == ["id", "email"]

    def test_primary_key_from_singleton(self):
        pk = PrimaryKey("id")
        assert pk.root == ["id"]

    def test_validate_fields_success(self):
        pk = PrimaryKey(["id", "email"])
        pk.validate_fields(field_names=["id", "email", "name"])

    def test_validate_fields_failure(self):
        pk = PrimaryKey(["id", "email"])
        with pytest.raises(ValueError) as e:
            pk.validate_fields(["id", "name"])
        assert "email" in str(e.value)

    def test_iteration(self):
        pk = PrimaryKey(["id", "email"])
        fields = list(pk)
        assert fields == ["id", "email"]
