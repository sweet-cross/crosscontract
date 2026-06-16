import json
from pathlib import Path
from typing import Any

import yaml


def read_yaml_or_json_file(file_path: str | Path) -> dict[str, Any]:
    """Read a YAML or JSON file and return its contents as a dictionary.

    Args:
        file_path (str | Path): The path to the YAML or JSON file.

    Returns:
        dict[str, Any]: The contents of the file as a dictionary.

    Raises:
        FileNotFoundError: If the specified file does not exist.
        ValueError: If the file format is not supported (not .json, .yaml, or .yml).
    """
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    match file_path.suffix.lower():
        case ".yaml" | ".yml":
            with open(file_path, encoding="utf-8") as f:
                data = yaml.safe_load(f)
        case ".json":
            with open(file_path, encoding="utf-8") as f:
                data = json.load(f)
        case _:
            raise ValueError(
                "Invalid file format. Only .json, .yaml, and .yml are supported."
            )
    return data


class IndentedDumper(yaml.SafeDumper):
    """SafeDumper that indents block sequences under their parent key."""

    def increase_indent(self, flow: bool = False, indentless: bool = False) -> None:
        return super().increase_indent(flow, False)


def _represent_none_as_empty(dumper: yaml.SafeDumper, _value: None) -> yaml.ScalarNode:
    """Render `None` as a bare `key:` (empty scalar) instead of `key: null`."""
    return dumper.represent_scalar("tag:yaml.org,2002:null", "")


IndentedDumper.add_representer(type(None), _represent_none_as_empty)


def dump_to_file(data: Any, path: str | Path) -> None:
    """Write `data` to `path`, picking format from the file extension.

    `.json` produces JSON via `json.dumps` with two-space indent.
    `.yaml` / `.yml` produces YAML via `IndentedDumper` with
    `sort_keys=False`. Any other extension raises `ValueError`.

    `data` should already be a JSON-serializable structure (typically the
    result of `BaseModel.model_dump(mode="json", ...)`).

    Args:
        data: The data to write.
        path: Target file path; must end in `.json`, `.yaml`, or `.yml`.
    """
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == ".json":
        path.write_text(json.dumps(data, indent=2))
    elif suffix in (".yaml", ".yml"):
        with path.open("w") as f:
            yaml.dump(data, f, Dumper=IndentedDumper, sort_keys=False)
    else:
        raise ValueError(
            f"Unsupported extension '{suffix}'. Use .json, .yaml, or .yml."
        )
