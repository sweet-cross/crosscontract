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
