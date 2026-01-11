from copy import deepcopy

import pytest
from pydantic import ValidationError

from crosscontract.contracts import BaseContract, CrossContract, TableSchema

data_base_contract = {
    "name": "data_base_contract",
    "tableschema": {
        "primaryKey": ["id"],
        "foreignKeys": [
            {
                "fields": ["id"],
                "reference": {
                    "resource": "some_other_contract",
                    "fields": ["id"],
                },
            }
        ],
        "fields": [
            {"name": "id", "type": "integer"},
            {"name": "value", "type": "number"},
            {"name": "timestamp", "type": "string"},
            {"name": "location", "type": "string"},
        ],
    },
}


class TestBaseContract:
    def test_valid_base_contract(self):
        # data provide a valid BaseContract
        contract = BaseContract.model_validate(data_base_contract)
        assert contract.name == "data_base_contract"

        assert contract.tableschema.primaryKey.root == ["id"]
        assert len(contract.tableschema.fields) == 4

        # setting the schema is possible through the property
        other_schema = {
            "fields": [
                {"name": "location", "type": "string"},
            ]
        }
        contract.tableschema = TableSchema.model_validate(other_schema)
        assert len(contract.tableschema.fields) == 1
        assert contract.tableschema.primaryKey.root == []

    def test_from_json_file(self, tmp_path):
        import json

        file_path = tmp_path / "contract.json"
        with open(file_path, "w") as f:
            json.dump(data_base_contract, f)

        contract = BaseContract.from_file(file_path)
        assert contract.name == "data_base_contract"
        assert len(contract.tableschema.fields) == 4

    def test_from_yaml_file(self, tmp_path):
        import yaml

        file_path = tmp_path / "contract.yaml"
        with open(file_path, "w") as f:
            yaml.dump(data_base_contract, f)

        contract = BaseContract.from_file(file_path)
        assert contract.name == "data_base_contract"
        assert len(contract.tableschema.fields) == 4

    def test_self_reference_error(self):
        # Test that self-referencing schema raises an error
        invalid_data = deepcopy(data_base_contract)
        invalid_data["tableschema"].update(
            {
                "foreignKeys": [
                    {
                        "fields": ["id"],
                        "reference": {
                            "resource": "data_base_contract",
                            "fields": ["id"],
                        },
                    }
                ]
            }
        )

        with pytest.raises(ValidationError):
            BaseContract.model_validate(invalid_data)


class TestCrossContract:
    def test_valid(self):
        new_data = data_base_contract.copy()
        new_data["title"] = "Data Base Contract"
        new_data["description"] = "This is a base contract for data."
        new_data["tags"] = ["tag1", "tag2"]

        # BaseContract should raise error due to unexpected fields
        with pytest.raises(ValueError):
            BaseContract.model_validate(new_data)

        # CrossContract should be valid
        cross_contract = CrossContract.model_validate(new_data)
        assert cross_contract.tags == ["tag1", "tag2"]

    def test_missing_fields(self):
        new_data = data_base_contract.copy()

        # BaseContract should raise error due to missing fields
        with pytest.raises(ValueError):
            CrossContract.model_validate(new_data)
