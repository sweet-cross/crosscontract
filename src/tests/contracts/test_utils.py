import json

import pytest
import yaml

from crosscontract.contracts.utils import read_yaml_or_json_file


class TestReadYamlOrJsonFile:
    def test_read_json(self, tmp_path):
        data = {"key": "value", "number": 1}
        file_path = tmp_path / "test.json"
        with open(file_path, "w") as f:
            json.dump(data, f)

        result = read_yaml_or_json_file(file_path)
        assert result == data

    def test_read_yaml(self, tmp_path):
        data = {"key": "value", "number": 1}
        file_path = tmp_path / "test.yaml"
        with open(file_path, "w") as f:
            yaml.dump(data, f)

        result = read_yaml_or_json_file(file_path)
        assert result == data

    def test_read_yml(self, tmp_path):
        data = {"key": "value", "number": 1}
        file_path = tmp_path / "test.yml"
        with open(file_path, "w") as f:
            yaml.dump(data, f)

        result = read_yaml_or_json_file(file_path)
        assert result == data

    def test_file_not_found(self, tmp_path):
        file_path = tmp_path / "nonexistent.json"
        with pytest.raises(FileNotFoundError):
            read_yaml_or_json_file(file_path)

    def test_invalid_extension(self, tmp_path):
        file_path = tmp_path / "test.txt"
        file_path.touch()
        with pytest.raises(ValueError, match="Invalid file format"):
            read_yaml_or_json_file(file_path)
