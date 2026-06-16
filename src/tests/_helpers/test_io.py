import json

import pytest
import yaml

from crosscontract._helpers import dump_to_file, read_yaml_or_json_file


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


class TestDumpToFile:
    def test_dump_json(self, tmp_path):
        data = {"key": "value", "number": 1}
        file_path = tmp_path / "out.json"
        dump_to_file(data, file_path)
        assert json.loads(file_path.read_text()) == data

    def test_dump_json_is_indented(self, tmp_path):
        file_path = tmp_path / "out.json"
        dump_to_file({"key": "value"}, file_path)
        assert file_path.read_text() == '{\n  "key": "value"\n}'

    def test_dump_yaml(self, tmp_path):
        data = {"key": "value", "number": 1}
        file_path = tmp_path / "out.yaml"
        dump_to_file(data, file_path)
        assert yaml.safe_load(file_path.read_text()) == data

    def test_dump_yml_extension(self, tmp_path):
        data = {"key": "value"}
        file_path = tmp_path / "out.yml"
        dump_to_file(data, file_path)
        assert yaml.safe_load(file_path.read_text()) == data

    def test_extension_is_case_insensitive(self, tmp_path):
        file_path = tmp_path / "out.JSON"
        dump_to_file({"key": "value"}, file_path)
        assert json.loads(file_path.read_text()) == {"key": "value"}

    def test_accepts_str_path(self, tmp_path):
        file_path = tmp_path / "out.json"
        dump_to_file({"key": "value"}, str(file_path))
        assert json.loads(file_path.read_text()) == {"key": "value"}

    def test_unsupported_extension_raises(self, tmp_path):
        with pytest.raises(ValueError, match="Unsupported extension"):
            dump_to_file({"key": "value"}, tmp_path / "out.txt")

    def test_roundtrips_with_reader(self, tmp_path):
        data = {"key": "value", "nested": {"a": [1, 2, 3]}}
        for name in ("rt.json", "rt.yaml", "rt.yml"):
            file_path = tmp_path / name
            dump_to_file(data, file_path)
            assert read_yaml_or_json_file(file_path) == data

    def test_yaml_preserves_key_order(self, tmp_path):
        # sort_keys=False: keys keep insertion order rather than being sorted.
        data = {"b": 1, "a": 2, "c": 3}
        file_path = tmp_path / "ordered.yaml"
        dump_to_file(data, file_path)
        text = file_path.read_text()
        assert text.index("b:") < text.index("a:") < text.index("c:")


class TestYamlFormatting:
    """The `IndentedDumper` / `_represent_none_as_empty` helpers, via output."""

    def test_none_renders_as_empty_not_null(self, tmp_path):
        file_path = tmp_path / "none.yaml"
        dump_to_file({"key": None}, file_path)
        text = file_path.read_text()
        assert "null" not in text
        assert yaml.safe_load(text) == {"key": None}

    def test_block_sequences_are_indented(self, tmp_path):
        file_path = tmp_path / "seq.yaml"
        dump_to_file({"items": ["x", "y"]}, file_path)
        text = file_path.read_text()
        # IndentedDumper indents list items under their parent key.
        assert "  - x" in text
        assert yaml.safe_load(text) == {"items": ["x", "y"]}
