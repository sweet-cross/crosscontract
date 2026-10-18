"""crosscontract package for data contracts and related utilities."""

from .contracts import (
    BaseContract,
    CrossContract,
    CrossDataPackageReleaseSpec,
    CrossDataResourceReleaseSpec,
    SchemaValidationError,
    TableSchema,
)
from .crossclient import CrossClient
from .registry import CrossRegistry
from .submission import (
    CrossSubmitter,
    Submission,
    SubmissionContract,
    SubmissionHandler,
    TargetValidationError,
    UnclaimedRowsError,
)

__version__ = "0.31.0"

__all__ = [
    "CrossClient",
    "CrossContract",
    "CrossDataPackageReleaseSpec",
    "CrossDataResourceReleaseSpec",
    "TableSchema",
    "BaseContract",
    "SchemaValidationError",
    "CrossRegistry",
    "CrossSubmitter",
    "Submission",
    "SubmissionContract",
    "SubmissionHandler",
    "TargetValidationError",
    "UnclaimedRowsError",
]
