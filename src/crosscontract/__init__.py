"""crosscontract package for data contracts and related utilities."""

from .contracts import BaseContract, CrossContract, SchemaValidationError, TableSchema
from .crossclient import CrossClient
from .registry import CrossRegistry

__version__ = "0.6.0"

__all__ = [
    "CrossClient",
    "CrossContract",
    "TableSchema",
    "BaseContract",
    "SchemaValidationError",
    "CrossRegistry",
]
