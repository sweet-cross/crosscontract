"""crosscontract package for data contracts and related utilities."""

from .contracts import BaseContract, CrossContract, SchemaValidationError, TableSchema
from .crossclient import CrossClient
from .registry import CrossRegistry
from .submission import SubmissionContract

__version__ = "0.15.0"

__all__ = [
    "CrossClient",
    "CrossContract",
    "TableSchema",
    "BaseContract",
    "SchemaValidationError",
    "CrossRegistry",
    "SubmissionContract",
]
