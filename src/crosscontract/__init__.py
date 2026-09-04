"""crosscontract package for data contracts and related utilities."""

from .contracts import BaseContract, CrossContract, SchemaValidationError, TableSchema
from .crossclient import CrossClient
from .registry import CrossRegistry
from .submission import (
    CrossSubmitter,
    SubmissionContract,
    SubmissionHandler,
    TargetValidationError,
    UnclaimedRowsError,
)

__version__ = "0.20.0"

__all__ = [
    "CrossClient",
    "CrossContract",
    "TableSchema",
    "BaseContract",
    "SchemaValidationError",
    "CrossRegistry",
    "CrossSubmitter",
    "SubmissionContract",
    "SubmissionHandler",
    "TargetValidationError",
    "UnclaimedRowsError",
]
