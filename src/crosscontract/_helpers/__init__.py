"""Internal, dependency-free helpers shared across the package.

- `_pydantic` — reusable pydantic types (`OptionalNonEmptyList`).
- `_io` — file readers (`read_yaml_or_json_file`).
"""

from ._io import read_yaml_or_json_file
from ._pydantic import OptionalNonEmptyList

__all__ = ["OptionalNonEmptyList", "read_yaml_or_json_file"]
