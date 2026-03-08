"""crosscontract package for data contracts and related utilities."""

from .contracts import BaseContract, CrossContract, SchemaValidationError, TableSchema
from .crossclient import CrossClient

__version__ = "0.2.3"

__all__ = [
    "CrossClient",
    "CrossContract",
    "TableSchema",
    "BaseContract",
    "SchemaValidationError",
]
